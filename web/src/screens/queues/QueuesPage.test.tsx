// Xatti-harakat testi — navbat aʼzosining dinamik belgisi va joriy holati (kirgan/pauzada/chiqgan)
// tahrirlash drawer'ida koʻrsatiladi (M2b §1). Qarang ../../../replica/m2b-contract.md §1.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { QueuesPage } = await import('./QueuesPage');

// i18n'da qatorlar ko'rinmay qolsa (noto'g'ri yo'l bilan chaqirilgan kalit yoki tarjimasiz enum qiymat)
// ishlab chiqarishda xuddi shu xomligicha ko'rinadi — shuni ushlab oladigan regex (0037 nazorati).
// Eslatma: avvalgi naqsh ([a-z]+[A-Z][A-Za-z]*(Label|...)) bitta "do'ng"li kalitlarni
// (masalan "nameHint") ushlamay o'tkazib yuborardi, chunki suffiksning o'z bosh harfi
// [A-Z] talabini "yeb qo'yardi" va keyin suffiks uchun harf qolmasdi. Keyingi "\b" talabi
// ham ishlamadi — DOM textContent'da elementlar orasida boʻsh joy boʻlmaydi, shu sabab
// "nameHintRaqam" kabi qo'shilib ketgan matnda so'z chegarasi hosil bo'lmaydi. Haqiqiy
// belgi: kichik harfdan keyin boʻsh joysiz ulangan katta harfli suffiks (camelCase chok),
// undan keyin yana kichik harf kelmasligi kerak (aks holda "Description"/"Optional" kabi
// haqiqiy soʻzlarni notoʻgʻri ushlab qolamiz).
const RAW_KEY_RE = /[a-z](Label|Desc|Hint|Title|Option)(?![a-z])/;
const RAW_SECTION_RE = /section\./i;
const RAW_ENUM_VALUES = new Set(['none', 'once', 'strict', 'loose', 'limit', 'more']);

describe('QueuesPage — aʼzo holati belgilari', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("pauzadagi dinamik aʼzo uchun «Dinamik» va «Pauzada» belgilari koʻrinadi", async () => {
    const user = userEvent.setup();
    const { items } = await client.listQueues();
    const queue = items[0]!;
    const memberId = queue.members[0]!.extension.id;
    await client.updateQueueMember(queue.id, memberId, { dynamic: true });
    await client.queueMemberAction(queue.id, memberId, 'pause', { reason: 'tushlik' });

    renderPage(<QueuesPage />);
    await user.dblClick(await screen.findByText(queue.name));

    expect(await screen.findByText('Pauzada')).toBeTruthy();
    expect(screen.getAllByText('Dinamik').length).toBeGreaterThan(0);
  });
});

describe('QueuesPage — «Yangi navbat» formasida xom i18n kalit yoki tarjimasiz enum yo‘q', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('dialog matnida xom kalit (fooLabel/SECTION.X) va tarjimasiz enum qiymat (none/once/strict/...) ko‘rinmaydi', async () => {
    const user = userEvent.setup();
    renderPage(<QueuesPage />);
    await user.click(await screen.findByRole('button', { name: 'Yangi navbat' }));

    const dialog = await screen.findByRole('dialog');
    const text = dialog.textContent ?? '';
    expect(text).not.toMatch(RAW_KEY_RE);
    expect(text).not.toMatch(RAW_SECTION_RE);

    // Bo'lim sarlavhalari va bir nechta FreePBX paritet maydonlari o'zbekchaga tarjima qilingan bo'lsin.
    for (const label of ['Umumiy', 'Vaqt va agentlar', 'Sigʻim', 'Eʼlonlar', 'Kengaytirilgan', 'Vazn', 'Avtomatik toʻldirish']) {
      expect(text).toContain(label);
    }

    // Har bir select'ning hozir tanlangan qiymati xom ingliz enum (none/once/strict/...) bo'lmasligi kerak.
    for (const combobox of within(dialog).getAllByRole('combobox')) {
      const shown = (combobox.textContent ?? '').trim().toLowerCase();
      expect(RAW_ENUM_VALUES.has(shown)).toBe(false);
    }

    // Har bir select ichidagi variantlar ham tarjima qilingan bo'lsin — xom "strict"/"loose"/"once"/"none" emas.
    for (const combobox of within(dialog).getAllByRole('combobox')) {
      await user.click(combobox);
      const options = await screen.findAllByRole('option');
      for (const option of options) {
        const shown = (option.textContent ?? '').trim().toLowerCase();
        expect(RAW_ENUM_VALUES.has(shown)).toBe(false);
      }
      await user.keyboard('{Escape}');
    }
  });
});
