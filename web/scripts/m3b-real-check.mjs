// M3b sahifasini HAQIQIY API bilan tekshiradi (contract §7.7, to'liq): admin -> /settings/integrations.
// API kalit yaratish/bekor qilish; vebhuk — taqiqlangan manzil 422, to'g'ri manzil bilan yaratish -> sinov ->
// yetkazishlar jurnali; Bitrix24 — webhook saqlash (maskalash + tarmoq javobida sir yo'qligi) -> ulanish
// sinovi -> umumiy tabdagi karta holati; amoCRM — xuddi shunday; 1C — 5 namuna + yuklab olish; /calls —
// yaratilgan sinov yozuvi va uni tinglash tugmasi. Hammasi LIGHT va DARK mavzuda. 5xx/konsol xatosi — FAIL.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m3b-real-check.mjs (stek ko'tarilgan bo'lsin).
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
const BASE = 'http://127.0.0.1:5175';
const API_CONTAINER = 'innova-m0-api-1';
const PG_CONTAINER = 'innova-m0-postgres-1';
const RECORDINGS_DIR = '/var/spool/asterisk/monitor';

// Haqiqiy backend run'lar orasida holatni saqlaydi (reset yo'q) — har ishga tushirishda yagona teg.
const RUN_TAG = Date.now().toString(36);
const BITRIX_WEBHOOK_URL = 'http://172.28.0.250/rest/1/abc/';
const AMO_BASE_URL = 'https://172.28.0.251';
const AMO_TOKEN = `sinov-amo-token-${RUN_TAG}`;

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
  await page.screenshot({ path: path.join(SHOTS, `m3b-${name}-${theme}.png`) });
}

// ------------------------------------------------------------ docker/psql yordamchilari
async function sh(cmd, args) {
  const { stdout } = await execFileP(cmd, args, { maxBuffer: 10 * 1024 * 1024 });
  return stdout;
}

async function psql(sql) {
  const out = await sh('docker', ['exec', PG_CONTAINER, 'psql', '-U', 'innova', '-d', 'innova', '-tAc', sql]);
  // `-tAc` ichidagi `INSERT ...RETURNING`/`DELETE` kabi buyruqlar natija qatoridan keyin
  // psql tomonidan har doim qo'shiladigan "INSERT 0 1"/"DELETE 1" kabi status qatorini ham chiqaradi —
  // bizga faqat haqiqiy natija (birinchi qator) kerak.
  return out.split('\n')[0].trim();
}

async function dockerExecApi(cmd) {
  return sh('docker', ['exec', API_CONTAINER, 'sh', '-c', cmd]);
}

/** Playback sinovi uchun — diskda haqiqiy WAV + mos `cdr`/`call_recordings` qatorlari yaratadi. */
async function createRecordingFixture(tag) {
  const linkedid = `m3bchk-${tag}`;
  const uniqueid = `${linkedid}-u1`;
  const src = '9601';
  const dst = '9602';
  const relPath = `m3b-check/${linkedid}-rec.wav`;
  const absPath = `${RECORDINGS_DIR}/${relPath}`;

  const tenantRow = (await psql(
    "select t.id || '|' || t.code from tenants t join users u on u.tenant_id=t.id where u.username='admin' limit 1;",
  )).trim();
  const [tenantId, tenantCode] = tenantRow.split('|');
  if (!tenantId || !tenantCode) throw new Error(`tenant topilmadi (admin foydalanuvchi): ${tenantRow}`);

  await dockerExecApi(
    `mkdir -p "$(dirname '${absPath}')" && ffmpeg -y -f lavfi -i "sine=frequency=440:duration=3" `
    + `-ar 8000 -ac 1 -c:a pcm_s16le '${absPath}'`,
  );
  const sizeBytes = Number((await dockerExecApi(`stat -c %s '${absPath}'`)).trim()) || 0;
  if (sizeBytes <= 0) throw new Error('ffmpeg WAV fayli yaratilmadi yoki bo‘sh');

  await psql(
    `insert into cdr (calldate, clid, src, dst, dcontext, channel, dstchannel, lastapp, lastdata, duration, `
    + `billsec, disposition, accountcode, uniqueid, linkedid) values (now(), '"M3B Check" <${src}>', '${src}', `
    + `'${dst}', 'from-internal', 'SIP/${src}-00000001', 'SIP/${dst}-00000002', 'Dial', '${dst}', 3, 3, `
    + `'ANSWERED', '${tenantCode}', '${uniqueid}', '${linkedid}');`,
  );
  const recordingId = (await psql(
    `insert into call_recordings (tenant_id, linkedid, uniqueid, path, extension, started_at, duration_s, `
    + `size_bytes) values ('${tenantId}', '${linkedid}', 'rec', '${relPath}', '${src}', now() - interval `
    + `'3 seconds', 3, ${sizeBytes}) returning id;`,
  )).trim();
  if (!recordingId) throw new Error('call_recordings qatori yaratilmadi');

  return { linkedid, uniqueid, relPath, absPath, tenantId, tenantCode, src, dst, recordingId };
}

async function cleanupRecordingFixture(fx) {
  if (!fx) return;
  await psql(`delete from call_recordings where linkedid = '${fx.linkedid}';`).catch((e) => console.log('TOZALASH XATO (call_recordings):', e.message));
  await psql(`delete from cdr where linkedid = '${fx.linkedid}';`).catch((e) => console.log('TOZALASH XATO (cdr):', e.message));
  await dockerExecApi(`rm -f '${fx.absPath}'`).catch((e) => console.log('TOZALASH XATO (fayl):', e.message));
}

/** Har bir `checkWebhooks` chaqiruvi yangi qator yaratadi — tozalanmasa, jadval sahifalanishi (pageSize=8)
 * tufayli keyingi ishga tushirishlarda yangi qator 1-sahifadan tushib qolib, flaky bo'ladi. */
async function cleanupTestWebhook(tag) {
  await psql(`delete from integration_subscriptions where kind = 'webhook' and name = 'Haqiqiy sinov vebhuki ${tag}';`)
    .catch((e) => console.log('TOZALASH XATO (webhook):', e.message));
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

// ------------------------------------------------------------ mavjud tekshiruvlar (API kalit, vebhuk)
async function checkApiKeys(page, theme, tag) {
  const name = `Haqiqiy sinov kaliti ${tag}`;
  await page.getByRole('tab', { name: 'API kalitlari' }).click();
  await page.getByTestId('apikey-create').click();
  await page.getByRole('textbox', { name: 'Nomi' }).fill(name);
  await page.getByRole('checkbox', { name: 'Qoʻngʻiroqlarni oʻqish' }).click();
  await page.getByRole('button', { name: 'Kalit yaratish' }).click();
  const secret = await page.getByTestId('apikey-secret').textContent({ timeout: 10000 });
  if (!secret || !secret.startsWith('ipk_')) throw new Error(`apikey-secret kutilmagan: ${secret}`);
  await shot(page, 'apikey-secret', theme);
  await page.getByRole('button', { name: 'Yopish' }).last().click();

  const row = page.getByRole('row', { name });
  await row.getByRole('button', { name: 'Bekor qilish' }).click();
  await page.getByRole('button', { name: 'Ha, bekor qilish' }).click();
  await row.getByText('Faol').waitFor({ state: 'detached', timeout: 10000 });
}

async function checkWebhooks(page, theme, tag) {
  const name = `Haqiqiy sinov vebhuki ${tag}`;
  await page.getByRole('tab', { name: 'Vebhuklar' }).click();
  await page.getByTestId('webhook-create').click();
  await page.getByRole('textbox', { name: 'Nomi' }).fill(name);
  await page.getByRole('textbox', { name: 'Manzil (URL)' }).fill('http://127.0.0.1/hook');
  await page.getByRole('checkbox', { name: 'Tugadi' }).click();
  await page.getByRole('button', { name: 'Vebhuk qoʻshish' }).click();
  await page.getByText('Bu manzilga vebhuk yuborish taqiqlangan').waitFor({ timeout: 10000 });

  const urlField = page.getByRole('textbox', { name: 'Manzil (URL)' });
  await urlField.fill('');
  await urlField.fill('https://example.com/innova-hook');
  await page.getByRole('button', { name: 'Vebhuk qoʻshish' }).click();
  const secret = await page.getByTestId('webhook-secret').textContent({ timeout: 10000 });
  if (!secret) throw new Error('webhook-secret bo‘sh');
  await shot(page, 'webhooks', theme);
  await page.getByRole('button', { name: 'Yopish' }).last().click();

  const row = page.getByRole('row', { name });
  await row.getByRole('button', { name: 'Sinov yuborish' }).click();
  await page.getByText('Sinov hodisasi navbatga qoʻyildi.').first().waitFor({ timeout: 10000 });

  await row.getByRole('button', { name: 'Yetkazishlar jurnali' }).click();
  await page.getByText('Yetkazishlar jurnali').first().waitFor({ timeout: 10000 });
  await shot(page, 'webhooks-deliveries', theme);
  await page.keyboard.press('Escape');
}

// ------------------------------------------------------------ Umumiy tabdagi karta holati
async function cardStatusNotConnected(page, title) {
  const card = page.getByRole('heading', { name: title, exact: true })
    .locator('xpath=ancestor::div[contains(@class,"rounded-lg")][1]');
  const text = await card.getByText(/Ishlayapti|Xato|Oʻchirilgan|Ulanmagan/).first().textContent();
  return (text ?? '').trim() === 'Ulanmagan';
}

// ------------------------------------------------------------ Bitrix24: forma + maskalash + sir sizmaligi + test
async function checkBitrix24(page, theme) {
  const leaks = [];
  const onResponse = (r) => {
    if (r.url().includes('/integrations/crm/')) {
      r.text().then((body) => { if (body.includes(BITRIX_WEBHOOK_URL)) leaks.push(r.url()); }).catch(() => {});
    }
  };
  page.on('response', onResponse);
  try {
    await page.getByRole('tab', { name: 'Bitrix24' }).click();
    await page.getByTestId('crm-bitrix24-form').waitFor({ timeout: 10000 });

    const toggle = page.getByRole('switch', { name: 'Bitrix24 integratsiyasi yoqilgan' });
    if ((await toggle.getAttribute('aria-checked')) !== 'true') await toggle.click();
    await page.getByLabel('Kiruvchi vebhuk manzili').fill(BITRIX_WEBHOOK_URL);

    const bitrix24Form = page.getByTestId('crm-bitrix24-form');
    await bitrix24Form.getByRole('button', { name: 'Saqlash' }).click();
    await page.getByText('Saqlandi.').first().waitFor({ timeout: 10000 });
    await delay(500); // tarmoq javob matnini o'qish (text() promise) ulgurishi uchun
    if (leaks.length) throw new Error(`webhook_url javobda ochiq topildi: ${leaks.join(', ')}`);

    await page.reload();
    await page.getByRole('tab', { name: 'Bitrix24' }).click();
    await page.getByTestId('crm-bitrix24-form').waitFor({ timeout: 10000 });
    const masked = await page.getByText('Manzil saqlangan').first().isVisible().catch(() => false);
    if (!masked) throw new Error('reload’dan keyin "Manzil saqlangan" (maskalangan) belgisi ko‘rinmadi');
    await shot(page, 'bitrix24', theme);

    let sawServerError = false;
    const onTestResponse = (r) => { if (r.url().includes('/integrations/crm/bitrix24/test') && r.status() >= 500) sawServerError = true; };
    page.on('response', onTestResponse);
    await page.getByTestId('crm-test').click();
    await page.getByText(/Ulanish muvaffaqiyatli\.|Ulanish muvaffaqiyatsiz\./).first().waitFor({ timeout: 15000 });
    page.off('response', onTestResponse);
    if (sawServerError) throw new Error('ulanish sinovi 5xx qaytardi (server xatosi bo‘lmasligi kerak)');

    await page.getByRole('tab', { name: 'Umumiy' }).click();
    if (await cardStatusNotConnected(page, 'Bitrix24')) throw new Error('Umumiy tabida Bitrix24 karta holati hali "Ulanmagan"');
  } finally {
    page.off('response', onResponse);
  }
}

// ------------------------------------------------------------ amoCRM: forma + maskalash + sir sizmaligi + test
async function checkAmoCrm(page, theme) {
  const leaks = [];
  const onResponse = (r) => {
    if (r.url().includes('/integrations/crm/')) {
      r.text().then((body) => { if (body.includes(AMO_TOKEN)) leaks.push(r.url()); }).catch(() => {});
    }
  };
  page.on('response', onResponse);
  try {
    await page.getByRole('tab', { name: 'amoCRM' }).click();
    await page.getByTestId('crm-amocrm-form').waitFor({ timeout: 10000 });

    const toggle = page.getByRole('switch', { name: 'amoCRM integratsiyasi yoqilgan' });
    if ((await toggle.getAttribute('aria-checked')) !== 'true') await toggle.click();
    await page.getByLabel('Portal manzili').fill(AMO_BASE_URL);
    await page.getByLabel('Uzoq muddatli token').fill(AMO_TOKEN);

    const amoForm = page.getByTestId('crm-amocrm-form');
    await amoForm.getByRole('button', { name: 'Saqlash' }).click();
    await page.getByText('Saqlandi.').first().waitFor({ timeout: 10000 });
    await delay(500);
    if (leaks.length) throw new Error(`token javobda ochiq topildi: ${leaks.join(', ')}`);

    await page.reload();
    await page.getByRole('tab', { name: 'amoCRM' }).click();
    await page.getByTestId('crm-amocrm-form').waitFor({ timeout: 10000 });
    const masked = await page.getByText('Token saqlangan').first().isVisible().catch(() => false);
    if (!masked) throw new Error('reload’dan keyin "Token saqlangan" (maskalangan) belgisi ko‘rinmadi');
    await shot(page, 'amocrm', theme);

    let sawServerError = false;
    const onTestResponse = (r) => { if (r.url().includes('/integrations/crm/amocrm/test') && r.status() >= 500) sawServerError = true; };
    page.on('response', onTestResponse);
    await page.getByTestId('crm-test').click();
    await page.getByText(/Ulanish muvaffaqiyatli\.|Ulanish muvaffaqiyatsiz\./).first().waitFor({ timeout: 15000 });
    page.off('response', onTestResponse);
    if (sawServerError) throw new Error('ulanish sinovi 5xx qaytardi (server xatosi bo‘lmasligi kerak)');

    await page.getByRole('tab', { name: 'Umumiy' }).click();
    if (await cardStatusNotConnected(page, 'amoCRM')) throw new Error('Umumiy tabida amoCRM karta holati hali "Ulanmagan"');
  } finally {
    page.off('response', onResponse);
  }
}

// ------------------------------------------------------------ 1C: 5 namuna + yuklab olish
async function checkOneC(page, theme) {
  await page.getByRole('tab', { name: '1C', exact: true }).click();
  const downloadButtons = page.getByRole('button', { name: 'Yuklab olish' });
  await downloadButtons.first().waitFor({ timeout: 10000 });
  const count = await downloadButtons.count();
  if (count !== 5) throw new Error(`namunalar soni 5 emas: ${count}`);
  await shot(page, '1c', theme);

  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/integrations/1c/samples/') && r.request().method() === 'GET', { timeout: 10000 }),
    downloadButtons.first().click(),
  ]);
  if (response.status() !== 200) throw new Error(`namuna yuklab olish status ${response.status()}`);
  const body = await response.body();
  if (!body || body.length === 0) throw new Error('namuna fayli bo‘sh');
}

async function checkSettings(page, theme) {
  await page.getByRole('tab', { name: 'Sozlamalar', exact: true }).click();
  await page.getByText('Integratsiyalar sozlamalari').waitFor({ timeout: 10000 });
  await shot(page, 'settings', theme);
}

// ------------------------------------------------------------ /calls — sinov yozuvini tinglash
async function checkRecordingPlayback(page, theme, fx) {
  await page.goto(BASE + '/cdr');
  const search = page.getByRole('searchbox');
  await search.waitFor({ timeout: 10000 });
  await search.fill(fx.src);
  const playBtn = page.getByTestId(`recording-play-${fx.recordingId}`);
  await playBtn.waitFor({ timeout: 10000 });

  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/recordings/') && r.url().includes('/audio'), { timeout: 10000 }),
    playBtn.click(),
  ]);
  if (response.status() !== 200) throw new Error(`yozuv audio javobi ${response.status()}`);
  await delay(300);
  await shot(page, 'calls-recording', theme);
}

// ------------------------------------------------------------ bitta mavzu (light/dark) uchun to'liq o'tish
async function runTheme(browser, runner, { theme, fixture }) {
  const tag = `${RUN_TAG}-${theme}`;
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme);
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e}`));
  // "Failed to load resource: ..." — Chrome brauzerining o'zi har qanday <2xx javob uchun avtomatik
  // chiqaradigan konsol yozuvi (4xx ham). 5xx holatlari yuqoridagi `response` tekshiruvida alohida
  // ushlanadi; 4xx esa ko'pincha ataylab tekshirilayotgan salbiy yo'llar (vebhuk 422, operator uchun
  // yo'q kengaytma 404 va sh.k.) — shu sababli bu auto-log signal sifatida hisoblanmaydi. Haqiqiy ilova
  // xatosi (console.error chaqiruvi/uncaught) baribir FAIL bo'lib qoladi.
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    if (/favicon/i.test(m.text()) || /^Failed to load resource:/.test(m.text())) return;
    consoleErrors.push(`console.error: ${m.text()}`);
  });
  page.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 500) consoleErrors.push(`${r.status()} ${r.url()}`); });

  const { step } = runner;
  try {
    await step(`[${theme}] kirish`, async () => {
      await page.goto(BASE + '/login');
      await page.getByLabel('Login').fill('admin');
      await page.getByLabel('Parol').fill(adminPassword());
      await page.getByRole('button', { name: 'Kirish' }).click();
      await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    });

    await step(`[${theme}] /settings/integrations ochildi`, async () => {
      await page.goto(BASE + '/settings/integrations');
      await page.getByTestId('integrations-page').waitFor({ timeout: 10000 });
      await shot(page, 'overview', theme);
    });

    await step(`[${theme}] API kalit yaratish/bekor qilish`, () => checkApiKeys(page, theme, tag));
    await step(`[${theme}] vebhuk yaratish/sinov/jurnal`, async () => {
      try {
        await checkWebhooks(page, theme, tag);
      } finally {
        await cleanupTestWebhook(tag);
      }
    });
    await step(`[${theme}] Bitrix24 forma + maskalash + sir sizmaligi + sinov + karta`, () => checkBitrix24(page, theme));
    await step(`[${theme}] amoCRM forma + maskalash + sir sizmaligi + sinov + karta`, () => checkAmoCrm(page, theme));
    await step(`[${theme}] 1C — 5 namuna + yuklab olish`, () => checkOneC(page, theme));
    await step(`[${theme}] Sozlamalar tabi`, () => checkSettings(page, theme));
    await step(`[${theme}] /calls — yozuvni tinglash`, () => checkRecordingPlayback(page, theme, fixture));

    await step(`[${theme}] konsol/5xx xatolari yo'q`, async () => {
      if (consoleErrors.length) throw new Error(consoleErrors.join(' | '));
    });
  } finally {
    await context.close();
  }
}

async function main() {
  const vite = spawn(path.join(WEB_DIR, 'node_modules', '.bin', 'vite'), ['--port', '5175', '--strictPort'], {
    cwd: WEB_DIR, env: { ...process.env, VITE_API: 'real' }, stdio: 'ignore',
  });
  const runner = makeRunner();
  let fixture = null;
  let browser = null;
  try {
    await waitForServer(BASE + '/', 30000);

    await runner.step('sinov yozuvi (cdr + call_recordings + WAV) yaratildi', async () => {
      fixture = await createRecordingFixture(RUN_TAG);
    });

    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    for (const theme of ['light', 'dark']) {
      await runTheme(browser, runner, { theme, fixture });
    }
  } catch (e) {
    runner.results.fail += 1;
    console.log('XATO:', e?.message ?? e);
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    await cleanupRecordingFixture(fixture);
    vite.kill('SIGTERM');
  }
  console.log(`PASS=${runner.results.pass} FAIL=${runner.results.fail}`);
  process.exit(runner.results.fail > 0 ? 1 : 0);
}

main();
