// M5b UI'ni HAQIQIY API bilan tekshiradi (contract §1 Follow Me, §2 QR):
// admin -> /extensions: QR tugmasi (WebRTC raqamda o'chiq), QR oynasi (rasm, qolgan vaqt, «Yangi QR» yangi token),
// tahrir oynasida Follow Me (raqam qo'shish, tartib, yoqish, saqlash -> API'da bor), noma'lum ichki raqam -> qator
// belgilanadi, Follow Me'dan keyin asosiy forma `stale` olmaydi; operator -> /me: Follow Me kartasi va QR;
// tashqi manzil sozlanmagan -> xato + sozlamalar havolasi. DARK/mobil — ko'rinish. 5xx/konsol xatosi — FAIL.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m5b-real-check.mjs (stek 127.0.0.1:8710 da ishlab turgan bo'lsin).
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const WEB_DIR = path.join(ROOT, '..');
const SHOTS = path.join(ROOT, '..', '..', 'replica', 'clone-screens');
const BASE = 'http://127.0.0.1:5177';
const API = 'http://127.0.0.1:8710/api/v1';
const OPERATOR = { username: 'm5b_rc_op', password: 'M5bRcOperator!2026' };
const PUBLIC_URL = 'https://pbx-rc.example.uz';
const EXT = { main: '531', target: '532', webrtc: '533', op: '534' };
let TOKEN = '';
const ids = {};
let originalPublicUrl = null;

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

async function ensureExtension(number, webrtc) {
  const created = await api('POST', '/extensions', { number, name: `M5b RC ${number}`, webrtc });
  if (![201, 409].includes(created.status)) throw new Error(`ext ${number}: ${created.status}`);
  const list = await api('GET', `/extensions?q=${number}`);
  const ext = (list.json?.items ?? []).find((e) => e.number === number);
  if (!ext) throw new Error(`ext ${number} topilmadi`);
  return ext.id;
}

async function setPublicUrl(url) {
  const cur = await api('GET', '/settings/integrations');
  const r = await api('PATCH', '/settings/integrations', { public_base_url: url, updated_at: cur.json.updated_at });
  if (r.status !== 200) throw new Error(`public_base_url: ${r.status} ${JSON.stringify(r.json)}`);
  return cur.json.public_base_url;
}

/** Admin yaratgan foydalanuvchi birinchi kirishda parolni almashtirishi shart — o'sha parolga «almashtiramiz». */
async function settleOperatorPassword() {
  const post = (p, body, token) => fetch(API + p, {
    method: 'POST', body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then((r) => r.json());
  const login = await post('/auth/login', { login: OPERATOR.username, password: OPERATOR.password });
  if (!login.access) throw new Error('operator login');
  if (!login.user?.must_change_password) return;
  const changed = await post('/auth/change-password', { current: OPERATOR.password, new: OPERATOR.password }, login.access);
  if (!changed.access) throw new Error(`operator change-password: ${JSON.stringify(changed)}`);
}

/** Tayyorlov (API): admin token, 4 ta ichki raqam, operator (534 ga bog'langan), Follow Me sukutga, tashqi manzil. */
async function prepare() {
  const r = await api('POST', '/auth/login', { login: 'admin', password: adminPassword() });
  TOKEN = r.json?.access ?? '';
  if (!TOKEN) throw new Error(`admin API login: ${r.status}`);
  for (const [key, number] of Object.entries(EXT)) ids[key] = await ensureExtension(number, key === 'webrtc');
  const op = await api('POST', '/users', { ...OPERATOR, full_name: 'M5b RC Op', role: 'operator', extension_id: ids.op });
  if (![201, 409].includes(op.status)) throw new Error(`operator: ${op.status}`);
  await settleOperatorPassword();
  const off = { enabled: false, numbers: [], strategy: 'ring_all', include_extension: true, ring_seconds: 20, confirm: true };
  for (const key of ['main', 'op']) {
    const fm = await api('PUT', `/extensions/${ids[key]}/follow-me`, off);
    if (fm.status !== 200) throw new Error(`follow-me reset ${key}: ${fm.status}`);
    const ext = (await api('GET', `/extensions?q=${EXT[key]}`)).json.items.find((e) => e.id === ids[key]);
    if (ext.dnd) await api('PATCH', `/extensions/${ids[key]}`, { dnd: false, updated_at: ext.updated_at });
  }
  originalPublicUrl = await setPublicUrl(PUBLIC_URL);
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
  await page.screenshot({ path: path.join(SHOTS, `m5b-${name}-${theme}.png`) });
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

async function login(page, login_, password) {
  await page.goto(BASE + '/login');
  await page.getByLabel('Login').fill(login_);
  await page.getByLabel('Parol').fill(password);
  await page.getByRole('button', { name: 'Kirish' }).click();
}

function watchPage(page) {
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('response', (r) => {
    // 409/422 — sinov ataylab chaqiradigan javoblar; boshqa 4xx/5xx — muammo (URL bilan).
    if (r.status() >= 400 && ![409, 422].includes(r.status())) problems.push(`${r.status()} ${r.url()}`);
  });
  return problems;
}

// Brauzerning «Failed to load resource» yozuvi URL'siz — javoblar o'zi (URL bilan) yuqorida yoziladi.
// Admin'da ichki raqam yo'q — `/me/softphone` 404 (M3a, kutilgan).
const realProblems = (problems) => problems.filter((p) => !p.includes('Failed to load resource') && !p.includes('/me/softphone'));

async function gotoExtensions(page) {
  await page.goto(BASE + '/extensions');
  // Jadval 8 qatordan sahifalaydi — sinov raqamlari (53x) qidiruv bilan bir sahifaga chiqariladi.
  await page.locator('input[type="search"]').fill('53');
  await page.getByTestId(`qr-open-${EXT.main}`).waitFor({ timeout: 45000 });
}

/** Bosish va javobni birga kutish (alohida promise rad etilsa jarayon yiqilmasin). */
async function clickFor(page, locator, method, urlPart) {
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(urlPart) && r.request().method() === method, { timeout: 15000 }),
    locator.click(),
  ]);
  return resp;
}

const qrClick = (page, locator) => clickFor(page, locator, 'POST', '/qr-provisioning');

// ------------------------------------------------------------ admin: QR
async function checkAdminQr(page, theme, step) {
  await step(`[${theme}] WebRTC raqamda QR tugmasi o'chiq, oddiyda yoqiq`, async () => {
    await gotoExtensions(page);
    if (!(await page.getByTestId(`qr-open-${EXT.webrtc}`).isDisabled())) throw new Error('webrtc QR yoqiq');
    if (await page.getByTestId(`qr-open-${EXT.main}`).isDisabled()) throw new Error('oddiy QR oʻchiq');
  });

  let firstUrl = '';
  await step(`[${theme}] QR oynasi: rasm, qolgan vaqt, bir martalik havola`, async () => {
    const body = await (await qrClick(page, page.getByTestId(`qr-open-${EXT.main}`))).json();
    firstUrl = body.url;
    if (!firstUrl.startsWith(`${PUBLIC_URL}/prov/qr/`)) throw new Error(`url: ${firstUrl}`);
    const src = await page.getByTestId('qr-image').getAttribute('src', { timeout: 10000 });
    if (!src?.startsWith('data:image/png')) throw new Error('QR rasm data URL emas');
    const cd = await page.getByTestId('qr-countdown').textContent();
    if (!/1[45]:\d\d/.test(cd ?? '')) throw new Error(`countdown: ${cd}`);
    await shot(page, 'qr-admin', theme);
  });

  await step(`[${theme}] «Yangi QR» — yangi token, eskisi bekor`, async () => {
    const body = await (await qrClick(page, page.getByTestId('qr-refresh'))).json();
    if (body.url === firstUrl) throw new Error('token oʻzgarmadi');
    const old = await fetch(firstUrl.replace(PUBLIC_URL, 'http://127.0.0.1:8710'));
    if (old.status !== 404) throw new Error(`eski token: ${old.status}`);
    await page.keyboard.press('Escape');
  });
}

// ------------------------------------------------------------ admin: Follow Me tahrir oynasida
async function openEditor(page) {
  await page.getByRole('button', { name: `${EXT.main}ni tahrirlash` }).click();
  const drawer = page.getByRole('dialog');
  await drawer.getByTestId('fm-add-input').waitFor({ timeout: 10000 });
  return drawer;
}

async function checkAdminFollowMe(page, theme, step) {
  await step(`[${theme}] Follow Me: qo'shish, tartib, yoqish, saqlash -> API`, async () => {
    const drawer = await openEditor(page);
    await drawer.getByTestId('fm-add-input').fill('+998 (90) 123-45-67');
    await drawer.getByTestId('fm-add-input').press('Enter');
    await drawer.getByTestId('fm-add-input').fill(EXT.target);
    await drawer.getByTestId('fm-add').click();
    await drawer.getByRole('button', { name: `${EXT.target}ni yuqoriga` }).click();
    await drawer.getByRole('switch', { name: 'Javob boʻlmasa boshqa raqamlarga jiringlash' }).click();
    await shot(page, 'followme-drawer', theme);
    await drawer.getByTestId('fm-save').click();
    await page.getByText('Follow Me saqlandi').waitFor({ timeout: 10000 });
    const fm = (await api('GET', `/extensions/${ids.main}/follow-me`)).json.follow_me;
    if (!fm.enabled || fm.numbers.join(',') !== `${EXT.target},998901234567`) throw new Error(JSON.stringify(fm));
  });

  await step(`[${theme}] Follow Me'dan keyin asosiy forma stale olmaydi`, async () => {
    const drawer = page.getByRole('dialog');
    await drawer.getByRole('switch', { name: 'Bezovta qilmang (DND)' }).click();
    const r = await clickFor(page, drawer.getByRole('button', { name: 'Saqlash', exact: true }), 'PATCH', `/extensions/${ids.main}`);
    if (r.status() !== 200) throw new Error(`PATCH ${r.status()}`);
    await drawer.waitFor({ state: 'detached', timeout: 10000 });
  });

  // Drawer qayta ochiladi — Follow Me keshi DND saqlangandan keyingi updated_at bilan bo'lishi kerak (409 stale emas).
  await step(`[${theme}] noma'lum ichki raqam -> 422, qator belgilanadi`, async () => {
    const drawer = await openEditor(page);
    await drawer.getByTestId('fm-add-input').fill('599');
    await drawer.getByTestId('fm-add-input').press('Enter');
    const put = await clickFor(page, drawer.getByTestId('fm-save'), 'PUT', '/follow-me');
    if (put.status() !== 422) throw new Error(`422 kutilgan, keldi ${put.status()}: ${await put.text()}`);
    const cls = await drawer.getByTestId('fm-number-2').getAttribute('class');
    if (!cls?.includes('border-danger')) throw new Error(`qator belgilanmadi: ${cls}`);
    await shot(page, 'followme-error', theme);
    await page.keyboard.press('Escape');
  });
}

// ------------------------------------------------------------ operator: /me
async function checkOperator(browser, theme, step, viewport) {
  const context = await browser.newContext({ viewport, colorScheme: theme.startsWith('dark') ? 'dark' : 'light' });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme.startsWith('dark') ? 'dark' : 'light');
  const page = await context.newPage();
  const problems = watchPage(page);
  try {
    await step(`[${theme}] operator /me: Follow Me kartasi va QR`, async () => {
      await login(page, OPERATOR.username, OPERATOR.password);
      await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 10000 });
      await page.goto(BASE + '/me');
      await page.getByTestId('follow-me').waitFor({ timeout: 30000 }).catch(async (e) => {
        await page.screenshot({ path: '/tmp/m5b-me-fail.png' });
        throw new Error(`${e.message.split('\n')[0]} @ ${page.url()}`);
      });
      if (await page.getByTestId('fm-ring-seconds').count()) throw new Error('compact rejimda vaqt maydoni bor');
      await shot(page, 'me', theme);
      if ((await qrClick(page, page.getByTestId('me-qr-open'))).status() !== 200) throw new Error('QR 200 emas');
      await page.getByTestId('qr-image').waitFor({ timeout: 10000 });
      await shot(page, 'me-qr', theme);
      if (realProblems(problems).length) throw new Error(realProblems(problems).join(' | '));
    });
  } finally {
    await context.close();
  }
}

// ------------------------------------------------------------ tashqi manzil yo'q
async function checkNoPublicHost(page, theme, step) {
  await step(`[${theme}] tashqi manzil sozlanmagan -> xato + sozlamalar havolasi`, async () => {
    await setPublicUrl(null);
    await gotoExtensions(page);
    if ((await qrClick(page, page.getByTestId(`qr-open-${EXT.main}`))).status() !== 409) throw new Error('409 kutilgan');
    const link = page.getByTestId('qr-error').getByRole('link', { name: 'Sozlamalarni ochish' });
    if ((await link.getAttribute('href')) !== '/settings/integrations') throw new Error('havola yoʻq');
    await shot(page, 'qr-no-host', theme);
    await page.keyboard.press('Escape');
    await setPublicUrl(PUBLIC_URL);
  });
}

async function runAdmin(browser, runner, theme, viewport) {
  const context = await browser.newContext({ viewport, colorScheme: theme.startsWith('dark') ? 'dark' : 'light' });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme.startsWith('dark') ? 'dark' : 'light');
  const page = await context.newPage();
  const problems = watchPage(page);
  try {
    await login(page, 'admin', adminPassword());
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    if (theme === 'light') {
      await checkAdminQr(page, theme, runner.step);
      await checkAdminFollowMe(page, theme, runner.step);
      await checkNoPublicHost(page, theme, runner.step);
    } else {
      await runner.step(`[${theme}] QR oynasi va Follow Me ko'rinishi`, async () => {
        await gotoExtensions(page);
        await page.getByTestId(`qr-open-${EXT.main}`).click();
        await page.getByTestId('qr-image').waitFor({ timeout: 10000 });
        await shot(page, 'qr-admin', theme);
        await page.keyboard.press('Escape');
        await openEditor(page);
        await page.getByTestId('follow-me').scrollIntoViewIfNeeded();
        await shot(page, 'followme-drawer', theme);
      });
    }
    const real = realProblems(problems);
    await runner.step(`[${theme}] 5xx/konsol xatosi yo'q`, async () => { if (real.length) throw new Error(real.join(' | ')); });
  } finally {
    await context.close();
  }
}

async function main() {
  const vite = spawn(path.join(WEB_DIR, 'node_modules', '.bin', 'vite'), ['--port', '5177', '--strictPort'], {
    cwd: WEB_DIR, env: { ...process.env, VITE_API: 'real' }, stdio: 'ignore',
  });
  const runner = makeRunner();
  let browser = null;
  try {
    await waitForServer(BASE + '/', 30000);
    await prepare();
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    await runAdmin(browser, runner, 'light', { width: 1440, height: 900 });
    await checkOperator(browser, 'light', runner.step, { width: 1440, height: 900 });
    await runAdmin(browser, runner, 'dark', { width: 1440, height: 900 });
    await checkOperator(browser, 'dark-mobile', runner.step, { width: 390, height: 844 });
  } catch (e) {
    runner.results.fail += 1;
    console.log('XATO:', e?.message ?? e);
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    if (TOKEN) await setPublicUrl(originalPublicUrl).catch(() => undefined);
    vite.kill('SIGTERM');
  }
  console.log(`PASS=${runner.results.pass} FAIL=${runner.results.fail}`);
  process.exit(runner.results.fail > 0 ? 1 : 0);
}

main();
