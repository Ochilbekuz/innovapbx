// M5a sahifasini HAQIQIY API bilan tekshiradi (contract §3, §4, §5): admin -> /settings/migration.
// Toʻplam yuklash -> tahlil -> koʻrib chiqish (toʻqnashuv/zaif sir) -> "KOCHIRISH" bilan qoʻllash ->
// natija -> tarix. Tahlildan keyin API orqali to'qnashuvchi ichki raqam yaratiladi -> haqiqiy `plan_stale` 409
// -> qayta tahlil -> qoʻllash. SSH: yetib bo'lmaydigan host -> «Ulanmadi» xabari (5xx emas).
// Operator uchun /settings/migration koʻrinmaydi. LIGHT to'liq, DARK/mobil — koʻrinish. 5xx/konsol xatosi — FAIL.
// Ishga tushirish: toza stek (masalan `scripts/m0-proof.sh --fresh` dan keyin), so'ng
// CHROME_PATH=... node web/scripts/m5a-real-check.mjs. Kanonik fixture: tests/freepbx-fixture/bundle/.
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const execFileP = promisify(execFile);
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const WEB_DIR = path.join(ROOT, '..');
const SHOTS = path.join(ROOT, '..', '..', 'replica', 'clone-screens');
const BASE = 'http://127.0.0.1:5176';
const API = 'http://127.0.0.1:8710/api/v1';
const UPLOAD_BUNDLE = path.join(ROOT, '..', '..', 'tests', 'freepbx-fixture', 'bundle', 'fpbx-export-fixture.tar.gz');
const OPERATOR = { username: 'm5a_rc_op', password: 'M5aRcOperator!2026' };
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

/** Tayyorlov (API): admin token, zaxira paroli (apply sharti), qo'lda 101 (to'qnashuv), operator. */
async function prepare() {
  const r = await api('POST', '/auth/login', { login: 'admin', password: adminPassword() });
  TOKEN = r.json?.access ?? '';
  if (!TOKEN) throw new Error(`admin API login: ${r.status}`);
  const pj = await api('PUT', '/settings/backup/passphrase', { passphrase: 'M5aRealCheck!Zaxira2026' });
  if (pj.status >= 300) throw new Error(`passphrase: ${pj.status}`);
  const ext = await api('POST', '/extensions', { number: '101', name: 'Qolda 101' });
  if (![201, 409].includes(ext.status)) throw new Error(`ext 101: ${ext.status}`);
  const op = await api('POST', '/users', { ...OPERATOR, full_name: 'M5a RC Op', role: 'operator' });
  if (![201, 409].includes(op.status)) throw new Error(`operator: ${op.status}`);
}

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

async function shot(page, name, theme) {
  await delay(400);
  await page.screenshot({ path: path.join(SHOTS, `m5a-${name}-${theme}.png`) });
}

async function sh(cmd, args) {
  const { stdout } = await execFileP(cmd, args, { maxBuffer: 10 * 1024 * 1024 });
  return stdout;
}

// ------------------------------------------------------------ yordamchi: bosqich hisoblagich
function makeRunner() {
  const results = { pass: 0, fail: 0 };
  const step = async (label, fn) => {
    try {
      await fn();
      results.pass += 1;
      console.log(`OK: ${label}`);
    } catch (e) {
      results.fail += 1;
      console.log(`FAIL: ${label}: ${e?.message ?? e}`);
    }
  };
  return { results, step };
}

async function gotoMigrationPage(page) {
  await page.goto(BASE + '/settings/migration');
  await page.getByTestId('migration-page').waitFor({ timeout: 45000 });
}

async function login(page, login_, password) {
  await page.goto(BASE + '/login');
  await page.getByLabel('Login').fill(login_);
  await page.getByLabel('Parol').fill(password);
  await page.getByRole('button', { name: 'Kirish' }).click();
}

// ------------------------------------------------------------ "Toʻplam yuklash" orqali toʻliq oqim
async function startNewImportIfNeeded(page) {
  const newImportBtn = page.getByRole('button', { name: 'Yangi import boshlash' });
  if (await newImportBtn.isVisible().catch(() => false)) await newImportBtn.click();
}

async function checkUploadAndAnalyze(page, theme) {
  await page.getByTestId('migration-source-step').waitFor({ timeout: 10000 });
  await page.getByRole('tab', { name: 'Toʻplam yuklash' }).click();
  await shot(page, 'source-upload', theme);
  await page.getByLabel(/Toʻplam fayli/).setInputFiles(UPLOAD_BUNDLE);
  await page.getByRole('button', { name: /Yuklash va tahlilga/ }).click();
  await page.getByTestId('migration-analyze-step').waitFor({ timeout: 10000 });
  await page.getByRole('button', { name: 'Tahlilni boshlash' }).click();
  await shot(page, 'analyzing', theme);
  await page.getByTestId('migration-review-step').waitFor({ timeout: 60000 });
}

async function checkReview(page, theme) {
  await page.getByText("Toʻqnashuv").first().waitFor({ timeout: 10000 });
  await shot(page, 'review', theme);
  await page.getByRole('button', { name: /Qoʻllashga oʻtish/ }).click();
}

/** Tahlildan KEYIN boshqa admin 103 ni qo'lda yaratdi -> saqlangan reja eskirdi -> 409 plan_stale. */
async function checkPlanStaleRecovery(page, theme) {
  await page.getByTestId('migration-apply-step').waitFor({ timeout: 10000 });
  const ext = await api('POST', '/extensions', { number: '103', name: 'Qolda 103' });
  if (ext.status !== 201) throw new Error(`ext 103: ${ext.status}`);
  await page.getByLabel('Tasdiqlash uchun quyidagi soʻzni yozing').fill('KOCHIRISH');
  await page.getByRole('button', { name: /^Qoʻllash$/ }).click();
  await page.getByText('qayta tahlil qilish kerak').waitFor({ timeout: 10000 });
  await shot(page, 'plan-stale', theme);
  await page.getByRole('button', { name: 'Qayta tahlil qilish' }).click();
  await page.getByTestId('migration-review-step').waitFor({ timeout: 30000 });
  await page.getByRole('button', { name: /Qoʻllashga oʻtish/ }).click();
}

async function checkApplyAndResult(page, theme) {
  await page.getByTestId('migration-apply-step').waitFor({ timeout: 10000 });
  await shot(page, 'apply', theme);
  await page.getByLabel('Tasdiqlash uchun quyidagi soʻzni yozing').fill('KOCHIRISH');
  await page.getByRole('button', { name: /^Qoʻllash$/ }).click();
  await shot(page, 'applying', theme);
  await page.getByTestId('migration-result-step').waitFor({ timeout: 120000 });
  await page.getByText('Koʻchirish yakunlandi').waitFor({ timeout: 10000 });
  await shot(page, 'result', theme);
  const ext = await api('GET', '/extensions?size=200');
  const items = ext.json?.items ?? [];
  const missing = ['101', '102', '103', '105', '106', '107'].filter((n) => !items.some((e) => e.number === n));
  if (missing.length) throw new Error(`import qilinmagan: ${missing.join(',')}`);
  const manual = items.find((e) => e.number === '103');
  if (manual?.name !== 'Qolda 103') throw new Error(`qo'lda 103 ustidan yozildi: ${manual?.name}`);
}

async function checkHistoryTable(page, theme) {
  await page.getByText('Koʻchirish tarixi').waitFor({ timeout: 10000 });
  await page.getByRole('row').first().waitFor({ timeout: 10000 });
  await shot(page, 'history', theme);
}

// ------------------------------------------------------------ SSH: yetib bo'lmaydigan host -> xabar
async function checkSshUnreachable(page, theme) {
  await startNewImportIfNeeded(page);
  await page.getByTestId('migration-source-step').waitFor({ timeout: 10000 });
  await page.getByRole('tab', { name: 'SSH orqali olish' }).click();
  await page.getByLabel('Host').fill('127.0.0.1');
  await page.getByLabel('Foydalanuvchi', { exact: true }).fill('root');
  await page.getByLabel('Parol', { exact: true }).fill('sekret-parol');
  await shot(page, 'source-ssh', theme);
  await page.getByRole('button', { name: 'Ulanishni tekshirish' }).click();
  await page.getByText(/Ulanmadi:/).waitFor({ timeout: 30000 });
  await shot(page, 'ssh-failed', theme);
}

// ------------------------------------------------------------ operator uchun koʻrinmaslik
async function checkOperatorBlocked(page) {
  await page.context().clearCookies();
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
  await login(page, OPERATOR.username, OPERATOR.password);
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 10000 });
  await page.goto(BASE + '/settings/migration');
  await delay(2500);
  if (await page.getByTestId('migration-page').isVisible().catch(() => false)) {
    throw new Error('operator /settings/migration sahifasini koʻrdi');
  }
  if (new URL(page.url()).pathname.startsWith('/settings/migration')) {
    throw new Error(`operator yoʻnaltirilmadi: ${page.url()}`);
  }
}

// ------------------------------------------------------------ bitta mavzu (light/dark) uchun to'liq o'tish
async function runTheme(browser, runner) {
  const theme = 'light';
  const { step } = runner;

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme);
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e}`));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    if (/favicon/i.test(m.text()) || /^Failed to load resource:/.test(m.text())) return;
    consoleErrors.push(`console.error: ${m.text()}`);
  });
  page.on('response', (r) => {
    if (!r.url().includes('/api/') || r.status() < 500) return;
    consoleErrors.push(`${r.status()} ${r.url()}`);
  });

  try {
    await step(`[${theme}] kirish`, async () => {
      await login(page, 'admin', adminPassword());
      await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    });
    await step(`[${theme}] /settings/migration ochildi`, async () => {
      await gotoMigrationPage(page);
      await shot(page, 'overview', theme);
    });
    await step(`[${theme}] toʻplam yuklash + tahlil`, () => checkUploadAndAnalyze(page, theme));
    await step(`[${theme}] koʻrib chiqish (101 toʻqnashuv)`, () => checkReview(page, theme));
    await step(`[${theme}] "plan_stale" 409 -> qayta tahlil`, () => checkPlanStaleRecovery(page, theme));
    await step(`[${theme}] "KOCHIRISH" bilan qoʻllash + natija (6 ichki raqam)`, () => checkApplyAndResult(page, theme));
    await step(`[${theme}] koʻchirish tarixi jadvali`, () => checkHistoryTable(page, theme));
    await step(`[${theme}] SSH yetib boʻlmaydi -> «Ulanmadi»`, () => checkSshUnreachable(page, theme));
    await step(`[${theme}] operator uchun koʻrinmaydi (/me)`, () => checkOperatorBlocked(page));
    await step(`[${theme}] konsol/5xx xatolari yoʻq`, async () => {
      if (consoleErrors.length) throw new Error(consoleErrors.join(' | '));
    });
  } finally {
    await context.close();
  }
}

/** Ikkinchi (dark) mavzuda — faqat koʻrinishni tekshirish, yon taʼsirli amallarni qaytarmaydi. */
async function runDarkThemeOverview(browser, runner) {
  const theme = 'dark';
  const { step } = runner;
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme);
  const page = await context.newPage();
  try {
    await step(`[${theme}] kirish + /settings/migration koʻrinishi`, async () => {
      await login(page, 'admin', adminPassword());
      await page.waitForURL(/\/dashboard/, { timeout: 10000 });
      await gotoMigrationPage(page);
      await shot(page, 'overview', theme);
    });
  } finally {
    await context.close();
  }
}

/** Mobil 390px — faqat sehrgar manba bosqichi koʻrinishini tekshiradi (contract: mobil ishlashi shart). */
async function runMobileOverview(browser, runner) {
  const theme = 'light-mobile';
  const { step } = runner;
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  try {
    await step(`[${theme}] 390px — /settings/migration koʻrinishi`, async () => {
      await login(page, 'admin', adminPassword());
      await page.waitForURL(/\/dashboard/, { timeout: 10000 });
      await gotoMigrationPage(page);
      await shot(page, 'overview', theme);
    });
  } finally {
    await context.close();
  }
}

async function main() {
  const vite = spawn(path.join(WEB_DIR, 'node_modules', '.bin', 'vite'), ['--port', '5176', '--strictPort'], {
    cwd: WEB_DIR, env: { ...process.env, VITE_API: 'real' }, stdio: 'ignore',
  });
  const runner = makeRunner();
  let browser = null;
  try {
    await waitForServer(BASE + '/', 30000);
    await prepare();
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    await runTheme(browser, runner);
    await runDarkThemeOverview(browser, runner);
    await runMobileOverview(browser, runner);
  } catch (e) {
    runner.results.fail += 1;
    console.log('XATO:', e?.message ?? e);
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    vite.kill('SIGTERM');
  }
  console.log(`PASS=${runner.results.pass} FAIL=${runner.results.fail}`);
  process.exit(runner.results.fail > 0 ? 1 : 0);
}

main();
