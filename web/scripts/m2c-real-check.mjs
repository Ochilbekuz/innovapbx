// M2c sahifalarini HAQIQIY API bilan tekshiradi: admin -> /settings/security (5 tab), IP'ni UI orqali
// bloklash -> jadvalda ko'rinadi -> UI orqali blokdan chiqarish; /settings/alerts.
// 5xx va JS xatosi yo'qligi + skrinshot. Ishga tushirish: CHROME_PATH=... node web/scripts/m2c-real-check.mjs (stek ko'tarilgan bo'lsin).
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
const TEST_IP = '198.51.100.77'; // TEST-NET-2 — hech qachon haqiqiy mijoz emas

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

async function shot(page, name) {
  await delay(800);
  await page.screenshot({ path: path.join(SHOTS, `m2c-real-${name}.png`) });
}

async function checkTabs(page) {
  await page.goto(BASE + '/settings/security');
  await page.locator('main').first().waitFor({ timeout: 10000 });
  for (const [name, label] of [['status', 'Holat'], ['bans', 'Bloklangan IP'], ['toll', 'Toll-fraud'], ['settings', 'Sozlamalar'], ['events', 'Hodisalar']]) {
    await page.getByRole('tab', { name: label }).click();
    await shot(page, `security-${name}`);
    console.log(`OK: /settings/security tab ${name}`);
  }
}

async function banAndUnbanViaUi(page) {
  await page.getByRole('tab', { name: 'Bloklangan IP' }).click();
  await page.getByRole('button', { name: 'IPʼni bloklash' }).click();
  await page.getByRole('textbox', { name: 'IP manzil', exact: true }).fill(TEST_IP);
  await page.getByRole('button', { name: 'Bloklash', exact: true }).click();
  await page.getByText(TEST_IP).first().waitFor({ timeout: 10000 });
  await shot(page, 'security-ban-added');
  console.log(`OK: ${TEST_IP} UI orqali bloklandi`);
  await page.getByRole('button', { name: `${TEST_IP} ni blokdan chiqarish` }).first().click();
  await page.getByRole('button', { name: 'Blokdan chiqarish' }).click();
  await page.getByRole('cell', { name: TEST_IP }).waitFor({ state: 'detached', timeout: 10000 });
  console.log(`OK: ${TEST_IP} UI orqali blokdan chiqarildi`);
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

    await checkTabs(page);
    await banAndUnbanViaUi(page);

    await page.goto(BASE + '/settings/alerts');
    await page.locator('main').first().waitFor({ timeout: 10000 });
    await shot(page, 'alerts');
    console.log('OK: /settings/alerts');

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
