import { readFileSync } from 'node:fs';
// M0 frontend <-> HAQIQIY backend integratsiya tekshiruvi (Playwright, bir martalik skript).
// `web/`ni `VITE_API=real` bilan ishga tushiradi (proxy /api -> 127.0.0.1:8710), login qiladi,
// Ichki raqamlar va Qo'ng'iroqlar tarixi ekranlarini tekshiradi, skrinshot oladi.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url)); // web/scripts
const WEB_DIR = path.join(ROOT, '..'); // web/
const SCREEN_OUT = path.join(ROOT, '..', '..', 'replica', 'clone-screens', 'M0-real-calls-1440.png');

function waitForServer(url, maxMs) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const r = await fetch(url);
        if (r.ok || r.status < 500) return resolve();
      } catch {}
      if (Date.now() - start > maxMs) return reject(new Error('vite dev server timeout'));
      setTimeout(tick, 500);
    };
    tick();
  });
}

// Parol deploy/.env dan (PROOF_ADMIN_PASSWORD) — kodda sir yo'q.
function adminPassword() {
  if (process.env.PROOF_ADMIN_PASSWORD) return process.env.PROOF_ADMIN_PASSWORD;
  const env = readFileSync(new URL('../../deploy/.env', import.meta.url), 'utf8');
  const m = env.match(/^PROOF_ADMIN_PASSWORD=(.+)$/m);
  if (!m) throw new Error('PROOF_ADMIN_PASSWORD deploy/.env da yo\'q');
  return m[1].trim();
}

async function main() {
  const viteBin = path.join(WEB_DIR, 'node_modules', '.bin', 'vite');
  const vite = spawn(viteBin, ['--port', '5173', '--strictPort'], {
    cwd: WEB_DIR,
    env: { ...process.env, VITE_API: 'real' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let viteOut = '';
  vite.stdout.on('data', (d) => (viteOut += d.toString()));
  vite.stderr.on('data', (d) => (viteOut += d.toString()));

  try {
    await waitForServer('http://127.0.0.1:5173/', 30000);
    await delay(500);

    const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

    await page.goto('http://127.0.0.1:5173/login');
    await page.getByLabel('Login').fill('admin');
    await page.getByLabel('Parol').fill(adminPassword());
    await page.getByRole('button', { name: 'Kirish' }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    console.log('OK: login -> /dashboard');

    await page.goto('http://127.0.0.1:5173/extensions');
    await page.locator('table tbody tr').first().waitFor({ timeout: 10000 });
    const extRows = await page.locator('table tbody tr').count();
    console.log(`OK: /extensions yuklandi, qator soni=${extRows}`);

    await page.goto('http://127.0.0.1:5173/cdr');
    await page.locator('table tbody tr').first().waitFor({ timeout: 10000 });
    const callRows = await page.locator('table tbody tr').count();
    console.log(`OK: /cdr (qo'ng'iroqlar tarixi) yuklandi, qator soni=${callRows}`);

    await page.screenshot({ path: SCREEN_OUT, fullPage: false });
    console.log(`OK: skrinshot saqlandi -> ${SCREEN_OUT}`);

    // --- M1a: audio token bilan olinadi (<audio src> Authorization yubora olmaydi) ---
    const streamStatuses = [];
    page.on('response', (r) => { if (r.url().includes('/audio/') && r.url().endsWith('/stream')) streamStatuses.push(r.status()); });
    await page.goto('http://127.0.0.1:5173/audio');
    await page.locator('table tbody tr').first().waitFor({ timeout: 10000 });
    const errorsBeforePlay = await page.getByText('Fayl topilmadi').count();
    if (errorsBeforePlay) throw new Error(`audio: bosilmasdan ${errorsBeforePlay} ta xato koʻrinyapti`);
    await page.getByRole('button', { name: 'Tinglash' }).first().click();
    await page.waitForFunction(() => { const a = document.querySelector('audio'); return a && a.src.startsWith('blob:') && a.readyState >= 1; }, null, { timeout: 10000 });
    const dur = await page.evaluate(() => document.querySelector('audio')?.duration ?? 0);
    if (!(dur > 0) || streamStatuses.some((s) => s !== 200)) throw new Error(`audio: stream=${streamStatuses} dur=${dur}`);
    console.log(`OK: /audio tinglash — stream ${streamStatuses.join(',')}, blob manzil, davomiylik ${dur.toFixed(1)} s`);
    await page.screenshot({ path: path.join(ROOT, '..', '..', 'replica', 'clone-screens', 'S11-audio-real-1440.png') });

    // --- M1a: oqim paneli sichqoncha bilan ochiladi va ichiga bosish uni yopmaydi (overlay qatlami) ---
    await page.goto('http://127.0.0.1:5173/inbound');
    await page.locator('table tbody tr').first().waitFor({ timeout: 10000 });
    await page.getByRole('button', { name: /qoʻngʻiroq yoʻlini koʻrish/ }).first().click();
    const drawer = page.getByRole('dialog');
    await drawer.locator('figure').waitFor({ timeout: 10000 });
    await drawer.locator('figure').click({ position: { x: 20, y: 20 } });
    await delay(400);
    if (!(await drawer.isVisible())) throw new Error('oqim paneli ichiga bosilganda yopildi (overlay panel ustida)');
    await delay(600);
    await page.screenshot({ path: path.join(ROOT, '..', '..', 'replica', 'clone-screens', 'S07-flow-real-1440.png') });
    console.log('OK: oqim paneli — sichqoncha bilan ochildi, ichiga bosish yopmadi');

    console.log(`Konsol xatolar soni: ${errors.length}`);
    if (errors.length) console.log(errors.slice(0, 5).join('\n'));

    await browser.close();
  } finally {
    vite.kill('SIGTERM');
    await delay(300);
    if (!vite.killed) vite.kill('SIGKILL');
  }
}

main().catch((e) => { console.error('FAIL:', e); process.exit(1); });
