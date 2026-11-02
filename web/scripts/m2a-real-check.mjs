// M2a sahifalarini HAQIQIY API bilan tekshiradi: `VITE_API=real` (proxy /api -> 127.0.0.1:8710), login,
// feature-kodlar / konferensiya / qora ro'yxat / dashboard sahifalari ochilishi, 5xx va JS xatosi yo'qligi + skrinshot.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m2a-real-check.mjs (stek ko'tarilgan bo'lsin).
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const WEB_DIR = path.join(ROOT, '..');
const SHOTS = path.join(ROOT, '..', '..', 'replica', 'clone-screens');
const BASE = 'http://127.0.0.1:5174';

function adminPassword() {
  if (process.env.PROOF_ADMIN_PASSWORD) return process.env.PROOF_ADMIN_PASSWORD;
  const env = readFileSync(new URL('../../deploy/.env', import.meta.url), 'utf8');
  return env.match(/^PROOF_ADMIN_PASSWORD=(.+)$/m)[1].trim();
}

async function waitForServer(url, maxMs) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try { if ((await fetch(url)).status < 500) return; } catch {}
    await delay(500);
  }
  throw new Error('vite dev server timeout');
}

async function check(page, name, url, locator) {
  await page.goto(BASE + url);
  await page.locator(locator).first().waitFor({ timeout: 10000 });
  await delay(800);
  await page.screenshot({ path: path.join(SHOTS, `m2a-real-${name}.png`) });
  console.log(`OK: ${url}`);
}

async function main() {
  const vite = spawn(path.join(WEB_DIR, 'node_modules', '.bin', 'vite'), ['--port', '5174', '--strictPort'], {
    cwd: WEB_DIR, env: { ...process.env, VITE_API: 'real' }, stdio: 'ignore',
  });
  let failed = false;
  try {
    await waitForServer(BASE + '/', 30000);
    const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });

    await page.goto(BASE + '/login');
    await page.getByLabel('Login').fill('admin');
    await page.getByLabel('Parol').fill(adminPassword());
    await page.getByRole('button', { name: 'Kirish' }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });

    await check(page, 'featurecodes', '/settings/feature-codes', 'text=*97');
    await check(page, 'conference', '/conference', 'main');
    await check(page, 'blacklist', '/blacklist', 'main');
    await check(page, 'dashboard', '/dashboard', 'main');
    if (errors.length) { failed = true; console.log('XATO:', errors.join('\n')); }
    await browser.close();
  } catch (e) {
    failed = true;
    console.log('XATO:', e.message);
  } finally {
    vite.kill('SIGTERM');
  }
  console.log(failed ? 'NATIJA: FAIL' : 'NATIJA: PASS');
  process.exit(failed ? 1 : 0);
}

main();
