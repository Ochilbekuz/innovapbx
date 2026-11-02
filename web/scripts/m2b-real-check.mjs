// M2b sahifalarini HAQIQIY API bilan tekshiradi: admin -> /live, /settings/users, /analytics, /queues;
// keyin API orqali operator (ext bilan) yaratiladi -> operator login -> majburiy parol almashtirish -> /me.
// 5xx va JS xatosi yo'qligi + skrinshot. Ishga tushirish: CHROME_PATH=... node web/scripts/m2b-real-check.mjs (stek ko'tarilgan bo'lsin).
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
  await page.screenshot({ path: path.join(SHOTS, `m2b-real-${name}.png`) });
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

    await check(page, 'live', '/live', 'main');
    await check(page, 'users', '/settings/users', 'text=admin');
    await check(page, 'analytics', '/analytics', 'main');
    await check(page, 'queues', '/queues', 'main');

    // Operator: API orqali (admin tokeni bilan) ext + foydalanuvchi.
    const login = await fetch('http://127.0.0.1:8710/api/v1/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ login: 'admin', password: adminPassword() }) });
    const token = (await login.json()).access;
    if (!token) throw new Error('admin access token topilmadi');
    const api = async (method, url, body) => {
      const r = await fetch('http://127.0.0.1:8710/api/v1' + url, { method, headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' }, body: body && JSON.stringify(body) });
      const j = await r.json().catch(() => ({})); if (r.status >= 300) throw new Error(`${method} ${url} -> ${r.status} ${JSON.stringify(j)}`); return j;
    };
    const num = String(170 + Math.floor(Math.random() * 20));
    const ext = await api('POST', '/extensions', { number: num, name: `Operator ${num}` });
    const uname = `op${num}${Date.now() % 10000}`;
    await api('POST', '/users', { username: uname, full_name: `Operator ${num}`, role: 'operator', extension_id: ext.item.id, password: 'Boshlangich-2026' });

    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const op = await ctx.newPage();
    op.on('pageerror', (e) => errors.push(String(e)));
    op.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });
    await op.goto(BASE + '/login');
    await op.getByLabel('Login').fill(uname);
    await op.getByLabel('Parol').fill('Boshlangich-2026');
    await op.getByRole('button', { name: 'Kirish' }).click();
    await op.waitForURL(/\/change-password/, { timeout: 10000 });
    await op.getByLabel('Joriy parol').fill('Boshlangich-2026');
    await op.getByLabel('Yangi parol').fill('Yangi-Parol-2026x');
    await op.getByRole('button', { name: /Parolni/ }).click();
    await op.waitForURL(/\/me/, { timeout: 10000 });
    await delay(2500);
    await op.screenshot({ path: path.join(SHOTS, 'm2b-real-me.png') });
    console.log('me url', op.url(), (await op.locator('main').innerText()).slice(0, 600).replace(/\n/g, ' | '));
    await op.getByText(num).first().waitFor({ timeout: 10000 });
    await delay(1500);
    await op.screenshot({ path: path.join(SHOTS, 'm2b-real-me.png') });
    console.log(`OK: operator ${uname} -> /change-password -> /me (ext ${num})`);
    await op.goto(BASE + '/extensions');
    await delay(1000);
    if (/\/extensions/.test(new URL(op.url()).pathname) && await op.getByRole('table').count()) errors.push('operator /extensions jadvalini ko\'rdi');
    console.log(`operator /extensions -> ${op.url()}`);
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
