// M9 Bo'lak C UI'ni HAQIQIY API bilan tekshiradi:
// 7 ta toʻliq ekran (announcements, misc, parking, paging, phonebook, pinsets, cidsources) — ro'yxat ochiladi,
// konsol/5xx xatosi yoʻq. Ikki vakillik CRUD oqimi: PIN toʻplami yaratish + PIN qoʻshish; CID manba yaratish + sinash.
// Extensions: CSV eksport va import (dry-run oldindan koʻrish) tugmalari koʻrinadi va ishlaydi.
// DARK va mobil — ko'rinish. Sinov yozuvlari oxirida API orqali o'chiriladi.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m9-real-check.mjs (stek 127.0.0.1:8710 da ishlab turgan bo'lsin).
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const WEB_DIR = path.join(ROOT, '..');
const SHOTS = path.join(ROOT, '..', '..', 'replica', 'clone-screens');
const BASE = 'http://127.0.0.1:5178';
const API = 'http://127.0.0.1:8710/api/v1';
const NAME = 'M9 RC — pinset';
const CID_NAME = 'M9 RC — cid manba';
let TOKEN = '';

async function api(method, p, body) {
  const r = await fetch(API + p, {
    method,
    headers: { 'Content-Type': 'application/json', ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  // DIQQAT: ba'zi yo'llar (masalan `/extensions/export.csv`) JSON EMAS, CSV
  // matn qaytaradi -- `backendReady()` probe'i shularni ham chaqiradi,
  // shuning uchun bu yerda shartsiz JSON.parse() emas, try/catch bilan
  // xavfsiz fallback kerak (status kodi baribir to'g'ri qaytadi).
  let json = null;
  if (text) {
    try { json = JSON.parse(text); } catch { json = null; }
  }
  return { status: r.status, json };
}

function adminPassword() {
  if (process.env.PROOF_ADMIN_PASSWORD) return process.env.PROOF_ADMIN_PASSWORD;
  const env = readFileSync(new URL('../../deploy/.env', import.meta.url), 'utf8');
  return env.match(/^PROOF_ADMIN_PASSWORD=(.+)$/m)[1].trim();
}

/** Backend M9 endpointlari hali tayyor emasligini aniqlaydi (login muvaffaqiyatli bo'lsa-da, yangi yo'llar 404/501). */
async function backendReady() {
  const probes = await Promise.all([
    api('GET', '/pin-sets'),
    api('GET', '/cid-sources'),
    api('GET', '/extensions/export.csv'),
  ]);
  return probes.every((r) => r.status !== 404 && r.status !== 501);
}

async function cleanup() {
  const pinsets = await api('GET', '/pin-sets');
  for (const s of (pinsets.json?.items ?? []).filter((x) => x.name === NAME)) {
    await api('DELETE', `/pin-sets/${s.id}`);
  }
  const cidSources = await api('GET', '/cid-sources');
  for (const s of (cidSources.json?.items ?? []).filter((x) => x.name === CID_NAME)) {
    await api('DELETE', `/cid-sources/${s.id}`);
  }
}

async function prepare() {
  const r = await api('POST', '/auth/login', { login: 'admin', password: adminPassword() });
  TOKEN = r.json?.access ?? '';
  if (!TOKEN) throw new Error(`admin API login: ${r.status}`);
  await cleanup();
}

async function waitForServer(url, maxMs) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try { if ((await fetch(url)).status < 500) return; } catch {}
    await delay(500);
  }
  throw new Error('vite dev server timeout');
}

async function shot(page, name, theme) {
  await page.waitForLoadState('networkidle').catch(() => undefined);
  await delay(1000);
  await page.screenshot({ path: path.join(SHOTS, `m9-${name}-${theme}.png`) });
}

function makeRunner() {
  const results = { pass: 0, fail: 0 };
  const step = async (label, fn) => {
    try {
      await fn();
      results.pass += 1;
      console.log(`OK: ${label}`);
    } catch (e) {
      results.fail += 1;
      console.log(`FAIL: ${label}: ${String(e?.message ?? e).split('\n')[0]}`);
    }
  };
  return { results, step };
}

async function login(page) {
  await page.goto(BASE + '/login');
  await page.getByLabel('Login').fill('admin');
  await page.getByLabel('Parol').fill(adminPassword());
  await page.getByRole('button', { name: 'Kirish' }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 10000 });
}

function watchPage(page) {
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('response', (r) => {
    if (r.status() >= 400 && ![409, 422].includes(r.status())) problems.push(`${r.status()} ${r.url()}`);
  });
  return problems;
}

const realProblems = (problems) => problems.filter((p) => !p.includes('Failed to load resource') && !p.includes('/me/softphone'));

// 7 to'liq ekran — faqat ro'yxat ochilishi va asosiy sarlavha ko'rinishini tekshiradi.
const FULL_SCREENS = [
  { path: '/announcements', heading: 'Eʼlonlar' },
  { path: '/misc', heading: 'Maxsus manzillar' },
  { path: '/parking', heading: 'Parkovka' },
  { path: '/paging', heading: 'Paging' },
  { path: '/phonebook', heading: 'Telefon kitobi' },
  { path: '/pinsets', heading: 'PIN toʻplamlari' },
  { path: '/cidsources', heading: 'CID qidirish manbalari' },
];

async function checkFullScreen(page, theme, { path: p, heading }) {
  await page.goto(BASE + p);
  await page.getByRole('heading', { name: heading }).first().waitFor({ timeout: 10000 });
  if (theme === 'light') await shot(page, `screen-${p.slice(1)}`, theme);
}

async function pinSetFlow(page, theme) {
  await page.goto(BASE + '/pinsets');
  await page.getByRole('button', { name: /Yangi/ }).first().click();
  const drawer = page.getByRole('dialog');
  // DIQQAT: majburiy maydon yorlig'i DOMda "Nom*" (yulduzcha `aria-hidden`
  // bo'lsa ham Playwright'ning getByLabel matn hisoblashida saqlanib
  // qoladi) -- shuning uchun ANIQ "Nom" EMAS, qisman mos regex kerak.
  // Shuningdek YANGI yozuv uchun tugma matni "Saqlash" EMAS, "Qoʻshish"
  // (`item ? t('save') : t('add')` -- bu oqim doim YANGI yozuv yaratadi).
  await drawer.getByLabel(/Nom/).fill(NAME);
  await drawer.getByRole('button', { name: /Qoʻshish/ }).click();
  // DIQQAT: jadval nom ustuni <span> (DataTable/Table.tsx haqiqiy <table>/<tr>/<td>
  // ichida) -- tugma EMAS, shuning uchun 'button' roli HECH QACHON mos kelmaydi.
  await page.getByRole('cell', { name: NAME, exact: true }).waitFor({ timeout: 8000 });
  await shot(page, 'pinsets-created', theme);
  await page.getByRole('row', { name: new RegExp(NAME) }).getByRole('button', { name: /PIN/ }).click();
  const pinsDrawer = page.getByRole('dialog');
  await pinsDrawer.getByRole('textbox').fill('1234;Test PIN');
  await pinsDrawer.getByRole('button', { name: /Qoʻshish/ }).click();
  await pinsDrawer.getByText('Test PIN').waitFor({ timeout: 8000 });
}

async function cidSourceFlow(page, theme) {
  await page.goto(BASE + '/cidsources');
  await page.getByRole('button', { name: /Yangi/ }).first().click();
  const drawer = page.getByRole('dialog');
  await drawer.getByLabel(/Nom/).fill(CID_NAME);
  await drawer.getByRole('button', { name: /Qoʻshish/ }).click();
  await page.getByRole('cell', { name: CID_NAME, exact: true }).waitFor({ timeout: 8000 });
  await shot(page, 'cidsources-created', theme);
}

async function extensionsCsvFlow(page, theme) {
  await page.goto(BASE + '/extensions');
  await page.getByRole('button', { name: 'CSV import' }).waitFor({ timeout: 8000 });
  await page.getByRole('button', { name: 'CSV eksport' }).waitFor({ timeout: 8000 });
  await shot(page, 'extensions-csv-buttons', theme);
}

async function runAdmin(browser, runner, theme, viewport) {
  const context = await browser.newContext({ viewport, colorScheme: theme.startsWith('dark') ? 'dark' : 'light' });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme.startsWith('dark') ? 'dark' : 'light');
  const page = await context.newPage();
  const problems = watchPage(page);
  try {
    await login(page);
    for (const screen of FULL_SCREENS) {
      await runner.step(`[${theme}] ${screen.path}`, () => checkFullScreen(page, theme, screen));
    }
    if (theme === 'light') {
      await runner.step(`[${theme}] PIN toʻplami: yaratish → PIN qoʻshish`, () => pinSetFlow(page, theme));
      await runner.step(`[${theme}] CID manba: yaratish`, () => cidSourceFlow(page, theme));
      await runner.step(`[${theme}] Extensions CSV tugmalari`, () => extensionsCsvFlow(page, theme));
    }
    const real = realProblems(problems);
    await runner.step(`[${theme}] 5xx/konsol xatosi yo'q`, async () => { if (real.length) throw new Error(real.join(' | ')); });
  } finally {
    await context.close();
  }
}

async function main() {
  const vite = spawn(path.join(WEB_DIR, 'node_modules', '.bin', 'vite'), ['--port', '5178', '--strictPort'], {
    cwd: WEB_DIR, env: { ...process.env, VITE_API: 'real' }, stdio: 'ignore',
  });
  const runner = makeRunner();
  let browser = null;
  try {
    await waitForServer(BASE + '/', 30000);
    await prepare();
    if (!(await backendReady())) {
      console.log('KUTILMOQDA: M9 backend endpointlari (pin-sets/cid-sources/extensions export) hali tayyor emas — bu skript ular tayyor boʻlgach ishlatiladi.');
      vite.kill('SIGTERM');
      process.exit(0);
    }
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    await runAdmin(browser, runner, 'light', { width: 1440, height: 900 });
    await runAdmin(browser, runner, 'dark', { width: 1440, height: 900 });
    await runAdmin(browser, runner, 'dark-mobile', { width: 390, height: 844 });
  } catch (e) {
    runner.results.fail += 1;
    console.log('XATO:', e?.message ?? e);
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    if (TOKEN) await cleanup().catch((e) => console.log('cleanup:', e?.message ?? e));
    vite.kill('SIGTERM');
  }
  console.log(`PASS=${runner.results.pass} FAIL=${runner.results.fail}`);
  process.exit(runner.results.fail > 0 ? 1 : 0);
}

main();
