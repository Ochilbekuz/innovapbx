// M3a §5 — softfon skrinshotlari HAQIQIY stek va Chromium bilan (light + dark):
//   m3a-chip-<t>.png (header chipi), m3a-panel-idle-<t>.png, m3a-incoming-<t>.png, m3a-talking-<t>.png.
// A (M3A_A_USER) B raqamiga (M3A_B_NUMBER) qo'ng'iroq qiladi; B kiruvchi oynani ko'radi va javob beradi.
// Ishga tushirish (stek ko'tarilgan, operatorlar paroli o'zgartirilgan bo'lsin):
//   CHROME_PATH=... M3A_A_USER=.. M3A_B_USER=.. M3A_PASS=.. M3A_B_NUMBER=103 node web/scripts/m3a-real-check.mjs
import path from 'node:path';
import { SHOTS, clickTestId, dial, ensurePanel, launchBrowser, openUser, waitState } from './m3a-browser.mjs';

const env = (k) => {
  const v = process.env[k];
  if (!v) throw new Error(`${k} berilmagan`);
  return v;
};
const A = env('M3A_A_USER');
const B = env('M3A_B_USER');
const PASS = env('M3A_PASS');
const B_NUMBER = env('M3A_B_NUMBER');

const shot = (page, name) => page.screenshot({ path: path.join(SHOTS, `m3a-${name}.png`) });

/** Element atrofidagi header bo'lagi (chip yolg'iz kichik rasm bo'lib qolmasin — kontekst bilan). */
async function shotAround(page, locator, name) {
  const box = await locator.boundingBox();
  const vp = page.viewportSize();
  const x = Math.max(0, box.x - 360);
  const width = Math.min(vp.width - x, box.width + 400);
  await page.screenshot({ path: path.join(SHOTS, `m3a-${name}.png`), clip: { x, y: 0, width, height: Math.max(64, box.y + box.height + 12) } });
}

async function round(browser, theme) {
  const a = await openUser(browser, { user: A, pass: PASS, theme });
  const b = await openUser(browser, { user: B, pass: PASS, theme });
  try {
    await waitState(a.page, (s) => s.connection === 'registered');
    await waitState(b.page, (s) => s.connection === 'registered');
    await shotAround(a.page, a.page.getByTestId('softphone-chip'), `chip-${theme}`);
    await ensurePanel(a.page);
    await a.page.waitForTimeout(400);
    await shot(a.page, `panel-idle-${theme}`);
    await dial(a.page, B_NUMBER);
    await waitState(b.page, (s) => s.phase === 'incoming', 15000);
    await b.page.getByTestId('softphone-incoming-from').waitFor();
    await b.page.waitForTimeout(400);
    await shot(b.page, `incoming-${theme}`);
    await clickTestId(b.page, 'answer');
    await waitState(b.page, (s) => s.phase === 'talking', 15000);
    await b.page.waitForTimeout(2500); // taymer 0:02 ko'rinsin
    await shot(b.page, `talking-${theme}`);
    await clickTestId(a.page, 'hangup');
    await waitState(b.page, (s) => s.phase === null, 10000);
    const errors = [...a.errors, ...b.errors].filter((e) => !/favicon/i.test(e));
    console.log(`${theme}: 4 skrinshot; konsol xatolari: ${errors.length ? errors.join(' | ') : 'yoʻq'}`);
  } finally {
    await a.context.close();
    await b.context.close();
  }
}

const browser = await launchBrowser();
try {
  for (const theme of ['light', 'dark']) await round(browser, theme);
} finally {
  await browser.close();
}
