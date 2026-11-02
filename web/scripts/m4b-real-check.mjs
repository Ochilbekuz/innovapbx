// M4b sahifasini HAQIQIY API bilan tekshiradi (contract §3, §4.8): admin -> /settings/backup.
// Zaxira parolini o'rnatish -> «Hozir zaxiralash» (progress) -> jadval/saqlash joylari sozlamalarini
// saqlash -> jadvaldan zaxirani yuklab olish -> «Fayldan tiklash»: yuklash -> parol -> inspect ->
// `TIKLASH` yozib tasdiqlash -> to'liq ekran progress -> login sahifasi «Tizim zaxiradan tiklandi». Tiklash
// tarixi jadvali ham tekshiriladi. Hammasi LIGHT va DARK mavzuda. 5xx/konsol xatosi — FAIL.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m4b-real-check.mjs (stek ko'tarilgan, m4b-proof
// o'tgan bo'lsin).
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
const PASSPHRASE = 'M4bSinovParoli987!';
// «Yuklab olish» bosqichida saqlangan HAQIQIY zaxira — «Fayldan tiklash» shu faylni yuklaydi.
const DOWNLOADED_BACKUP = '/tmp/m4b-real-check.ibk';

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
  await page.screenshot({ path: path.join(SHOTS, `m4b-${name}-${theme}.png`) });
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

async function gotoBackupPage(page) {
  await page.goto(BASE + '/settings/backup');
  await page.getByTestId('backup-page').waitFor({ timeout: 45000 });
}

// ------------------------------------------------------------ Zaxiralar tabi
async function checkSetPassphrase(page, theme) {
  await page.getByRole('tab', { name: 'Jadval va saqlash joylari' }).click();
  await page.getByText('Zaxira paroli').first().waitFor({ timeout: 10000 });
  // Qayta ishga tushirishda parol allaqachon o'rnatilgan — joriy parol (shu PASSPHRASE) ham so'raladi.
  const current = page.getByLabel('Joriy parol');
  if (await current.isVisible()) await current.fill(PASSPHRASE);
  await page.getByLabel('Yangi parol').fill(PASSPHRASE);
  await shot(page, 'passphrase', theme);
  await page.getByRole('button', { name: 'Parolni saqlash' }).click();
  await page.getByText('Zaxira paroli saqlandi.').first().waitFor({ timeout: 10000 });
  await page.getByRole('tab', { name: 'Zaxiralar' }).click();
}

async function checkCreateBackup(page, theme) {
  await page.getByRole('button', { name: 'Hozir zaxiralash' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('heading', { name: 'Zaxira yaratish' }).waitFor({ timeout: 10000 });
  await shot(page, 'create-modal', theme);
  await dialog.getByRole('button', { name: 'Boshlash' }).click();
  await page.getByText('Zaxiralash boshlandi.').first().waitFor({ timeout: 10000 });
  await shot(page, 'progress', theme);
  await page.getByText('Zaxira muvaffaqiyatli yaratildi.').first().waitFor({ timeout: 20000 });
}

function firstBackupRow(page) {
  return page.getByRole('row').filter({ has: page.getByRole('button', { name: 'Tiklash' }) }).first();
}

async function checkBackupsTable(page, theme) {
  await page.getByText('Zaxiralar roʻyxati').waitFor({ timeout: 10000 });
  const row = firstBackupRow(page);
  await row.waitFor({ timeout: 10000 });
  await shot(page, 'table', theme);
}

async function checkDownload(page) {
  const row = firstBackupRow(page);
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 10000 }),
    row.getByRole('button', { name: 'Yuklab olish' }).click(),
  ]);
  if (!download.suggestedFilename().endsWith('.ibk')) throw new Error(`kutilmagan fayl nomi: ${download.suggestedFilename()}`);
  await download.saveAs(DOWNLOADED_BACKUP);
}

// ------------------------------------------------------------ Jadval va saqlash joylari tabi
async function checkScheduleSettings(page, theme) {
  await page.getByRole('tab', { name: 'Jadval va saqlash joylari' }).click();
  await page.getByText('Avtomatik zaxira jadvali').waitFor({ timeout: 10000 });
  await shot(page, 'settings', theme);
  await page.getByRole('button', { name: 'Saqlash' }).first().click();
  await page.getByText('Saqlandi.').first().waitFor({ timeout: 10000 });
}

// ------------------------------------------------------------ Fayldan tiklash tabi
async function checkUploadInspect(page, theme) {
  await page.getByRole('tab', { name: 'Fayldan tiklash' }).click();
  await page.getByText('Mavjud zaxiradan yoki fayldan tizimni oldingi holatga qaytarish.').waitFor({ timeout: 10000 });
  await page.getByTestId('restore-upload-input').setInputFiles(DOWNLOADED_BACKUP);
  await page.getByRole('button', { name: 'Yuklash' }).click();
  await page.getByText('Fayl yuklandi.').first().waitFor({ timeout: 10000 });
  await shot(page, 'uploaded', theme);
  await page.getByLabel('Zaxira paroli').fill(PASSPHRASE);
  await page.getByRole('button', { name: 'Tekshirish' }).click();
  await page.getByText('Zaxira maʼlumotlari').waitFor({ timeout: 10000 });
  await shot(page, 'inspect', theme);
}

async function checkRestoreFlow(page, theme) {
  await page.getByRole('button', { name: 'Tiklashga oʻtish' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('heading', { name: 'Tiklashni tasdiqlaysizmi?' }).waitFor({ timeout: 10000 });
  await dialog.getByPlaceholder('TIKLASH').fill('TIKLASH');
  await shot(page, 'confirm-modal', theme);
  await dialog.getByRole('button', { name: 'Tiklash' }).click();
  await page.getByRole('heading', { name: 'Tiklanmoqda…' }).waitFor({ timeout: 10000 });
  // Real API bosqichni identifikator bilan beradi — UI tarjima qilgan matn ko'rinishi shart (xom `pre_restore_backup` emas).
  await page.getByText('Joriy holat zaxiralanmoqda').waitFor({ timeout: 10000 });
  await shot(page, 'restore-progress', theme);
  await page.waitForURL(/\/login/, { timeout: 30000 });
  await page.getByText('Tizim zaxiradan tiklandi').first().waitFor({ timeout: 10000 });
  await shot(page, 'restored-login', theme);
}

/** Tiklashdan keyingi eski sessiya amal qilmaydi — qayta kirib tarixni tekshiradi. */
async function checkRestoreHistory(page, theme) {
  await page.goto(BASE + '/login');
  await page.getByLabel('Login').fill('admin');
  await page.getByLabel('Parol').fill(adminPassword());
  await page.getByRole('button', { name: 'Kirish' }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 10000 });
  await gotoBackupPage(page);
  await page.getByRole('tab', { name: 'Fayldan tiklash' }).click();
  await page.getByRole('heading', { name: 'Tiklash tarixi' }).waitFor({ timeout: 10000 });
  await page.getByRole('row').filter({ hasText: 'Yuklangan fayldan' }).first().waitFor({ timeout: 10000 });
  await shot(page, 'restore-history', theme);
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
  // Tiklash paytidagi 503 `maintenance` — kutilgan (UI shu bilan progressni ko'rsatadi), xato emas.
  page.on('response', async (r) => {
    if (!r.url().includes('/api/') || r.status() < 500) return;
    const body = r.status() === 503 ? await r.text().catch(() => '') : '';
    if (!body.includes('"code":"maintenance"')) consoleErrors.push(`${r.status()} ${r.url()}`);
  });

  try {
    await step(`[${theme}] kirish`, async () => {
      await page.goto(BASE + '/login');
      await page.getByLabel('Login').fill('admin');
      await page.getByLabel('Parol').fill(adminPassword());
      await page.getByRole('button', { name: 'Kirish' }).click();
      await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    });
    await step(`[${theme}] /settings/backup ochildi`, async () => {
      await gotoBackupPage(page);
      await shot(page, 'overview', theme);
    });
    await step(`[${theme}] zaxira parolini oʻrnatish`, () => checkSetPassphrase(page, theme));
    await step(`[${theme}] «Hozir zaxiralash» + progress`, () => checkCreateBackup(page, theme));
    await step(`[${theme}] zaxiralar jadvali`, () => checkBackupsTable(page, theme));
    await step(`[${theme}] zaxirani yuklab olish`, () => checkDownload(page));
    await step(`[${theme}] jadval sozlamalarini saqlash`, () => checkScheduleSettings(page, theme));
    await step(`[${theme}] fayl yuklash + parol + tekshirish`, () => checkUploadInspect(page, theme));
    await step(`[${theme}] tiklash (TIKLASH) -> login`, () => checkRestoreFlow(page, theme));
    await step(`[${theme}] tiklash tarixi`, () => checkRestoreHistory(page, theme));
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
    await step(`[${theme}] kirish + /settings/backup ko'rinishi`, async () => {
      await page.goto(BASE + '/login');
      await page.getByLabel('Login').fill('admin');
      await page.getByLabel('Parol').fill(adminPassword());
      await page.getByRole('button', { name: 'Kirish' }).click();
      await page.waitForURL(/\/dashboard/, { timeout: 10000 });
      await gotoBackupPage(page);
      await shot(page, 'overview', theme);
      await page.getByRole('tab', { name: 'Jadval va saqlash joylari' }).click();
      await shot(page, 'settings', theme);
      await page.getByRole('tab', { name: 'Fayldan tiklash' }).click();
      await shot(page, 'restore-tab', theme);
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
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    // Tiklash oqimi butun stekni restart qiladi (login sahifasiga qaytaradi) — shuning uchun
    // yon taʼsirli (parol/zaxiralash/tiklash) toʻliq oqim faqat LIGHT'da, DARK'da faqat koʻrinish.
    await runTheme(browser, runner);
    await runDarkThemeOverview(browser, runner);
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
