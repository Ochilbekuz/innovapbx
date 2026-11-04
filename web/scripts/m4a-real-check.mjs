// M4a sahifasini HAQIQIY API bilan tekshiradi (contract §5.7): admin -> /devices.
// Proof tarmog'idagi «apparat» (python konteyner, haqiqiy Yealink UA bilan) noma'lum MAC'dan config so'raydi ->
// «Topilgan qurilmalar» bannerida chiqadi -> UI orqali 104 ga biriktirish -> BLF tugmasini tahrirlash (102) ->
// config'ni ko'rish (parol `***`, ochiq parol YO'Q, BLF qatorlari bor) -> qayta sozlash (ro'yxatda bo'lmagani uchun 409 toast,
// 5xx emas) -> Sozlamalar va Jurnal tablari. Hammasi LIGHT va DARK mavzuda. 5xx/konsol xatosi — FAIL.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m4a-real-check.mjs (stek ko'tarilgan, m4a-proof o'tgan bo'lsin —
// u `allowed_networks` ni proof quyi tarmog'iga cheklaydi, apparat konteyneri shu tarmoqdan so'raydi).
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
const PG_CONTAINER = 'innova-m0-postgres-1';
const NET = 'innova-m0_innova-net';
const PHONE = 'm4a-check-phone';
const PHONE_IP = '172.28.0.238';
const TARGET_EXT = '105'; // 104 da m4a-proof max_contacts (3) ni to'ldirib qo'ygan
const BLF_EXT = '102';

// Har mavzu uchun alohida MAC (run'lar orasida takrorlanmasin — oxirgi 4 hex vaqtdan).
const RUN_HEX = (Date.now() % 0xffff).toString(16).padStart(4, '0');
// MAC — 12 hex, ajratgichsiz (API/UI shu shaklda; `macaddr` ustuni ham qabul qiladi).
const macFor = (theme) => `805ec0${theme === 'light' ? 'c1' : 'd2'}${RUN_HEX}`;
const uaFor = (mac) => `Yealink SIP-T46S 66.86.0.15 ${mac.match(/../g).join(':')}`;

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
  await page.screenshot({ path: path.join(SHOTS, `m4a-${name}-${theme}.png`) });
}

async function sh(cmd, args) {
  const { stdout } = await execFileP(cmd, args, { maxBuffer: 10 * 1024 * 1024 });
  return stdout;
}

async function psql(sql) {
  const out = await sh('docker', ['exec', PG_CONTAINER, 'psql', '-U', 'innova', '-d', 'innova', '-tAc', sql]);
  return out.split('\n')[0].trim();
}

// ------------------------------------------------------------ API (faqat tayyorgarlik: token va parol uchun)
async function apiToken() {
  const r = await fetch(`${API}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login: 'admin', password: adminPassword() }),
  });
  return (await r.json()).access;
}

async function provToken(token) {
  const r = await fetch(`${API}/settings/provisioning`, { headers: { Authorization: `Bearer ${token}` } });
  const url = (await r.json()).url;
  return url.match(/\/prov\/([0-9a-f]{32})\//)[1];
}

/** Ichki raqam parolini (config'da ochiq bo'lmasligi kerak bo'lgan sir) DB'dan o'qiydi. */
async function extensionSecret(number) {
  return psql(`select password from ps_auths where id like '%-${number}' limit 1;`)
    .catch(() => '');
}

// ------------------------------------------------------------ «apparat» konteyneri
async function startPhone() {
  await sh('docker', ['rm', '-f', PHONE]).catch(() => undefined);
  await sh('docker', ['run', '-d', '--name', PHONE, '--network', NET, '--ip', PHONE_IP, 'python:3.12-slim', 'sleep', 'infinity']);
}

async function stopPhone() {
  await sh('docker', ['rm', '-f', PHONE]).catch(() => undefined);
}

/** Apparat sifatida `web` nginx orqali config so'raydi -> HTTP kod. */
async function phoneFetch(token, file, ua) {
  const code = `import urllib.request,urllib.error
r=urllib.request.Request('http://web/prov/${token}/${file}',headers={'User-Agent':${JSON.stringify(ua)}})
try: print(urllib.request.urlopen(r,timeout=10).status)
except urllib.error.HTTPError as e: print(e.code)`;
  return Number((await sh('docker', ['exec', PHONE, 'python3', '-c', code])).trim());
}

async function cleanupDevice(mac) {
  await psql(`delete from device_keys where device_id in (select id from devices where mac = '${mac}');`).catch(() => undefined);
  await psql(`delete from devices where mac = '${mac}';`).catch((e) => console.log('TOZALASH XATO (devices):', e.message));
  await psql(`delete from discovered_devices where mac = '${mac}';`).catch(() => undefined);
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

async function pickOption(page, combobox, optionName) {
  await combobox.click();
  await page.getByRole('option', { name: optionName }).first().click();
}

// ------------------------------------------------------------ tekshiruvlar
async function checkDiscoveredAssign(page, theme, mac) {
  await page.getByText(/Topilgan qurilmalar: \d+ ta/).waitFor({ timeout: 10000 });
  const row = page.locator('div.rounded-md').filter({ hasText: mac })
    .filter({ has: page.getByRole('button', { name: 'Raqamga biriktirish' }) });
  await row.waitFor({ timeout: 10000 });
  await shot(page, 'discovered', theme);
  await row.getByRole('button', { name: 'Raqamga biriktirish' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText('Qurilmani ichki raqamga biriktirish').waitFor({ timeout: 10000 });
  await pickOption(page, dialog.getByRole('combobox').first(), new RegExp(`^${TARGET_EXT}\\b`));
  await dialog.getByRole('textbox').last().fill(`Sinov ${theme}`);
  await shot(page, 'assign-modal', theme);
  await dialog.getByRole('button', { name: 'Raqamga biriktirish' }).click();
  await page.getByText('Qurilma biriktirildi.').first().waitFor({ timeout: 10000 });
  await dialog.waitFor({ state: 'detached', timeout: 10000 });
  const dev = await psql(`select e.number from devices d join extensions e on e.id = d.extension_id where d.mac = '${mac}';`);
  if (dev !== TARGET_EXT) throw new Error(`devices yozuvi kutilmagan: '${dev}'`);
}

/** Jadval 8 qatordan sahifalanadi — avval MAC bo'yicha qidiruv. */
async function searchTable(page, mac) {
  const box = page.getByRole('searchbox').last();
  await box.fill('');
  await box.fill(mac);
}

function deviceRow(page, mac) {
  return page.getByRole('row').filter({ hasText: mac }).filter({ has: page.getByRole('button', { name: 'Tugmalar' }) });
}

async function checkKeys(page, theme, mac) {
  await searchTable(page, mac);
  const row = deviceRow(page, mac);
  await row.getByRole('button', { name: 'Tugmalar' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText(/dastur tugmasini qoʻllaydi/).waitFor({ timeout: 10000 });
  await dialog.getByRole('button', { name: 'Tugma qoʻshish' }).click();
  await dialog.getByPlaceholder('Raqam').last().fill(BLF_EXT);
  await dialog.getByPlaceholder('Yorliq').last().fill('Hamkasb');
  await shot(page, 'keys', theme);
  await dialog.getByRole('button', { name: 'Saqlash' }).click();
  await page.getByText('Tugmalar saqlandi.').first().waitFor({ timeout: 10000 });
  const k = await psql(
    `select k.type || '|' || k.value from device_keys k join devices d on d.id = k.device_id where d.mac = '${mac}' order by k.idx limit 1;`,
  );
  if (k !== `blf|${BLF_EXT}`) throw new Error(`device_keys kutilmagan: '${k}'`);
}

async function checkConfig(page, theme, mac, secret) {
  const row = deviceRow(page, mac);
  const [resp] = await Promise.all([
    page.waitForResponse((r) => /\/devices\/[^/]+\/config/.test(r.url()), { timeout: 10000 }),
    row.getByRole('button', { name: 'Config' }).click(),
  ]);
  const body = await resp.text();
  if (resp.status() !== 200) throw new Error(`config javobi ${resp.status()}`);
  if (secret && body.includes(secret)) throw new Error('config javobida OCHIQ parol bor');
  const dialog = page.getByRole('dialog');
  const pre = dialog.locator('pre');
  await pre.getByText(/account\.1\.password = \*\*\*/).waitFor({ timeout: 10000 });
  const text = await pre.textContent();
  if (!/linekey\.1\.type = 16/.test(text) || !new RegExp(`linekey\\.1\\.value = ${BLF_EXT}`).test(text)) {
    throw new Error('config ko‘rinishida BLF qatorlari yo‘q');
  }
  await shot(page, 'config', theme);
  await dialog.getByRole('button', { name: 'Yopish' }).last().click();
  await dialog.waitFor({ state: 'detached', timeout: 10000 });
}

async function checkResync(page, mac) {
  const row = deviceRow(page, mac);
  const [resp] = await Promise.all([
    page.waitForResponse((r) => /\/devices\/[^/]+\/resync/.test(r.url()), { timeout: 10000 }),
    row.getByRole('button', { name: 'Qayta sozlash' }).click(),
  ]);
  // Apparat SIP'da ro'yxatdan o'tmagan — kontrakt bo'yicha 409 `not_registered` va xato toast'i.
  if (resp.status() !== 409) throw new Error(`resync javobi ${resp.status()} (409 kutilgan)`);
  await page.getByText('Qayta sozlab boʻlmadi.').first().waitFor({ timeout: 10000 });
}

async function checkProvisioningCard(page) {
  await page.getByText('Provizioning manzili').first().waitFor({ timeout: 10000 });
  const url = await page.getByLabel('Provizioning URL').inputValue();
  if (!/\/prov\/\*{3}|\/prov\/[0-9a-f]{32}\//.test(url)) throw new Error(`provizioning URL kutilmagan: ${url}`);
}

async function checkSettingsTab(page, theme) {
  await page.getByRole('tab', { name: 'Sozlamalar' }).click();
  await page.getByText('Provizioning sozlamalari').first().waitFor({ timeout: 10000 });
  await page.getByText('Parol saqlangan — oʻzgartirish uchun qayta kiriting.').first().waitFor({ timeout: 10000 });
  await shot(page, 'settings', theme);
}

async function checkLogTab(page, theme, mac) {
  await page.getByRole('tab', { name: 'Jurnal' }).click();
  await page.getByText('Provizioning jurnali').first().waitFor({ timeout: 10000 });
  await searchTable(page, mac);
  await page.getByRole('row').filter({ hasText: mac }).first().waitFor({ timeout: 10000 });
  const tableText = await page.locator('table').last().textContent();
  if (/\/prov\/[0-9a-f]{32}/.test(tableText)) throw new Error('jurnalda ochiq token bor');
  await shot(page, 'log', theme);
  await page.getByRole('tab', { name: 'Apparatlar' }).click();
}

// ------------------------------------------------------------ bitta mavzu (light/dark) uchun to'liq o'tish
async function runTheme(browser, runner, { theme, token, secret }) {
  const mac = macFor(theme);
  const { step } = runner;
  await cleanupDevice(mac);

  await step(`[${theme}] apparat noma'lum MAC'dan so'radi -> 404 (topilganlarga yozildi)`, async () => {
    const code = await phoneFetch(token, `${mac}.cfg`, uaFor(mac));
    if (code !== 404) throw new Error(`kutilgan 404, keldi ${code}`);
  });

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme);
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e}`));
  // 4xx (resync 409) — ataylab tekshirilayotgan yo'l; brauzerning avtomatik «Failed to load resource» yozuvi hisoblanmaydi.
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    if (/favicon/i.test(m.text()) || /^Failed to load resource:/.test(m.text())) return;
    consoleErrors.push(`console.error: ${m.text()}`);
  });
  page.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 500) consoleErrors.push(`${r.status()} ${r.url()}`); });

  try {
    await step(`[${theme}] kirish`, async () => {
      await page.goto(BASE + '/login');
      await page.getByLabel('Login').fill('admin');
      await page.getByLabel('Parol').fill(adminPassword());
      await page.getByRole('button', { name: 'Kirish' }).click();
      await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    });
    await step(`[${theme}] /devices ochildi + provizioning kartasi`, async () => {
      await page.goto(BASE + '/devices');
      // birinchi ochilishda vite sahifa modullarini kompilyatsiya qiladi — 10 s yetmasligi mumkin
      await page.getByTestId('devices-page').waitFor({ timeout: 45000 });
      await checkProvisioningCard(page);
      await shot(page, 'overview', theme);
    });
    await step(`[${theme}] topilgan apparatni ${TARGET_EXT} ga biriktirish`, () => checkDiscoveredAssign(page, theme, mac));
    await step(`[${theme}] apparat endi config oladi (200)`, async () => {
      const code = await phoneFetch(token, `${mac}.cfg`, uaFor(mac));
      if (code !== 200) throw new Error(`kutilgan 200, keldi ${code}`);
    });
    await step(`[${theme}] BLF ${BLF_EXT} tugmasi`, () => checkKeys(page, theme, mac));
    await step(`[${theme}] config ko'rish (maskalangan, BLF bor)`, () => checkConfig(page, theme, mac, secret));
    await step(`[${theme}] qayta sozlash -> 409 toast`, () => checkResync(page, mac));
    await step(`[${theme}] jadval holati`, async () => {
      await page.reload();
      await page.getByTestId('devices-page').waitFor({ timeout: 10000 });
      await searchTable(page, mac);
      await deviceRow(page, mac).getByText(/Sozlandi|Yangilanishi kerak/).first().waitFor({ timeout: 10000 });
      await shot(page, 'table', theme);
    });
    await step(`[${theme}] Sozlamalar tabi`, () => checkSettingsTab(page, theme));
    await step(`[${theme}] Jurnal tabi (tokensiz)`, () => checkLogTab(page, theme, mac));
    await step(`[${theme}] konsol/5xx xatolari yo'q`, async () => {
      if (consoleErrors.length) throw new Error(consoleErrors.join(' | '));
    });
  } finally {
    await context.close();
    await cleanupDevice(mac);
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
    const token = await provToken(await apiToken());
    const secret = await extensionSecret(TARGET_EXT);
    await startPhone();
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    for (const theme of ['light', 'dark']) {
      await runTheme(browser, runner, { theme, token, secret });
    }
  } catch (e) {
    runner.results.fail += 1;
    console.log('XATO:', e?.message ?? e);
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    await stopPhone();
    vite.kill('SIGTERM');
  }
  console.log(`PASS=${runner.results.pass} FAIL=${runner.results.fail}`);
  process.exit(runner.results.fail > 0 ? 1 : 0);
}

main();
