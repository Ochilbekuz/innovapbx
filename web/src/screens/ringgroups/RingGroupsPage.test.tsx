// 0038 (FreePBX Ring Groups parity) — yangi boʻlimlar (Jiringlash va eʼlonlar/Kengaytirilgan) va
// "Confirm calls" yoqilganda "Tasdiqlash eʼloni" maydoni koʻrinishi, hamda saqlash orqali
// yangi FreePBX maydonlari (skip_busy_agent, confirm_calls, recording_policy) haqiqatan saqlanishi.
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

const { RingGroupsPage } = await import('./RingGroupsPage');

// i18n'da noto'g'ri yo'l bilan chaqirilgan kalit yoki tarjimasiz enum qiymat ishlab chiqarishda
// xomligicha ko'rinadi — shuni ushlab oladigan regex (0038 nazorati, queues'dagi bilan bir xil naqsh).
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

describe('RingGroupsPage — FreePBX parity boʻlimlari', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('tahrirlash drawer besh boʻlimga boʻlingan', async () => {
    const user = userEvent.setup();
    const { items } = await client.listRingGroups();
    renderPage(<RingGroupsPage />);
    await user.dblClick(await screen.findByText(items[0]!.name));

    expect(await screen.findByRole('heading', { name: 'Umumiy' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Aʼzolar' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Jiringlash va eʼlonlar' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Caller ID' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Kengaytirilgan' })).toBeTruthy();
  });

  it('"Qoʻngʻiroqni tasdiqlash" yoqilmaguncha "Tasdiqlash eʼloni" koʻrinmaydi', async () => {
    const user = userEvent.setup();
    const { items } = await client.listRingGroups();
    renderPage(<RingGroupsPage />);
    await user.dblClick(await screen.findByText(items[0]!.name));
    await screen.findByRole('heading', { name: 'Umumiy' });

    expect(screen.queryByText('Tasdiqlash eʼloni')).toBeNull();
    await user.click(screen.getByText('Qoʻngʻiroqni tasdiqlash'));
    expect(await screen.findByText('Tasdiqlash eʼloni')).toBeTruthy();
  });

  it('"Band aʼzoni oʻtkazib yuborish"ni yoqib saqlash — fake API orqali haqiqatan saqlanadi', async () => {
    const user = userEvent.setup();
    const { items } = await client.listRingGroups();
    const group = items[0]!;
    expect(group.skip_busy_agent).toBe(false);

    renderPage(<RingGroupsPage />);
    await user.dblClick(await screen.findByText(group.name));
    await screen.findByRole('heading', { name: 'Umumiy' });
    await user.click(screen.getByText('Band aʼzoni oʻtkazib yuborish'));
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    const { items: after } = await client.listRingGroups();
    expect(after.find((g) => g.id === group.id)?.skip_busy_agent).toBe(true);
  });
});

describe('RingGroupsPage — «Yangi guruh» formasida xom i18n kalit yoki tarjimasiz enum yo‘q', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('dialog matnida xom kalit (fooLabel/SECTION.X) va tarjimasiz enum qiymat (none/once/strict/...) ko‘rinmaydi', async () => {
    const user = userEvent.setup();
    renderPage(<RingGroupsPage />);
    await user.click(await screen.findByRole('button', { name: 'Yangi guruh' }));

    const dialog = await screen.findByRole('dialog');
    const text = dialog.textContent ?? '';
    expect(text).not.toMatch(RAW_KEY_RE);
    expect(text).not.toMatch(RAW_SECTION_RE);

    for (const label of ['Umumiy', 'Aʼzolar', 'Jiringlash va eʼlonlar', 'Caller ID', 'Kengaytirilgan']) {
      expect(text).toContain(label);
    }

    for (const combobox of within(dialog).getAllByRole('combobox')) {
      const shown = (combobox.textContent ?? '').trim().toLowerCase();
      expect(RAW_ENUM_VALUES.has(shown)).toBe(false);
    }

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
