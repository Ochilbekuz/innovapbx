// M6 UI'ni HAQIQIY API bilan tekshiradi (S18 kampaniyalar):
// admin -> /campaigns: ro'yxat (m6-proof natijalari), yangi kampaniya formasi (audio, «1» → ichki raqam, kunlar),
// yaratilgach karta ochiladi; CSV oldindan ko'rish (takror/yaroqsiz) -> Yuklash -> natija qatori, kontaktlar;
// boshlash (oyna tashqarisida — hech kim terilmaydi) -> pauza -> to'xtatish tasdig'i; tugagan kampaniya kartasi.
// DARK va mobil — ko'rinish. 5xx/konsol xatosi — FAIL. Sinov kampaniyasi oxirida API orqali o'chiriladi.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m6-real-check.mjs (stek 127.0.0.1:8710 da ishlab turgan bo'lsin).
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
const NAME = 'M6 RC — noyabr eslatmasi';
let TARGET = '';
// Oyna hozirgi Toshkent vaqtidan uzoqda — boshlangan kampaniya hech kimga qo'ng'iroq qilmaydi.
const WINDOW = (() => {
  const h = (new Date().getUTCHours() + 5 + 12) % 24;
  const pad = (n) => String(n).padStart(2, '0');
  return [`${pad(h)}:00`, `${pad((h + 1) % 24)}:00`];
})();
const CSV = ['raqam;ism', '998901110001;Aziz', '998901110002;Dilnoza', '+998 90 111-00-03;Sardor', '998901110001;Takror', 'abc;Xato'].join('\n');
let TOKEN = '';

async function api(method, p, body) {
  const r = await fetch(API + p, {
    method,
    headers: { 'Content-Type': 'application/json', ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, json: text ? JSON.parse(text) : null };
}

function adminPassword() {
  if (process.env.PROOF_ADMIN_PASSWORD) return process.env.PROOF_ADMIN_PASSWORD;
  const env = readFileSync(new URL('../../deploy/.env', import.meta.url), 'utf8');
  return env.match(/^PROOF_ADMIN_PASSWORD=(.+)$/m)[1].trim();
}

/** Oldingi yugurishdan qolgan sinov kampaniyasi bo'lsa — to'xtatib o'chiradi. */
async function cleanup() {
  const list = await api('GET', '/campaigns');
  for (const c of (list.json?.items ?? []).filter((x) => x.name === NAME)) {
    if (c.status === 'running') await api('POST', `/campaigns/${c.id}/stop`);
    const r = await api('DELETE', `/campaigns/${c.id}`);
    if (r.status !== 204) throw new Error(`cleanup ${c.id}: ${r.status}`);
  }
}

async function prepare() {
  const r = await api('POST', '/auth/login', { login: 'admin', password: adminPassword() });
  TOKEN = r.json?.access ?? '';
  if (!TOKEN) throw new Error(`admin API login: ${r.status}`);
  await cleanup();
  TARGET = (await api('GET', '/extensions')).json?.items?.[0]?.number ?? '';
  if (!TARGET) throw new Error('ichki raqam yoʻq — «1» ulash manzili kerak');
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
  await delay(1500);
  await page.screenshot({ path: path.join(SHOTS, `m6-${name}-${theme}.png`) });
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

async function gotoCampaigns(page) {
  await page.goto(BASE + '/campaigns');
  await page.getByRole('button', { name: 'M6 Avto', exact: true }).waitFor({ timeout: 10000 });
}

async function expectToast(page, text) {
  await page.getByText(text, { exact: true }).first().waitFor({ timeout: 8000 });
}

async function fillForm(page, theme) {
  await page.getByRole('button', { name: 'Yangi kampaniya' }).first().click();
  const form = page.getByRole('dialog');
  await form.getByLabel(/Nomi/).fill(NAME);
  await form.getByRole('combobox', { name: /Audio xabar/ }).click();
  await page.getByRole('option', { name: 'Salomlashuv (tizim)' }).click();
  await form.getByRole('switch', { name: /«1» — operatorga ulash/ }).click();
  await form.getByLabel(/Kimga ulanadi/).fill(TARGET);
  await form.getByLabel('Boshlanishi').fill(WINDOW[0]);
  await form.getByLabel('Tugashi').fill(WINDOW[1]);
  await form.getByRole('button', { name: 'Ya', exact: true }).click();
  await shot(page, 'form', theme);
  await form.getByRole('button', { name: 'Yaratish' }).click();
  await expectToast(page, 'Kampaniya yaratildi — endi raqamlarni yuklang');
}

async function importCsv(page, theme) {
  const card = page.getByRole('dialog', { name: NAME });
  await card.waitFor({ timeout: 8000 });
  if (!(await card.getByRole('button', { name: 'Boshlash' }).isDisabled())) throw new Error("bo'sh kampaniyada «Boshlash» faol");
  await card.getByRole('textbox', { name: 'Raqamlarni yuklash' }).fill(CSV);
  await card.getByText('3 ta yangi raqam · 1 takror · 1 yaroqsiz').waitFor({ timeout: 4000 });
  await card.getByText('6-qator: «abc»').waitFor({ timeout: 4000 });
  await shot(page, 'import-preview', theme);
  await card.getByRole('button', { name: 'Yuklash' }).click();
  await card.getByText('3 ta qoʻshildi · 0 oʻtkazildi · 1 takror · 1 yaroqsiz').waitFor({ timeout: 8000 });
  await card.getByText('998901110003').waitFor({ timeout: 8000 });
  const saved = (await api('GET', '/campaigns')).json.items.find((c) => c.name === NAME);
  if (saved?.stats.total !== 3 || saved.target_number !== TARGET || !saved.dtmf_connect || !saved.days.includes(7)) {
    throw new Error(`API'dagi kampaniya mos emas: ${JSON.stringify(saved)}`);
  }
  return card;
}

async function runLifecycle(page, card, theme) {
  await card.getByRole('button', { name: 'Boshlash' }).click();
  await expectToast(page, `«${NAME}» boshlandi`);
  await card.getByText('Ishlayapti').first().waitFor({ timeout: 8000 });
  await shot(page, 'running', theme);
  await card.getByRole('button', { name: 'Pauza' }).click();
  await expectToast(page, `«${NAME}» pauzaga qoʻyildi`);
  await card.getByRole('button', { name: 'Davom ettirish' }).waitFor({ timeout: 8000 });
  await card.getByRole('button', { name: 'Toʻxtatish' }).click();
  const confirm = page.getByRole('dialog', { name: `«${NAME}» toʻxtatilsinmi?` });
  await confirm.getByRole('button', { name: 'Toʻxtatish' }).click();
  await expectToast(page, `«${NAME}» toʻxtatildi`);
  await card.getByText('Tugagan kampaniyaga raqam qoʻshilmaydi — yangisini yarating.').waitFor({ timeout: 8000 });
  const after = (await api('GET', '/campaigns')).json.items.find((c) => c.name === NAME);
  const s = after.stats;
  if (after.status !== 'stopped' || s.done + s.failed > 0 || s.pending + s.retry > 0 || s.skipped !== 3) {
    throw new Error(`holat: ${after.status} ${JSON.stringify(s)}`);
  }
  await card.getByText('Kampaniya toʻxtatildi').first().waitFor({ timeout: 8000 });
}

async function viewCompleted(page, theme) {
  await page.getByRole('button', { name: 'M6 Avto', exact: true }).click();
  const card = page.getByRole('dialog', { name: 'M6 Avto' });
  await card.getByText('Bajarildi').first().waitFor({ timeout: 8000 });
  await shot(page, 'completed', theme);
  await page.keyboard.press('Escape');
}

async function runAdmin(browser, runner, theme, viewport) {
  const context = await browser.newContext({ viewport, colorScheme: theme.startsWith('dark') ? 'dark' : 'light' });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme.startsWith('dark') ? 'dark' : 'light');
  const page = await context.newPage();
  const problems = watchPage(page);
  try {
    await login(page);
    await runner.step(`[${theme}] ro'yxat`, async () => { await gotoCampaigns(page); await shot(page, 'list', theme); });
    if (theme === 'light') {
      await runner.step(`[${theme}] yaratish formasi`, () => fillForm(page, theme));
      let card = null;
      await runner.step(`[${theme}] CSV import`, async () => { card = await importCsv(page, theme); });
      await runner.step(`[${theme}] boshlash → pauza → to'xtatish`, () => runLifecycle(page, card, theme));
      await page.getByRole('dialog', { name: NAME }).getByRole('button', { name: 'Yopish', exact: true }).last().click();
    }
    await runner.step(`[${theme}] tugagan kampaniya kartasi`, () => viewCompleted(page, theme));
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
