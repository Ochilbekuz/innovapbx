import { expect, test, type Locator, type Page } from '@playwright/test';

/**
 * M1a stsenariysi: ish vaqti guruhi → IVR (tugma 1 → navbat) → kiruvchi marshrut
 * (maqsad = ish vaqti sharti) → oqim grafigi koʻrinadi. Interaksiyalar faqat klaviatura orqali
 * (fokus + Enter/Space/Tab/matn terish) — `.click()` ishlatilmaydi. Har bir qadamda konsolda
 * xato yoʻqligi tekshiriladi.
 */

const ADMIN_LOGIN = 'e2e-m1a-admin';
const ADMIN_PASSWORD = 'SuperParolM1a2026!';

// `fake-audio:<id>` — fake klientning audio oqimi uchun ataylab ishlatilgan soxta sxema
// (haqiqiy backend "real" rejimda http(s) manzil beradi). <audio> elementi mount boʻlganida
// brauzer avtomatik shu manzilni yuklashga urinadi va "net::ERR_UNKNOWN_URL_SCHEME" bilan
// muvaffaqiyatsiz tugaydi — bu fake rejimning bilinadigan, hujjatlashtirilgan cheklovi
// (build-log.md, S11), IVR tahrirlash oynasi audio preview bilan ochilganda doim yuzaga keladi.
const KNOWN_FAKE_AUDIO_SCHEME_ERROR = /ERR_UNKNOWN_URL_SCHEME/;

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error' && !KNOWN_FAKE_AUDIO_SCHEME_ERROR.test(m.text())) errors.push(`console.error: ${m.text()}`);
  });
  return errors;
}

/** Barcha `DestinationPicker`lar bir xil naqsh: trigger -> ochish -> qidirish -> Enter bilan tanlash. */
async function pickDestination(page: Page, scope: Locator, triggerName: RegExp, query: string) {
  const trigger = scope.getByRole('button', { name: triggerName });
  await trigger.focus();
  await page.keyboard.press('Enter');
  const search = page.getByLabel('Nom yoki raqam boʻyicha qidirish');
  await search.fill(query);
  // Filtrlangan ro'yxat chindan ham qayta chizilganini kutamiz — aks holda Enter
  // hali eski (bo'sh) ro'yxat holatiga tushib, hech narsa tanlamasligi mumkin (poyga sharti).
  await expect(page.getByRole('option', { name: new RegExp(query) })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(search).toBeHidden();
  // Popover yopilgandan keyin Radix fokusni triggerga qaytaradi (yoki DigitPad holatida trigger
  // butunlay unmount boʻladi) — bu amal tugaguncha qisqa kutamiz, aks holda keyingi qadamdagi
  // fokus/Enter hali shu oʻtish bilan poyga holatida qolib ketadi.
  await page.waitForTimeout(150);
}

/** `Qoʻshish`/submit tugmasini bosish — DestinationPicker yopilgach Radix fokusni triggerga
 * qaytarishi mumkin (poyga sharti), shu sabab fokusni ikki marta tasdiqlaymiz. */
async function submit(page: Page, button: Locator) {
  await button.focus();
  await page.waitForTimeout(150);
  await button.focus();
  await page.keyboard.press('Enter');
}

test('ish vaqti guruhi -> IVR (1->navbat) -> marshrut (vaqt sharti) -> oqim grafigi (faqat klaviatura)', async ({ page }) => {
  const errors = trackConsoleErrors(page);

  const queueName = 'E2E Sotuv navbati';
  const groupName = 'E2E Ish vaqti';
  const ivrName = 'E2E IVR';
  const tcName = 'E2E Ish vaqti sharti';
  const routeName = 'E2E Marshrut';

  // --- S01: Sehrgar ---
  await page.goto('/');
  await expect(page).toHaveURL(/\/setup$/);
  await page.getByLabel('Login').fill(ADMIN_LOGIN);
  await page.getByLabel('Toʻliq ism').fill('M1a E2E Administrator');
  await page.getByLabel('Parol').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Davom etish' }).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'PBXʼni ishga tushirish' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/dashboard$/);

  // --- S10: Navbat — IVRʼning 1-tugmasi shu yerga tushadi ---
  await page.getByRole('link', { name: 'Navbatlar' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/queues$/);
  await expect(page.getByRole('heading', { name: 'Navbatlar' })).toBeVisible();

  await page.getByRole('button', { name: 'Yangi navbat' }).focus();
  await page.keyboard.press('Enter');
  const queueDrawer = page.getByRole('dialog');
  await queueDrawer.getByLabel('Nom').fill(queueName);

  // Eʼtibor: bu combobox Field bilan oʻralmagan (hech qanday <label>ga bog'lanmagan) va ARIA
  // combobox roli "name from content" qoidasiga kirmaydi — shu sabab matn orqali filtrlaymiz, nom orqali emas.
  const addMember = queueDrawer.getByRole('combobox').filter({ hasText: 'Aʼzo qoʻshish' });
  await addMember.focus();
  await page.keyboard.press('Enter');
  const jahongirOption = page.getByRole('option', { name: /Jahongir/ });
  await expect(jahongirOption).toBeVisible(); // menyu ochilganini kutamiz — aks holda keyingi tasma bosilishlar hali yopiq triggerga tushib ketadi
  // Radix Selectʼda ro'yxat: + Aʼzo qoʻshish, 101..104, 105=Jahongir — joriy qiymatdan (__add, 0-indeks) 5 marta ArrowDown bilan yetamiz.
  // Har bosishdan keyin qisqa kutish kerak — aks holda Radixʼning ichki highlight holati ulgurmaydi.
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(80);
  }
  await page.keyboard.press('Enter');
  await expect(jahongirOption).toBeHidden();
  await expect(queueDrawer.getByText('Aʼzolar (1 ta)')).toBeVisible();
  await page.waitForTimeout(150); // Radix Select yopilgach fokus qaytarilishini kutamiz (poyga holati)

  await pickDestination(page, queueDrawer, /Kutish vaqti tugasa/, 'yakunlash');

  await submit(page, queueDrawer.getByRole('button', { name: 'Qoʻshish' }));

  await page.getByLabel('Navbatlar: qidirish').fill(queueName);
  await expect(page.getByRole('table').getByText(queueName)).toBeVisible();

  // --- S08: Ish vaqti — "E2E Ish vaqti" guruhi (dushanba 09:00–13:00 band) ---
  await page.getByRole('link', { name: 'Ish vaqti' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/timegroups$/);
  await expect(page.getByRole('heading', { name: 'Ish vaqti' })).toBeVisible();

  await page.getByRole('button', { name: 'Yangi guruh' }).focus();
  await page.keyboard.press('Enter');
  const groupDrawer = page.getByRole('dialog');
  await groupDrawer.getByLabel('Nom').fill(groupName);
  await page.keyboard.press('Tab'); // Nomʼdan WeekGridʼning kursor katakchasiga (Dushanba 09:00)
  await page.keyboard.press('Space'); // yoqamiz
  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('Shift+ArrowRight'); // 09:00–13:00 band boʻladi (dushanba)

  await submit(page, groupDrawer.getByRole('button', { name: 'Qoʻshish' }));

  await page.getByLabel('Ish vaqti guruhlari: qidirish').fill(groupName);
  await expect(page.getByRole('table').getByText(groupName)).toBeVisible();

  // --- S09: IVR — "1" tugmasi yangi navbatga yoʻnaltiriladi ---
  await page.getByRole('link', { name: 'IVR' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/ivr$/);
  await expect(page.getByRole('heading', { name: 'IVR menyular' })).toBeVisible();

  const newIvrButton = page.getByRole('button', { name: 'Yangi IVR' });
  await expect(newIvrButton).toBeEnabled(); // audio kutubxonasi yuklanguncha tugma oʻchiq boʻladi
  await newIvrButton.focus();
  await page.keyboard.press('Enter');
  const ivrDrawer = page.getByRole('dialog');
  await ivrDrawer.getByLabel('Nom').fill(ivrName);

  await ivrDrawer.getByRole('button', { name: 'Band etilmagan' }).first().focus();
  await page.keyboard.press('Enter');
  await pickDestination(page, ivrDrawer, /Tugma 1/, queueName);

  await pickDestination(page, ivrDrawer, /Vaqt tugaganda/, 'yakunlash');
  await pickDestination(page, ivrDrawer, /Notoʻgʻri tugma boʻlganda/, 'Band ohangi');

  await submit(page, ivrDrawer.getByRole('button', { name: 'Qoʻshish' }));

  await page.getByLabel('IVR menyular: qidirish').fill(ivrName);
  await expect(page.getByRole('table').getByText(ivrName)).toBeVisible();

  // --- S08: Ish vaqti — "Shartlar" tabida yangi guruh + yangi IVRʼga bogʻlangan shart ---
  await page.getByRole('link', { name: 'Ish vaqti' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/timegroups$/);

  await page.getByRole('tab', { name: 'Shartlar' }).focus();
  await page.keyboard.press('Enter');

  await page.getByRole('button', { name: 'Yangi shart' }).focus();
  await page.keyboard.press('Enter');
  const tcDrawer = page.getByRole('dialog');
  await tcDrawer.getByLabel('Nom').fill(tcName);

  const groupSelect = tcDrawer.getByLabel('Ish vaqti guruhi');
  await groupSelect.focus();
  await page.keyboard.press('e'); // "E2E Ish vaqti" — 'e' bilan boshlanadigan yagona guruh

  await pickDestination(page, tcDrawer, /Ochiq boʻlganda/, ivrName);
  await pickDestination(page, tcDrawer, /Yopiq boʻlganda/, 'yakunlash');

  await submit(page, tcDrawer.getByRole('button', { name: 'Qoʻshish' }));

  await page.getByLabel('Ish vaqti shartlari: qidirish').fill(tcName);
  await expect(page.getByRole('table').getByText(tcName)).toBeVisible();

  // --- S07: Kiruvchi marshrut — maqsad = yangi ish vaqti sharti ---
  await page.getByRole('link', { name: 'Kiruvchi marshrutlar' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/inbound$/);

  await page.getByRole('button', { name: 'Yangi marshrut' }).focus();
  await page.keyboard.press('Enter');
  const routeDialog = page.getByRole('dialog');
  await routeDialog.getByLabel('Nom').fill(routeName);
  // "Har qanday DID" yoqilgan holda (did=null, cid=null) seeddagi "Qabul (hammasi)" marshruti bilan
  // 409 did_conflict beradi — shu sabab aniq DID beramiz (m0.spec.ts bilan bir xil naqsh).
  const didToggle = routeDialog.getByRole('switch', { name: 'Har qanday DID' });
  await didToggle.focus();
  await page.keyboard.press('Space');
  await routeDialog.getByRole('textbox', { name: 'DID' }).fill('998712005500');
  await pickDestination(page, routeDialog, /Manzil/, tcName);

  await submit(page, routeDialog.getByRole('button', { name: 'Qoʻshish' }));

  await page.getByLabel('Kiruvchi marshrutlar: qidirish').fill(routeName);
  const routeRow = page.getByRole('table').getByRole('row', { name: new RegExp(routeName) });
  await expect(routeRow).toBeVisible();

  // --- Qoʻngʻiroq yoʻli grafigi: marshrut -> shart -> IVR -> navbat, halqa/singan manzilsiz ---
  await routeRow.getByRole('button', { name: new RegExp(`${routeName}: qoʻngʻiroq yoʻlini koʻrish`) }).focus();
  await page.keyboard.press('Enter');

  const flowFigure = page.getByRole('dialog').locator('figure');
  await expect(flowFigure.getByText('Yoʻl toza')).toBeVisible();
  await expect(flowFigure.getByText(ivrName)).toBeVisible();
  await expect(flowFigure.getByText(queueName)).toBeVisible();

  expect(errors, `Konsolda xato bo'lmasligi kerak:\n${errors.join('\n')}`).toEqual([]);
});
