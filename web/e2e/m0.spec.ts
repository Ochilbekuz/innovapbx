import { expect, test, type Page } from '@playwright/test';

/**
 * M0 vertikal kesimining asosiy yo'li, boshidan oxirigacha: sehrgar → kirish → ichki raqam →
 * trunk → kiruvchi marshrut → qo'ngʻiroqlar tarixi. Interaksiyalar faqat klaviatura orqali
 * (fokus + Enter/Space/Tab) — `.click()` ishlatilmaydi. Har bir qadamda konsolda xato yo'qligi tekshiriladi.
 */

const ADMIN_LOGIN = 'e2e-admin';
const ADMIN_PASSWORD = 'SuperParol2026!';

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`console.error: ${m.text()}`);
  });
  return errors;
}

test('setup -> login -> ichki raqam -> trunk -> marshrut -> tarix (faqat klaviatura)', async ({ page }) => {
  const errors = trackConsoleErrors(page);

  // --- S01: Sehrgar ---
  await page.goto('/');
  await expect(page).toHaveURL(/\/setup$/);

  await page.getByLabel('Oʻrnatish kodi').fill('e2e-setup-code');
  await page.getByLabel('Login').fill(ADMIN_LOGIN);
  await page.getByLabel('Toʻliq ism').fill('E2E Administrator');
  await page.getByLabel('Parol').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Davom etish' }).focus();
  await page.keyboard.press('Enter');

  // Ikkinchi qadam — tarmoq. Standart qiymatlar yaroqli, shunchaki yuboramiz.
  const finishBtn = page.getByRole('button', { name: 'PBXʼni ishga tushirish' });
  await finishBtn.focus();
  await page.keyboard.press('Enter');

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: 'Boshqaruv paneli' })).toBeVisible();

  // --- S02: Chiqish va qayta kirish (kirish oqimini sinash uchun) ---
  const userMenuBtn = page.getByRole('button', { name: /Foydalanuvchi menyusi/ });
  await userMenuBtn.focus();
  await page.keyboard.press('Enter');
  const logoutBtn = page.getByRole('button', { name: 'Chiqish' });
  await logoutBtn.focus();
  await page.keyboard.press('Enter');

  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Login').fill(ADMIN_LOGIN);
  await page.getByLabel('Parol').fill(ADMIN_PASSWORD);
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/dashboard$/);

  // --- S04: Ichki raqam yaratish ---
  await page.getByRole('link', { name: 'Ichki raqamlar' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/extensions$/);

  await page.getByRole('button', { name: 'Yangi ichki raqam' }).focus();
  await page.keyboard.press('Enter');
  const extName = 'E2E Sinov Foydalanuvchi';
  const extDialog = page.getByRole('dialog');
  await extDialog.getByLabel('Nom').fill(extName);
  const createExtBtn = extDialog.getByRole('button', { name: 'Yaratish' });
  await createExtBtn.focus();
  await page.keyboard.press('Enter');

  // SIP maʼlumotlari ko'rsatiladi — yopamiz.
  const sipCloseBtn = page.getByRole('button', { name: 'Saqladim, yopish' });
  await sipCloseBtn.focus();
  await page.keyboard.press('Enter');

  // Ro'yxat sahifalangan — yangi yozuv 2-sahifada bo'lishi mumkin, shu sabab filtrlab tekshiramiz.
  // Jadvalga qamrab olamiz — bildirishnoma/toast matnida ham xuddi shu nom chiqishi mumkin.
  await page.getByLabel('Ichki raqamlar: qidirish').fill(extName);
  await expect(page.getByRole('table').getByText(extName)).toBeVisible();

  // --- S06: Trunk yaratish ---
  await page.getByRole('link', { name: 'Trunklar' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/trunks$/);

  await page.getByRole('button', { name: 'Yangi trunk' }).focus();
  await page.keyboard.press('Enter');
  const trunkName = 'E2E Trunk';
  const trunkDialog = page.getByRole('dialog');
  await trunkDialog.getByLabel('Nom').fill(trunkName);
  await trunkDialog.getByLabel('Host').fill('sip.e2e-sinov.uz');
  const addTrunkBtn = trunkDialog.getByRole('button', { name: 'Qoʻshish' });
  await addTrunkBtn.focus();
  await page.keyboard.press('Enter');

  await page.getByLabel('Trunklar: qidirish').fill(trunkName);
  await expect(page.getByRole('table').getByText(trunkName)).toBeVisible();

  // --- S07: Kiruvchi marshrut yaratish, yangi ichki raqamga yoʻnaltirilgan ---
  await page.getByRole('link', { name: 'Kiruvchi marshrutlar' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/inbound$/);

  await page.getByRole('button', { name: 'Yangi marshrut' }).focus();
  await page.keyboard.press('Enter');
  const routeName = 'E2E Marshrut';
  const routeDialog = page.getByRole('dialog');
  await routeDialog.getByLabel('Nom').fill(routeName);

  const didToggle = routeDialog.getByRole('switch', { name: 'Har qanday DID' });
  await didToggle.focus();
  await page.keyboard.press('Space'); // o'chiramiz — DID maydoni ochiladi
  await routeDialog.getByRole('textbox', { name: 'DID' }).fill('998712009999');

  const destTrigger = routeDialog.getByRole('button', { name: /Manzil/ });
  await destTrigger.focus();
  await page.keyboard.press('Enter');
  const destSearch = page.getByLabel('Nom yoki raqam boʻyicha qidirish');
  await destSearch.fill(extName);
  // Filtrlangan ro'yxat chindan ham qayta chizilganini kutamiz — aks holda Enter
  // hali eski (bo'sh) ro'yxat holatiga tushib, hech narsa tanlamasligi mumkin (poyga sharti).
  await expect(page.getByRole('option', { name: new RegExp(extName) })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(destSearch).toBeHidden();
  await expect(destTrigger).toHaveText(new RegExp(extName));

  const addRouteBtn = routeDialog.getByRole('button', { name: 'Qoʻshish' });
  await addRouteBtn.focus();
  await page.keyboard.press('Enter');

  await page.getByLabel('Kiruvchi marshrutlar: qidirish').fill(routeName);
  const routeRow = page.getByRole('table').getByRole('row', { name: new RegExp(routeName) });
  await expect(routeRow).toBeVisible();
  await expect(routeRow.getByText(extName)).toBeVisible();

  // --- S12: Qo'ngʻiroqlar tarixi ---
  await page.getByRole('link', { name: 'Qoʻngʻiroqlar tarixi' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/cdr$/);
  await expect(page.getByRole('heading', { name: 'Qoʻngʻiroqlar tarixi' })).toBeVisible();
  await expect(page.getByRole('table')).toBeVisible();

  expect(errors, `Konsolda xato bo'lmasligi kerak:\n${errors.join('\n')}`).toEqual([]);
});
