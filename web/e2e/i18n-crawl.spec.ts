import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

/**
 * Har sahifa (va undagi «Yangi …» dialogi) ekranida XOM i18n kalit qolmaganini tekshiradi:
 * `agentTimeoutRestartLabel`, `SECTION.CAPACITY` kabi — 1.0.21 da navbat formasi shunday chiqqan.
 * Kalitlar ro'yxati i18n fayllaridan olinadi; ekran matni (CSS uppercase bilan) katta-kichik harfsiz solishtiriladi.
 */

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');
const i18nFiles = readdirSync(join(SRC, 'i18n')).filter((f) => /^[a-z]+\.ts$/.test(f));
const KEYS = new Set<string>();
for (const f of i18nFiles) {
  for (const m of readFileSync(join(SRC, 'i18n', f), 'utf8').matchAll(/\b([a-zA-Z][a-zA-Z0-9_]*)\s*:/g)) KEYS.add(m[1]!.toLowerCase());
}
const ALL_PATHS = [...readFileSync(join(SRC, 'shell', 'screens.ts'), 'utf8').matchAll(/path: '([^']+)'/g)].map((m) => m[1]!);
const PATHS = process.env.CRAWL_ONLY ? ALL_PATHS.filter((p) => new RegExp(process.env.CRAWL_ONLY!).test(p)) : ALL_PATHS;

/** Kod namunalaridagi `ws.send(` kabi chaqiruvlar hisobga olinmaydi. camelCase kalit (kamida bitta katta harf ichida) yoki `a.b` nuqtali kalit — ikkalasi ham kalitlar ro'yxatida bo'lsa. */
/** Brend/mahsulot nomlari — camelCase bo'lsa ham xom kalit emas. */
const BRANDS = new Set(['amocrm', 'freepbx', 'iphone', 'macos', 'webrtc', 'ipv4', 'ipv6']);

function rawKeys(text: string): string[] {
  const found = new Set<string>();
  for (const w of text.match(/\b[a-z][a-z0-9]*(?:[A-Z][a-zA-Z0-9]*)+\b/g) ?? []) if (KEYS.has(w.toLowerCase()) && !BRANDS.has(w.toLowerCase())) found.add(w);
  for (const w of text.match(/\b[a-zA-Z][a-zA-Z]+\.[a-zA-Z][a-zA-Z]+\b(?!\s*\()/g) ?? []) {
    const [a, b] = w.toLowerCase().split('.');
    if (KEYS.has(a!) && KEYS.has(b!) && /[a-z]{3,}/.test(b!)) found.add(w);
  }
  return [...found];
}

async function setup(page: Page) {
  await page.goto('/');
  await expect(page).toHaveURL(/\/setup$/);
  await page.getByLabel('Oʻrnatish kodi').fill('e2e-setup-code');
  await page.getByLabel('Login').fill('e2e-admin');
  await page.getByLabel('Toʻliq ism').fill('E2E Administrator');
  await page.getByLabel('Parol').fill('SuperParol2026!');
  await page.getByRole('button', { name: 'Davom etish' }).click();
  await page.getByRole('button', { name: 'PBXʼni ishga tushirish' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

// Uzoq yurishda fake sessiya bir necha daqiqadan keyin tushib qoladi — har bo'lak yangi kirish bilan.
const CHUNK = 5;
const CHUNKS = Array.from({ length: Math.ceil(PATHS.length / CHUNK) }, (_, i) => PATHS.slice(i * CHUNK, (i + 1) * CHUNK));

for (const [n, chunk] of CHUNKS.entries()) test(`xom i18n kalit yoʻq — ${n + 1}-boʻlak (${chunk[0]} …)`, async ({ page }) => {
  test.setTimeout(chunk.length * 10_000 + 60_000);
  await setup(page);
  const problems: string[] = [];
  for (const path of chunk) {
    // goto sahifani qayta yuklaydi — fake rejimda sessiya yo'qoladi; SPA ichida o'tamiz.
    await page.evaluate((p) => { window.history.pushState({}, '', p); window.dispatchEvent(new PopStateEvent('popstate')); }, path);
    await page.waitForTimeout(700);
    const main = await page.locator('body').innerText();
    if (/Davom etish/.test(main) && !/Dialplan|Chiqish/.test(main)) { problems.push(`${path}: login sahifasiga tushdi (${page.url()})`); await page.screenshot({ path: `/tmp/crawl-login${path.replaceAll('/', '_')}.png` }); }
    for (const k of rawKeys(main)) problems.push(`${path}: ${k}`);
    // Har tab (Tarmoq → Ping, Firewall, Kirish …) — ichidagi matn ham.
    const tabs = page.getByRole('tab');
    for (let i = 0; i < Math.min(await tabs.count(), 12); i++) {
      await tabs.nth(i).click().catch(() => undefined);
      await page.waitForTimeout(300);
      for (const k of rawKeys(await page.locator('body').innerText())) problems.push(`${path} [tab ${i}]: ${k}`);
    }
    // Birinchi «Yangi …» / «… qoʻshish» tugmasi — forma dialogini ham tekshiramiz.
    const add = page.getByRole('button', { name: /^(\+\s*)?(Yangi\b|.*qoʻshish$)/ }).first();
    if (process.env.CRAWL_ONLY) console.log(path, 'add:', await add.isVisible().catch(() => false), await page.getByRole('button').allInnerTexts());
    if (await add.isVisible().catch(() => false)) {
      await add.click();
      await page.waitForTimeout(500);
      const dlg = page.getByRole('dialog').first();
      if (await dlg.isVisible().catch(() => false)) {
        if (process.env.CRAWL_ONLY) await page.screenshot({ path: `/tmp/crawl-${path.replaceAll('/', '_')}.png`, fullPage: true });
        for (const k of rawKeys(await dlg.innerText())) problems.push(`${path} [dialog]: ${k}`);
        await page.keyboard.press('Escape');
      }
    }
  }
  console.log(`tekshirildi: ${chunk.length} sahifa; topildi: ${problems.length}`);
  expect(problems).toEqual([]);
});
