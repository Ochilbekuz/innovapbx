// M3a §5 isboti — HAQIQIY Chromium (Playwright) boshqaruvchisi. `scripts/m3a-proof.sh` uni fon jarayon
// sifatida ishga tushiradi va 127.0.0.1:${M3A_CTL_PORT:-8799} dagi kichik HTTP boshqaruv orqali
// buyruq beradi (har foydalanuvchi — alohida browser context: alohida sessiya, alohida `navigator.locks`).
//
//   GET /open?who=A&user=..&pass=..   kirish (sahifa `?diag=1` bilan) -> {"ok":true}
//   GET /state?who=A                  window.__innovaSoftphone.state() + chip bor/yo'q
//   GET /stats?who=A                  window.__innovaSoftphone.stats() (RTCPeerConnection getStats)
//   GET /dial?who=A&num=103           panel -> tergich -> «Qo'ng'iroq»
//   GET /click?who=A&id=answer        data-testid="softphone-<id>" tugmasini bosadi (answer/reject/hangup/mute/hold)
//   GET /dtmf?who=A&d=1               gaplashish paytidagi tergich tugmasi
//   GET /transfer?who=B&num=102       transfer paneli -> raqam -> softphone-transfer
//   GET /reload?who=A                 sahifani qayta yuklash
//   GET /shot?who=A&name=x            replica/clone-screens/<name>.png
//   GET /close?who=A | /quit
//
// Ishga tushirish: CHROME_PATH=... node web/scripts/m3a-browser.mjs  (BASE sukut http://127.0.0.1:8711)
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
export const SHOTS = path.join(ROOT, '..', '..', 'replica', 'clone-screens');
export const BASE = process.env.M3A_BASE ?? 'http://127.0.0.1:8711';
const PORT = Number(process.env.M3A_CTL_PORT ?? 8799);

export const CHROME_ARGS = [
  '--use-fake-device-for-media-stream',
  '--use-fake-ui-for-media-stream',
  '--autoplay-policy=no-user-gesture-required',
];

export async function launchBrowser() {
  return chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    args: CHROME_ARGS,
  });
}

/** Yangi context + kirish. `theme` — 'light' | 'dark' (localStorage `innova.theme`), til — `pbx.language`. */
export async function openUser(browser, { user, pass, theme = 'light', lang = 'uz' }) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ['microphone'],
    colorScheme: theme,
  });
  await context.addInitScript(([t, l]) => {
    localStorage.setItem('innova.theme', t);
    if (!localStorage.getItem('pbx.language')) localStorage.setItem('pbx.language', l);
  }, [theme, lang]);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  const frames = [];
  // SIP darajasidagi iz (birinchi qator) — isbot muvaffaqiyatsiz bo'lsa sabab shu yerda ko'rinadi.
  page.on('websocket', (ws) => {
    const first = (p) => String(p).split('\r\n', 1)[0];
    ws.on('framesent', (f) => frames.push(`> ${first(f.payload)}`));
    ws.on('framereceived', (f) => frames.push(`< ${first(f.payload)}`));
    ws.on('close', () => frames.push('# ws close'));
  });
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`console.${m.type()}: ${m.text()}`); });
  await page.goto(`${BASE}/login?diag=1`);
  await page.getByLabel('Login').fill(user);
  await page.getByLabel('Parol').fill(pass);
  await page.getByRole('button', { name: 'Kirish' }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 15000 });
  // `?diag=1` kirishdan keyingi yo'naltirishda yo'qoladi — diagnostikani yoqish uchun qayta ochamiz.
  await page.goto(`${page.url().split('?')[0]}?diag=1`);
  await page.waitForFunction(() => Boolean(window.__innovaSoftphone), null, { timeout: 15000 });
  return { context, page, errors, frames };
}

export async function softphoneState(page) {
  return page.evaluate(() => {
    const s = window.__innovaSoftphone?.state?.() ?? null;
    return { ...s, chip: Boolean(document.querySelector('[data-testid="softphone-chip"]')) };
  });
}

export async function waitState(page, predicate, timeoutMs = 20000) {
  const start = Date.now();
  let last = null;
  while (Date.now() - start < timeoutMs) {
    last = await softphoneState(page);
    if (predicate(last)) return last;
    await page.waitForTimeout(250);
  }
  throw new Error(`holat kutildi, oxirgisi: ${JSON.stringify(last)}`);
}

export async function ensurePanel(page) {
  if (await page.locator('section header [data-testid="softphone-state"]').isVisible().catch(() => false)) return;
  await page.getByTestId('softphone-chip').click();
  await page.locator('section header [data-testid="softphone-state"]').waitFor({ timeout: 5000 });
}

export async function dial(page, num) {
  await ensurePanel(page);
  await page.getByTestId('softphone-dial-input').fill(num);
  await page.getByTestId('softphone-call').click();
}

export async function clickTestId(page, id) {
  await ensurePanel(page);
  await page.getByTestId(`softphone-${id}`).click({ timeout: 10000 });
}

export async function pressDtmf(page, digit) {
  await ensurePanel(page);
  await page.locator('section').getByRole('button', { name: digit, exact: true }).click();
}

export async function transfer(page, num) {
  await ensurePanel(page);
  const input = page.getByTestId('softphone-transfer-input');
  if (!(await input.isVisible().catch(() => false))) {
    await page.getByTestId('softphone-transfer-toggle').click();
  }
  await input.fill(num);
  await page.getByTestId('softphone-transfer').click();
}

// ------------------------------------------------------------------ HTTP boshqaruv
async function serve() {
  const browser = await launchBrowser();
  const users = new Map();
  const need = (who) => {
    const u = users.get(who);
    if (!u) throw new Error(`foydalanuvchi ${who} ochilmagan`);
    return u;
  };
  const handlers = {
    open: async (q) => {
      if (users.has(q.who)) await users.get(q.who).context.close();
      users.set(q.who, await openUser(browser, { user: q.user, pass: q.pass, theme: q.theme ?? 'light' }));
      return { ok: true };
    },
    state: async (q) => softphoneState(need(q.who).page),
    stats: async (q) => need(q.who).page.evaluate(() => window.__innovaSoftphone.stats()),
    dial: async (q) => { await dial(need(q.who).page, q.num); return { ok: true }; },
    click: async (q) => { await clickTestId(need(q.who).page, q.id); return { ok: true }; },
    dtmf: async (q) => { await pressDtmf(need(q.who).page, q.d); return { ok: true }; },
    transfer: async (q) => { await transfer(need(q.who).page, q.num); return { ok: true }; },
    text: async (q) => ({ text: await need(q.who).page.getByTestId(q.id).first().textContent({ timeout: 5000 }) }),
    reload: async (q) => {
      const { page } = need(q.who);
      await page.reload();
      await page.waitForFunction(() => Boolean(window.__innovaSoftphone), null, { timeout: 15000 });
      return { ok: true };
    },
    shot: async (q) => {
      await need(q.who).page.screenshot({ path: path.join(SHOTS, `${q.name}.png`) });
      return { ok: true };
    },
    errors: async (q) => ({ errors: need(q.who).errors }),
    frames: async (q) => ({ frames: need(q.who).frames.slice(-Number(q.n ?? 40)) }),
    close: async (q) => {
      await need(q.who).context.close();
      users.delete(q.who);
      return { ok: true };
    },
  };
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    const name = url.pathname.slice(1);
    const q = Object.fromEntries(url.searchParams);
    if (name === 'quit') {
      res.end('{"ok":true}');
      setTimeout(() => process.exit(0), 5000).unref(); // browser.close() osilib qolsa ham chiqamiz
      await browser.close().catch(() => undefined);
      server.close();
      process.exit(0);
    }
    try {
      const fn = handlers[name];
      if (!fn) throw new Error(`noma'lum buyruq: ${name}`);
      const out = await fn(q);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(out));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e?.message ?? e) }));
    }
  });
  server.listen(PORT, '127.0.0.1', () => console.log(`m3a-browser tayyor :${PORT}`));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  serve().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
