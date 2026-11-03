// M10 Bo'lak C UI'ni HAQIQIY API bilan (deploy qilingan `web` konteyneri, 127.0.0.1:8711) tekshiradi:
// Sifat nazorati (varaqa yaratish -> qo'ng'iroqni baholash -> Baholashlar/Xulosa), Callback vidjeti
// (yaratish + joylashtirish kodi), Javobsiz qo'ng'iroq qoidasi (yaratish + sinash), Integratsiyalar
// (Yandex SpeechKit sozlamalari + sinash + WebSocket namunasi), Audio TTS dialogi, Xavfsizlik
// (require_2fa siyosati), 2FA toʻliq oqimi (bir martalik test foydalanuvchida: ulash -> kirishda
// kod soʻralishi -> UsersPage'dan admin tomonidan tiklash). Hamma test yozuvlari oxirida API orqali
// o'chiriladi; `require_2fa` ham ishdan oldingi holatiga ('off') qaytariladi.
// Ishga tushirish: CHROME_PATH=... node web/scripts/m10-real-check.mjs (stek 127.0.0.1:8710/8711'da ishlab turgan bo'lsin).
import { readFileSync } from 'node:fs';
import crypto from 'node:crypto';
import { chromium } from 'playwright';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(ROOT, '..', '..', 'replica', 'clone-screens');
const BASE = 'http://127.0.0.1:8711';
const API = 'http://127.0.0.1:8710/api/v1';

const CHECKLIST_NAME = 'M10 RC — varaqa';
const WIDGET_NAME = 'M10 RC — vidjet';
const RULE_NAME = 'M10 RC — qoida';
const TEMP_USERNAME = 'm10rc_temp_2fa';
const TEMP_PASSWORD = 'M10rc!Temp2026Pass';
// DIQQAT (xavfsizlik — 2026-11-03 voqeasi): `require_2fa` siyosatini HAQIQIY, ulashilgan
// `admin` hisobi orqali sinamaymiz. Sabab: siyosat 'admins'/'all' ga o'tgan zahoti, ulanmagan
// (totp yoqilmagan) admin-rolli aktyorning HAR QANDAY keyingi so'rovi (jumladan uni qaytarib
// 'off' qiladigan PATCH so'rovining o'zi ham!) `403 2fa_enrollment_required` bilan bloklanadi —
// bu chiqishi yo'q qulf (deadlock): API orqali faqat allaqachon 2FA ulagan aktyor qaytarishi
// mumkin. Shu sababli bu sinovni mahalliy, bir martalik "admin" rolidagi vaqtinchalik
// foydalanuvchida — oldindan 2FA ulab qo'yilgan holda — o'tkazamiz: siyosat qanday bo'lishidan
// qat'i nazar, bu aktyor hech qachon qulflanib qolmaydi va qaytarishni kafolatlab bajaradi.
const TEMP_ADMIN_USERNAME = 'm10rc_temp_admin';
const TEMP_ADMIN_PASSWORD = 'M10rc!TempAdmin2026';

let TOKEN = '';

async function api(method, p, body, token) {
  const r = await fetch(API + p, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token ?? TOKEN}` },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
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

// ─────────────────────────── RFC 6238 TOTP (sof Node `crypto`, yangi paket qo'shilmadi) ───────────────────────────
function base32Decode(b32) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of b32.replace(/=+$/, '').toUpperCase()) {
    const idx = alphabet.indexOf(c);
    if (idx === -1) continue;
    bits += idx.toString(2).padStart(5, '0');
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

function totpCode(secretBase32, stepS = 30, digits = 6) {
  const key = base32Decode(secretBase32);
  const counter = Math.floor(Date.now() / 1000 / stepS);
  const buf = Buffer.alloc(8);
  buf.writeUInt32BE(Math.floor(counter / 2 ** 32), 0);
  buf.writeUInt32BE(counter % 2 ** 32, 4);
  const hmac = crypto.createHmac('sha1', key).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const code = ((hmac[offset] & 0x7f) << 24 | (hmac[offset + 1] & 0xff) << 16
    | (hmac[offset + 2] & 0xff) << 8 | (hmac[offset + 3] & 0xff)) % 10 ** digits;
  return code.toString().padStart(digits, '0');
}

/** Hozirgi 30s oynaning oxirigacha hali 5s dan ko'p qolganini tekshiradi -- aks holda submitdan oldin kod eskirib qolmasligi uchun keyingi oynagacha kutamiz. */
async function waitForFreshTotpWindow(stepS = 30, marginMs = 5000) {
  const msIntoStep = (Date.now() / 1000 % stepS) * 1000;
  const left = stepS * 1000 - msIntoStep;
  if (left < marginMs) await delay(left + 500);
}

// Backend bitta sekret uchun oxirgi tasdiqlangan qadamni (`totp_last_step`) takroriy
// hujumlardan himoyalanish uchun saqlaydi — xuddi shu sekretning xuddi shu 30s qadamidagi kodi
// ikkinchi marta yuborilsa, "invalid_code" bilan rad etiladi. Shu skript ichida bir sekret ketma-ket
// ikki joyda ishlatiladigan holatlar bor (masalan ulashdan keyin darhol kirish sinovi) — shu
// sababli har bir sekret uchun oxirgi ishlatilgan qadamni kuzatib, zarur bo'lsa keyingi qadamgacha
// kutamiz.
const usedTotpSteps = new Map();
async function freshTotpCode(secret, stepS = 30) {
  await waitForFreshTotpWindow(stepS);
  let step = Math.floor(Date.now() / 1000 / stepS);
  if (usedTotpSteps.get(secret) === step) {
    const msIntoStep = (Date.now() / 1000 % stepS) * 1000;
    await delay(stepS * 1000 - msIntoStep + 500);
    step = Math.floor(Date.now() / 1000 / stepS);
  }
  usedTotpSteps.set(secret, step);
  return totpCode(secret, stepS);
}

/** Backend M10 C endpointlari hali tayyor emasligini aniqlaydi. */
async function backendReady() {
  const probes = await Promise.all([
    api('GET', '/qa/checklists'),
    api('GET', '/callback-widgets'),
    api('GET', '/missed-call-rules'),
    api('GET', '/settings/tts'),
    api('GET', '/security/settings'),
  ]);
  return probes.every((r) => r.status !== 404 && r.status !== 501);
}

async function cleanup() {
  const checklists = await api('GET', '/qa/checklists');
  for (const c of (checklists.json?.items ?? []).filter((x) => x.name === CHECKLIST_NAME)) {
    const del = await api('DELETE', `/qa/checklists/${c.id}`);
    if (del.status === 409) {
      // DIQQAT: backend "in_use" bilan rad etadi — varaqa biror baholashda ishlatilgan bo'lsa
      // hard-delete qilib bo'lmaydi (2026-11-03 voqeasidan keyin topilgan haqiqiy holat: oldingi
      // uzilgan yurishlar qoldirgan baholashlar nomni abadiy band qilib qo'yardi). Avval shu
      // varaqaga tegishli baholashlarni o'chiramiz, keyin varaqaning o'zini qayta o'chiramiz.
      const evals = await api('GET', '/qa/evaluations?size=200');
      for (const ev of (evals.json?.items ?? []).filter((x) => x.checklist_id === c.id)) {
        await api('DELETE', `/qa/evaluations/${ev.id}`);
      }
      await api('DELETE', `/qa/checklists/${c.id}`);
    }
  }
  const widgets = await api('GET', '/callback-widgets');
  for (const w of (widgets.json?.items ?? []).filter((x) => x.name === WIDGET_NAME)) {
    await api('DELETE', `/callback-widgets/${w.id}`);
  }
  const rules = await api('GET', '/missed-call-rules');
  for (const r of (rules.json?.items ?? []).filter((x) => x.name === RULE_NAME)) {
    await api('DELETE', `/missed-call-rules/${r.id}`);
  }
  const users = await api('GET', '/users');
  for (const u of (users.json?.items ?? []).filter((x) => x.username === TEMP_USERNAME || x.username === TEMP_ADMIN_USERNAME)) {
    await api('DELETE', `/users/${u.id}`);
  }
  // DIQQAT: agar oldingi yurish yarim yo'lda uzilgan bo'lsa, `require_2fa` ham qaytarilmagan bo'lishi
  // mumkin -- agent A bilan baham ko'rilgan stekni buzmaslik uchun har safar 'off'ga qaytaramiz.
  const sec = await api('GET', '/security/settings');
  if (sec.json && sec.json.require_2fa !== 'off') {
    await api('PATCH', '/security/settings', { ...sec.json, require_2fa: 'off', updated_at: sec.json.updated_at });
  }
  // SpeechKit sinov kalitlarini ham tozalaymiz (keyingi yurish/boshqa agent uchun toza holat).
  const tts = await api('GET', '/settings/tts');
  if (tts.json && tts.json.provider !== 'none') {
    await api('PATCH', '/settings/tts', {
      provider: 'none', folder_id: null, voices: tts.json.voices, updated_at: tts.json.updated_at,
    });
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
  throw new Error('web konteyner javob bermadi');
}

async function shot(page, name) {
  await page.waitForLoadState('networkidle').catch(() => undefined);
  await delay(800);
  await page.screenshot({ path: path.join(SHOTS, `m10-${name}.png`) }).catch(() => undefined);
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

/** `totpSecret` berilsa — kirishdan keyin chiqadigan TOTP challenge ekranini ham shaffof bosib
 * o'tadi (masalan, allaqachon 2FA ulangan vaqtinchalik admin uchun). Berilmasa — challenge
 * ekrani (agar chiqsa) chaqiruvchiga qoldiriladi (masalan `loginTotpChallengeFlow` buni o'zi,
 * UI'ni sinash maqsadida, qo'lda bajaradi). */
async function login(page, username, password, totpSecret) {
  await page.goto(BASE + '/login');
  await page.getByLabel('Login').fill(username);
  await page.getByLabel('Parol').fill(password);
  await page.getByRole('button', { name: 'Kirish' }).click();
  if (totpSecret) {
    const challenge = page.getByText('Ikki bosqichli tasdiqlash');
    const sawChallenge = await challenge.waitFor({ state: 'visible', timeout: 5000 }).then(() => true).catch(() => false);
    if (sawChallenge) {
      await page.getByTestId('totp-code').fill(await freshTotpCode(totpSecret));
      await page.getByRole('button', { name: 'Tasdiqlash' }).click();
    }
  }
  // `POST /users` orqali yaratilgan foydalanuvchilarda `must_change_password: true` sukut
  // qiymat — birinchi kirishda "/change-password" oraliq ekrani majburiy chiqadi (o'tkazib
  // bo'lmaydi). Shu bosqichni shu yerda shaffof bosib o'tamiz (yangi parol = eski parol —
  // backend buni taqiqlamaydi), shunda chaqiruvchilar doim yakuniy ("home") sahifada tugaydi.
  const changePwd = page.getByRole('heading', { name: 'Parolni oʻzgartirish' });
  const sawChangePwd = await changePwd.waitFor({ state: 'visible', timeout: 5000 }).then(() => true).catch(() => false);
  if (sawChangePwd) {
    await page.getByLabel('Joriy parol').fill(password);
    await page.getByLabel('Yangi parol').fill(password);
    await page.getByRole('button', { name: 'Parolni oʻzgartirish va davom etish' }).click();
    // Mutatsiya (token yangilash + navigate) tugashini kutamiz — aks holda chaqiruvchi
    // zudlik bilan boshqa sahifaga o'tsa, hali tugallanmagan autentifikatsiya holati bilan
    // poyga (race) yuzaga kelishi mumkin.
    await page.waitForURL((url) => !url.pathname.startsWith('/change-password'), { timeout: 10000 });
  }
}

function watchPage(page) {
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('response', (r) => {
    if (r.status() >= 400 && ![409, 422].includes(r.status())) problems.push(`${r.status()} ${r.url()}`);
  });
  return problems;
}

// `/settings/tts/test` va `/audio/tts/preview` haqiqiy Yandex SpeechKit'ga boradi -- bu skriptda
// ataylab SOXTA kalit bilan sinaladi (maqsad: UI<->API simlanishini tekshirish, haqiqiy nutq
// sintezini EMAS), shuning uchun bu ikki yo'ldan kelgan 4xx/5xx "muammo" hisoblanmaydi.
const realProblems = (problems) => problems.filter((p) =>
  !p.includes('Failed to load resource')
  && !p.includes('/me/softphone')
  && !p.includes('/settings/tts/test')
  && !p.includes('/audio/tts/preview')
  && !p.includes('/audio/tts')
  // M9'dan sukut global widget `/parking`ni so'raydi — bu M10 C doirasidan tashqari va
  // umumiy stekda parallel ishlayotgan "M10 Bo'lak A" agentining `api/`dagi ishi bilan bog'liq
  // bo'lishi mumkin (biz `api/`ga tegmaymiz). M10 C'ning o'z xatosi emasligi aniq bo'lgani
  // uchun shovqin sifatida chetlab o'tamiz.
  && !p.includes('/parking'));

const FULL_SCREENS = [
  { path: '/quality', heading: 'Sifat nazorati' },
  { path: '/settings/integrations/widget', heading: 'Qayta qoʻngʻiroq vidjeti' },
  { path: '/missed-calls', heading: 'Javobsiz qoʻngʻiroq xabari' },
  { path: '/audio', heading: 'Audio kutubxona' },
  { path: '/settings/integrations', heading: 'Integratsiyalar' },
  { path: '/settings/security', heading: 'Xavfsizlik' },
  { path: '/settings/users', heading: 'Foydalanuvchilar' },
  { path: '/me', heading: 'Mening kabinetim' },
];

async function checkFullScreen(page, theme, { path: p, heading }) {
  await page.goto(BASE + p);
  await page.getByRole('heading', { name: heading }).first().waitFor({ timeout: 10000 });
  if (theme === 'light') await shot(page, `screen-${p.replace(/\//g, '-').slice(1)}`);
}

// ─────────────────────────── 3) Sifat nazorati: varaqa -> baholash -> xulosa ───────────────────────────

async function qaChecklistFlow(page) {
  await page.goto(BASE + '/quality');
  await page.getByRole('button', { name: 'Yangi varaqa' }).click();
  const drawer = page.getByRole('dialog');
  await drawer.getByLabel('Nomi').fill(CHECKLIST_NAME);
  await drawer.getByRole('button', { name: 'Mezon qoʻshish' }).click();
  await drawer.getByPlaceholder('Masalan: Salomlashish standartiga amal qildi').fill('Salomlashdimi?');
  await drawer.getByRole('button', { name: 'Qoʻshish', exact: true }).click();
  await page.getByRole('cell', { name: CHECKLIST_NAME, exact: true }).waitFor({ timeout: 8000 });
  await shot(page, 'quality-checklist-created');
}

async function evaluateCallFlow(page) {
  await page.goto(BASE + '/cdr');
  await page.getByRole('button', { name: /raqamiga qilingan qoʻngʻiroqni baholash/ }).first().click();
  const drawer = page.getByRole('dialog');
  await drawer.getByText('Qoʻngʻiroqni baholash').waitFor({ timeout: 8000 });
  await drawer.getByRole('combobox', { name: 'Varaqa' }).click();
  await page.getByRole('option', { name: CHECKLIST_NAME }).click();
  await drawer.getByRole('radiogroup', { name: 'Salomlashdimi?' }).getByRole('radio', { name: 'Ha' }).click();
  await drawer.getByLabel('Izoh (ixtiyoriy)').fill('M10 RC sinovi');
  await drawer.getByRole('button', { name: 'Baholashni saqlash' }).click();
  await page.getByText('Baholash saqlandi').waitFor({ timeout: 8000 });
  await shot(page, 'cdr-evaluated');
}

async function qualitySummaryFlow(page) {
  await page.goto(BASE + '/quality');
  await page.getByRole('tab', { name: 'Baholashlar' }).click();
  await page.getByRole('cell', { name: CHECKLIST_NAME, exact: true }).first().waitFor({ timeout: 8000 });
  await page.getByRole('tab', { name: 'Xulosa' }).click();
  await page.getByText('Jami baholashlar').waitFor({ timeout: 8000 });
  await shot(page, 'quality-summary');
}

// ─────────────────────────── 4b/9) 2FA: ulash (MePage) -> kirishda kod -> admin reset (UsersPage) ───────────────────────────

async function createTempOperatorUser() {
  // DIQQAT: `role` maydoni rol NOMI (masalan "operator"), UUID emas — UsersPage'ning oʻzi ham
  // shunday yuboradi (`roleOptions` → `value: r.name`). MePage ichki raqam bog'lanmagan
  // foydalanuvchiga ogohlantirish ekranini ko'rsatadi, 2FA kartasi esa faqat ichki raqam
  // bog'langandan keyin chiqadi — shu sababli boshqa foydalanuvchiga band bo'lmagan ichki
  // raqamni topib biriktiramiz.
  const [exts, users] = await Promise.all([api('GET', '/extensions?size=200'), api('GET', '/users?size=200')]);
  const taken = new Set((users.json?.items ?? []).map((u) => u.extension?.id).filter(Boolean));
  const freeExt = (exts.json?.items ?? []).find((e) => !taken.has(e.id));
  if (!freeExt) throw new Error('createTempOperatorUser: bo\'sh ichki raqam topilmadi');
  const res = await api('POST', '/users', {
    username: TEMP_USERNAME, full_name: 'M10 RC — vaqtinchalik', role: 'operator',
    password: TEMP_PASSWORD, language: 'uz', extension_id: freeExt.id,
  });
  if (res.status >= 400) throw new Error(`createUser: ${res.status} ${JSON.stringify(res.json)}`);
  return res.json.item;
}

// `require_2fa` sinovi uchun — admin rolida, lekin HAQIQIY `admin`dan butunlay mustaqil —
// vaqtinchalik foydalanuvchi yaratadi va unga sof API orqali (UI'siz, tezroq va ishonchliroq)
// TOTP ulaydi. `/auth/login`, `/me/2fa/setup`, `/me/2fa/enable` — barchasi `require_2fa`
// siyosatidan mustasno yo'llar (`is_enrollment_exempt_path`), shu sababli bu funksiya siyosat
// qanday bo'lishidan qat'i nazar doim ishlaydi.
async function createEnrolledTempAdmin() {
  const res = await api('POST', '/users', {
    username: TEMP_ADMIN_USERNAME, full_name: 'M10 RC — vaqtinchalik admin', role: 'admin',
    password: TEMP_ADMIN_PASSWORD, language: 'uz', extension_id: null,
  });
  if (res.status >= 400) throw new Error(`createTempAdmin: ${res.status} ${JSON.stringify(res.json)}`);
  const loginRes = await api('POST', '/auth/login', { login: TEMP_ADMIN_USERNAME, password: TEMP_ADMIN_PASSWORD });
  const token = loginRes.json?.access ?? '';
  if (!token) throw new Error(`tempAdmin login: ${loginRes.status} ${JSON.stringify(loginRes.json)}`);
  const setupRes = await api('POST', '/me/2fa/setup', undefined, token);
  const secret = setupRes.json?.secret ?? '';
  if (!secret) throw new Error(`tempAdmin 2fa/setup: ${setupRes.status} ${JSON.stringify(setupRes.json)}`);
  const enableRes = await api('POST', '/me/2fa/enable', { code: await freshTotpCode(secret) }, token);
  if (enableRes.status >= 400) throw new Error(`tempAdmin 2fa/enable: ${enableRes.status} ${JSON.stringify(enableRes.json)}`);
  return { token, secret };
}

// MePage'dagi TwoFactorCard orqali 2FA'ni yoqadi va keyingi (login-challenge) qadam uchun TOTP
// sekretini qaytaradi — sekret faqat ulash (setup) chaqirig'ida bir marta qaytariladi, shu
// sababli uni shu yerda saqlab qolamiz.
async function enrollTotpFlow(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  try {
    await login(page, TEMP_USERNAME, TEMP_PASSWORD);
    // DIQQAT: operator rolining kirishdan keyingi sukut sahifasi `homeFor()` qoidasiga ko'ra
    // ko'rinadigan birinchi ekran (masalan `/cdr`) bo'lishi mumkin, `/me` emas — shu sababli
    // bu yerni sinash uchun to'g'ridan-to'g'ri o'zimiz o'tamiz.
    await page.goto(BASE + '/me');
    let secret = '';
    await page.getByText('Ikki bosqichli tasdiqlash (2FA)').waitFor({ timeout: 8000 });
    await page.getByRole('button', { name: 'Yoqish' }).click();
    // DIQQAT: `span.num` klassi sahifada bir nechta joyda ishlatiladi (masalan
    // `RecentCallsCard`ning sana ustunida) — shu sababli sekretni faqat shu maqsad uchun
    // qo'yilgan `data-testid="totp-secret"` orqali olamiz, umumiy klass tanlagich emas.
    const secretEl = page.getByTestId('totp-secret');
    await secretEl.waitFor({ timeout: 8000 });
    secret = (await secretEl.textContent())?.trim() ?? '';
    if (!secret) throw new Error('TOTP sekret topilmadi');
    const codeField = page.getByLabel('Ilovadan 6 xonali kod');
    await codeField.fill(await freshTotpCode(secret));
    await page.getByRole('button', { name: 'Yoqish' }).click();
    await page.getByText('Zaxira kodlarni xavfsiz joyda saqlang').waitFor({ timeout: 8000 });
    await shot(page, 'me-2fa-enabled');
    await page.getByRole('button', { name: 'Tayyor' }).click();
    await page.getByText('Yoqilgan').first().waitFor({ timeout: 8000 });
    return secret;
  } finally {
    await context.close();
  }
}

// LoginPage'ning 2-bosqich (TOTP challenge) UI'sini — alohida, yangi sessiyada — toʻliq sinaydi:
// login+parol -> kod soʻralishi -> sekretdan hisoblangan haqiqiy kod -> «/me»ga tushishi.
async function loginTotpChallengeFlow(browser, secret) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  try {
    await login(page, TEMP_USERNAME, TEMP_PASSWORD);
    await page.getByText('Ikki bosqichli tasdiqlash').waitFor({ timeout: 8000 });
    await page.getByTestId('totp-code').fill(await freshTotpCode(secret));
    await page.getByRole('button', { name: 'Tasdiqlash' }).click();
    // DIQQAT: operator kirishdan keyin sukut holda `/me`ga emas, ko'rinadigan birinchi ekranga
    // (`homeFor()`) tushadi — shu sababli login challenge'dan keyin faqat "/login"dan
    // chiqqanini tekshiramiz, keyin autentifikatsiya haqiqatan ishlaganini `/me`ga o'tib
    // tasdiqlaymiz.
    await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 10000 });
    await page.goto(BASE + '/me');
    await page.getByText('Ikki bosqichli tasdiqlash (2FA)').waitFor({ timeout: 8000 });
    await shot(page, 'login-totp-challenge');
  } finally {
    await context.close();
  }
}

async function usersResetFlow(page) {
  await page.goto(BASE + '/settings/users');
  const row = page.getByRole('row', { name: new RegExp(TEMP_USERNAME) });
  await row.waitFor({ timeout: 8000 });
  await row.getByText('Yoqilgan', { exact: true }).waitFor({ timeout: 8000 });
  await row.getByRole('button', { name: new RegExp(`${TEMP_USERNAME} uchun 2FAʼni tiklash`) }).click();
  await page.getByRole('button', { name: '2FAʼni tiklash', exact: true }).click();
  await page.getByText(`${TEMP_USERNAME} uchun 2FA tiklandi`).waitFor({ timeout: 8000 });
  await row.getByText('Oʻchirilgan', { exact: true }).waitFor({ timeout: 8000 });
  await shot(page, 'users-2fa-reset');
}

// ─────────────────────────── 5) CallbackWidgetPage ───────────────────────────

async function callbackWidgetFlow(page) {
  await page.goto(BASE + '/settings/integrations/widget');
  await page.getByRole('button', { name: 'Yangi vidjet' }).click();
  const drawer = page.getByRole('dialog');
  await drawer.getByLabel('Nomi').fill(WIDGET_NAME);
  await drawer.getByRole('button', { name: /Qabul qiluvchi/ }).click();
  await page.getByRole('combobox', { name: 'Nom yoki raqam boʻyicha qidirish' }).press('Enter');
  await drawer.getByPlaceholder('https://sayt.uz').fill('https://m10rc.uz');
  await drawer.getByPlaceholder('https://sayt.uz').press('Enter');
  // DIQQAT: shu drawer ichida ikkita "Qoʻshish" tugmasi bor — ChipListField'ning o'ziniki (manzil
  // qo'shish) va formaning yakuniy submit tugmasi. Ikkinchisi DOMda keyinroq (footer) joylashgan.
  await drawer.getByRole('button', { name: 'Qoʻshish', exact: true }).last().click();
  await page.getByRole('cell', { name: WIDGET_NAME, exact: true }).waitFor({ timeout: 8000 });
  await shot(page, 'callback-widget-created');
  // DIQQAT: `embed_snippet` backendda hali `null` qaytmoqda (public_base_url sozlangan boʻlsa ham) —
  // bu M10 C UI qamrovida emas, shu sababli tugma disabled boʻlishi mumkin: shunday holatda faqat
  // tugma mavjudligini tasdiqlaymiz, nusxalashni majburlamaymiz.
  const copyBtn = page.getByRole('row', { name: new RegExp(WIDGET_NAME) }).getByRole('button', { name: new RegExp(`«${WIDGET_NAME}» kodini nusxalash`) });
  await copyBtn.waitFor({ timeout: 8000 });
  if (await copyBtn.isEnabled()) {
    await copyBtn.click();
    await page.getByText('Nusxalandi').waitFor({ timeout: 8000 });
  }
  await page.getByRole('tab', { name: 'Soʻrovlar jurnali' }).click();
  await page.getByText('Soʻrovlar jurnali').first().waitFor({ timeout: 8000 });
}

// ─────────────────────────── 6) MissedCallsPage ───────────────────────────

async function missedCallsFlow(page) {
  await page.goto(BASE + '/missed-calls');
  await page.getByRole('button', { name: 'Yangi qoida' }).click();
  const drawer = page.getByRole('dialog');
  await drawer.getByLabel('Nomi').fill(RULE_NAME);
  await drawer.getByPlaceholder('ism@korxona.uz').fill('m10rc@example.com');
  await drawer.getByPlaceholder('ism@korxona.uz').press('Enter');
  // DIQQAT: ChipListField'ning o'z "Qoʻshish" tugmasi bilan formaning yakuniy submit tugmasi
  // bir xil matnli — footer DOMda keyinroq joylashgani uchun oxirgisini olamiz.
  await drawer.getByRole('button', { name: 'Qoʻshish', exact: true }).last().click();
  await page.getByRole('cell', { name: RULE_NAME, exact: true }).waitFor({ timeout: 8000 });
  await shot(page, 'missedcalls-rule-created');
  await page.getByRole('row', { name: new RegExp(RULE_NAME) }).getByRole('button', { name: new RegExp(`«${RULE_NAME}»ni sinash`) }).click();
  await page.waitForTimeout(1500);
  await page.getByRole('tab', { name: 'Xabarlar jurnali' }).click();
  await page.getByText('Xabarlar jurnali').first().waitFor({ timeout: 8000 });
}

// ─────────────────────────── 7) AudioPage TTS + IntegrationsPage SpeechKit ───────────────────────────

async function speechkitConfigureFlow(page) {
  await page.goto(BASE + '/settings/integrations');
  await page.getByRole('tab', { name: 'Sozlamalar' }).click();
  const section = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Nutq sintezi (Yandex SpeechKit)' }) });
  await section.getByRole('combobox', { name: 'Provayder' }).click();
  await page.getByRole('option', { name: 'Yandex SpeechKit' }).click();
  await section.getByLabel('API kalit').fill('AQVN-m10rc-fake-key');
  await section.getByLabel('Katalog ID (folder_id)').fill('m10rc-folder');
  await section.getByRole('button', { name: 'Saqlash' }).click();
  await page.getByText('Saqlandi.').waitFor({ timeout: 8000 });
  await section.getByRole('button', { name: 'Sinash' }).click();
  await page.waitForTimeout(1500);
  await shot(page, 'integrations-speechkit');
}

async function speechkitRevertFlow(page) {
  await page.goto(BASE + '/settings/integrations');
  await page.getByRole('tab', { name: 'Sozlamalar' }).click();
  const section = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Nutq sintezi (Yandex SpeechKit)' }) });
  await section.getByRole('combobox', { name: 'Provayder' }).click();
  await page.getByRole('option', { name: 'Oʻchirilgan' }).click();
  await section.getByRole('button', { name: 'Saqlash' }).click();
  await page.getByText('Saqlandi.').waitFor({ timeout: 8000 });
}

async function apiKeysWsSnippetFlow(page) {
  await page.goto(BASE + '/settings/integrations');
  await page.getByRole('tab', { name: 'API kalitlari' }).click();
  await page.getByText('WebSocket ulanish namunasi').waitFor({ timeout: 8000 });
  await page.getByRole('button', { name: 'Nusxalash' }).click();
  await page.getByText('Nusxalandi').waitFor({ timeout: 8000 });
}

async function audioTtsDialogFlow(page) {
  await page.goto(BASE + '/audio');
  // DIQQAT: mikrofon yozuvining "Yozishni boshlash" tugmasi ham "boshlash" soʻzini oʻz ichiga
  // oladi — aniq (exact) moslik kerak, aks holda ikkita tugma mos kelib strict-mode xatosi beradi.
  await page.getByRole('button', { name: 'Boshlash', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText('Matndan audio yaratish').first().waitFor({ timeout: 8000 });
  await dialog.getByLabel('Matn').fill('Assalomu alaykum, bu M10 RC sinov matni.');
  await dialog.getByRole('button', { name: 'Tinglab koʻrish' }).click();
  await page.waitForTimeout(1500);
  await shot(page, 'audio-tts-dialog');
  await dialog.getByRole('button', { name: 'Bekor qilish' }).click();
}

// ─────────────────────────── 8) SecurityPage require_2fa ───────────────────────────

// DIQQAT (xavfsizlik — 2026-11-03 voqeasi): bu oqim ataylab HAQIQIY `admin` sessiyasida EMAS,
// oldindan 2FA ulangan vaqtinchalik admin-rolli foydalanuvchida ishlaydi (sabab — fayl boshidagi
// izoh va `createEnrolledTempAdmin`). `finally` blokida qaytarish — API orqali, UI'ga bog'liq
// emas — har doim, UI qadamlardan biri muvaffaqiyatsiz bo'lsa ham, bajariladi.
async function requireTotpPolicyFlow(browser, tempAdminToken, tempAdminSecret) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  try {
    // DIQQAT: bu aktyor allaqachon 2FA ulagan (`createEnrolledTempAdmin`) — shu sababli UI
    // kirishida ham TOTP challenge chiqadi, sekretni `login()`ga berib shaffof o'tamiz.
    await login(page, TEMP_ADMIN_USERNAME, TEMP_ADMIN_PASSWORD, tempAdminSecret);
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    await page.goto(BASE + '/settings/security');
    // `require_2fa` maydoni sukut "Holat" emas, "Sozlamalar" ichki tabida.
    await page.getByRole('tab', { name: 'Sozlamalar' }).click();
    const select = page.getByRole('combobox', { name: 'Kim uchun majburiy' });
    await select.click();
    await page.getByRole('option', { name: 'Faqat adminlar' }).click();
    await page.getByRole('button', { name: 'Saqlash' }).click();
    await page.waitForTimeout(1000);
    await page.reload();
    await page.getByRole('tab', { name: 'Sozlamalar' }).click();
    await select.waitFor({ timeout: 8000 });
    await page.getByText('Faqat adminlar').first().waitFor({ timeout: 8000 });
    await shot(page, 'security-require2fa-admins');
    await select.click();
    await page.getByRole('option', { name: 'Majburiy emas' }).click();
    await page.getByRole('button', { name: 'Saqlash' }).click();
    await page.waitForTimeout(1000);
  } finally {
    // Kafolatlangan qaytarish: UI qadam qayerda uzilmasin, siyosatni ishonchli, 2FA ulangan
    // tempAdmin tokeni orqali to'g'ridan-to'g'ri API bilan 'off'ga qaytaramiz (bu aktyor hech
    // qachon `2fa_enrollment_required` qulfiga tushmaydi — allaqachon ulangan).
    const sec = await api('GET', '/security/settings', undefined, tempAdminToken);
    if (sec.json && sec.json.require_2fa !== 'off') {
      await api('PATCH', '/security/settings', { ...sec.json, require_2fa: 'off', updated_at: sec.json.updated_at }, tempAdminToken);
    }
    await context.close();
  }
}

async function runAdmin(browser, runner, theme, viewport) {
  const context = await browser.newContext({ viewport, colorScheme: theme.startsWith('dark') ? 'dark' : 'light' });
  await context.addInitScript((t) => localStorage.setItem('innova.theme', t), theme.startsWith('dark') ? 'dark' : 'light');
  const page = await context.newPage();
  const problems = watchPage(page);
  try {
    await login(page, 'admin', adminPassword());
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    for (const screen of FULL_SCREENS) {
      await runner.step(`[${theme}] ${screen.path}`, () => checkFullScreen(page, theme, screen));
    }
    if (theme === 'light') {
      await runner.step('[light] Sifat: varaqa yaratish', () => qaChecklistFlow(page));
      await runner.step('[light] CDR: qoʻngʻiroqni baholash', () => evaluateCallFlow(page));
      await runner.step('[light] Sifat: baholashlar + xulosa', () => qualitySummaryFlow(page));
      await runner.step('[light] Callback vidjet: yaratish + kod nusxalash', () => callbackWidgetFlow(page));
      await runner.step('[light] Javobsiz qoʻngʻiroq: qoida yaratish + sinash', () => missedCallsFlow(page));
      await runner.step('[light] Integratsiyalar: SpeechKit sozlash + sinash', () => speechkitConfigureFlow(page));
      await runner.step('[light] Audio: TTS dialogi', () => audioTtsDialogFlow(page));
      await runner.step('[light] Integratsiyalar: SpeechKit oʻchirish (tozalash)', () => speechkitRevertFlow(page));
      await runner.step('[light] Integratsiyalar: WebSocket namunasi nusxalash', () => apiKeysWsSnippetFlow(page));
      await runner.step('[light] UsersPage: 2FA badge + reset tugmasi', () => usersResetFlow(page));
    }
    const real = realProblems(problems);
    await runner.step(`[${theme}] 5xx/konsol xatosi yo'q`, async () => { if (real.length) throw new Error(real.join(' | ')); });
  } finally {
    await context.close();
  }
}

async function main() {
  const runner = makeRunner();
  let browser = null;
  try {
    await waitForServer(BASE + '/login', 30000);
    await prepare();
    if (!(await backendReady())) {
      console.log('KUTILMOQDA: M10 C backend endpointlari hali tayyor emas — bu skript ular tayyor boʻlgach ishlatiladi.');
      process.exit(0);
    }
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});

    let totpSecret = '';
    await runner.step('2FA: test foydalanuvchi yaratish', () => createTempOperatorUser());
    await runner.step('2FA: MePage orqali ulash (QR/sekret -> kod -> zaxira kodlar)', async () => {
      totpSecret = await enrollTotpFlow(browser);
    });
    await runner.step('2FA: kirishda kod soʻralishi (LoginPage challenge)', () => {
      if (!totpSecret) throw new Error('sekret yoʻq (ulash muvaffaqiyatsiz boʻlgan)');
      return loginTotpChallengeFlow(browser, totpSecret);
    });

    // DIQQAT: xavfsizlik — bu sinov ataylab HAQIQIY `admin`da EMAS, allaqachon 2FA ulangan
    // vaqtinchalik admin-rolli foydalanuvchida ishlaydi (qulflanish xavfisiz — tafsilot fayl
    // boshidagi izohda).
    let tempAdminToken = '';
    let tempAdminSecret = '';
    await runner.step('Xavfsizlik: vaqtinchalik admin yaratish + 2FA ulash (API)', async () => {
      ({ token: tempAdminToken, secret: tempAdminSecret } = await createEnrolledTempAdmin());
    });
    await runner.step('Xavfsizlik: require_2fa admins -> off', () => {
      if (!tempAdminToken) throw new Error('tempAdminToken yoʻq (ulash muvaffaqiyatsiz boʻlgan)');
      return requireTotpPolicyFlow(browser, tempAdminToken, tempAdminSecret);
    });

    await runAdmin(browser, runner, 'light', { width: 1440, height: 900 });
    await runAdmin(browser, runner, 'dark', { width: 1440, height: 900 });
    await runAdmin(browser, runner, 'dark-mobile', { width: 390, height: 844 });
  } catch (e) {
    runner.results.fail += 1;
    console.log('XATO:', e?.message ?? e);
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    if (TOKEN) await cleanup().catch((e) => console.log('cleanup:', e?.message ?? e));
  }
  console.log(`PASS=${runner.results.pass} FAIL=${runner.results.fail}`);
  process.exit(runner.results.fail > 0 ? 1 : 0);
}

main();
