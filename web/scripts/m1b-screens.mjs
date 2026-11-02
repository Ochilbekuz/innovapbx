// M1b frontend — fake backend skrinshotlari (Playwright, bir martalik skript).
// `web/`ni fake API bilan ishga tushiradi (VITE_API default), Setup sehrgarini bir marta toʻldiradi,
// soʻng faqat SPA navigatsiya (Link bosish) orqali ekranlar orasida oʻtadi — chunki fake.ts holati
// JS modul xotirasida saqlanadi va `page.goto()` har safar uni qayta "needed=true" holatiga qaytaradi.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url)); // web/scripts
const WEB_DIR = path.join(ROOT, '..'); // web/
const OUT_DIR = path.join(ROOT, '..', '..', 'replica', 'screens-m1b');
const PORT = 5180;
const BASE = `http://127.0.0.1:${PORT}`;

mkdirSync(OUT_DIR, { recursive: true });

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

const errors = [];

async function shot(page, name) {
  // Sichqonchani betaraf nuqtaga olib boramiz — aks holda tez-tez bosishdan headless Chromium'da
  // eski :hover bo'yoq (paint) ekranga "muzlab qolishi" mumkin (haqiqiy ilova holati emas, faqat render artefakti).
  await page.mouse.move(700, 10);
  await delay(350); // animatsiya/transition va qayta chizish tugashini kutish
  await page.screenshot({ path: path.join(OUT_DIR, `${name}.png`), fullPage: false });
  console.log(`OK: ${name}.png`);
}

/** Yorugʻ holatda skrinshot, soʻng qorongʻiga oʻtib yana bir marta — oxirida yorugʻga qaytaradi.
 * Eslatma: tema almashtirish tugmasi header'da — Drawer/Dialog ochiq paytda bosilmaydi (focus-trap/overlay
 * uni bosilmas qiladi), shu sabab drawer skrinshotlari uchun alohida `shotDrawerBoth()` ishlatiladi. */
async function shotBoth(page, name) {
  await shot(page, `${name}-light`);
  await page.getByRole('button', { name: 'Qorongʻi rejim' }).click();
  await shot(page, `${name}-dark`);
  await page.getByRole('button', { name: 'Yorugʻ rejim' }).click();
  await delay(150);
}

/** Drawer/Dialog ochiq paytda tema tugmasi bosilmaydi — avval yopib tema almashtiramiz, qayta ochib dark skrinshot olamiz. */
async function shotDrawerBoth(page, name, openDrawer, closeDrawerFn) {
  await shot(page, `${name}-light`);
  await closeDrawerFn(page);
  await page.getByRole('button', { name: 'Qorongʻi rejim' }).click();
  await openDrawer(page);
  await shot(page, `${name}-dark`);
  await closeDrawerFn(page);
  await page.getByRole('button', { name: 'Yorugʻ rejim' }).click();
  await delay(150);
}

async function runSetup(page) {
  await page.goto(`${BASE}/`);
  await page.waitForURL(/\/setup/, { timeout: 10000 });
  await page.getByLabel('Login').fill('admin');
  await page.getByLabel('Toʻliq ism').fill('Admin Aliyev');
  await page.getByLabel('Parol').fill('Admin12345!');
  await page.getByRole('button', { name: 'Davom etish' }).click();
  await page.getByRole('button', { name: /ishga tushirish/ }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 10000 });
  console.log('OK: setup -> /dashboard');
}

async function openOutboundDrawer(page) {
  await page.getByRole('button', { name: 'Yangi marshrut' }).click();
  await page.getByRole('dialog').waitFor({ timeout: 5000 });
}

async function closeDrawer(page) {
  await page.keyboard.press('Escape');
  await delay(200);
}

async function main() {
  const viteBin = path.join(WEB_DIR, 'node_modules', '.bin', 'vite');
  const vite = spawn(viteBin, ['--port', String(PORT), '--strictPort'], {
    cwd: WEB_DIR,
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let viteOut = '';
  vite.stdout.on('data', (d) => (viteOut += d.toString()));
  vite.stderr.on('data', (d) => (viteOut += d.toString()));

  try {
    await waitForServer(`${BASE}/`, 30000);
    await delay(500);

    const browser = await chromium.launch({
      executablePath: process.env.CHROME_PATH || '/root/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',
      args: ['--no-sandbox'],
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.setDefaultTimeout(12000);
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

    await runSetup(page);
    await shotBoth(page, 'S03-dashboard');

    // --- S22 Chiquvchi marshrutlar: roʻyxat + simulyator, soʻng drawer ---
    await page.getByRole('link', { name: 'Chiquvchi marshrutlar' }).click();
    await page.waitForURL(/\/outbound/, { timeout: 10000 });
    await page.getByText('Simulyator').waitFor({ timeout: 10000 });
    await shotBoth(page, 'S22-outbound-list');
    await openOutboundDrawer(page);
    await shotDrawerBoth(page, 'S22-outbound-drawer', openOutboundDrawer, closeDrawer);

    // --- S32 SIP va tarmoq ---
    await page.getByRole('link', { name: 'SIP va tarmoq' }).click();
    await page.waitForURL(/\/settings\/sip/, { timeout: 10000 });
    await delay(300);
    await shotBoth(page, 'S32-sip');

    // --- Audit jurnali ---
    await page.getByRole('link', { name: 'Audit jurnali' }).click();
    await page.waitForURL(/\/settings\/audit/, { timeout: 10000 });
    await delay(300);
    await shotBoth(page, 'S37-audit');

    // --- Revisions (header RevisionBadge orqali) ---
    await page.getByTitle('Konfiguratsiya reviziyalari tarixi').click();
    await page.waitForURL(/\/settings\/revisions/, { timeout: 10000 });
    await delay(300);
    await shotBoth(page, 'revisions');

    // --- S11 Audio: fayllar tabi + MoH tabi + rekorder ---
    await page.getByRole('link', { name: 'Audio kutubxona' }).click();
    await page.waitForURL(/\/audio/, { timeout: 10000 });
    await page.getByText('mikrofon bilan yozib oling').waitFor({ timeout: 10000 });
    await delay(300);
    await shotBoth(page, 'S11-audio-files');
    await page.getByRole('tab', { name: 'Kutish musiqasi' }).click();
    await delay(300);
    await shotBoth(page, 'S11-audio-moh');

    console.log(`Konsol xatolar soni: ${errors.length}`);
    if (errors.length) console.log(errors.slice(0, 10).join('\n'));
    if (errors.length) process.exitCode = 1;

    await browser.close();
  } catch (e) {
    console.error('XATO:', e);
    console.error('--- vite chiqishi ---');
    console.error(viteOut);
    process.exitCode = 1;
  } finally {
    vite.kill();
  }
}

const watchdog = setTimeout(() => {
  console.error('XATO: umumiy vaqt tugadi (watchdog 90s) — majburan toʻxtatildi.');
  process.exit(1);
}, 90000);
watchdog.unref?.();

main().finally(() => clearTimeout(watchdog));
