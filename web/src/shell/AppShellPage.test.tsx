// Yuqori panel: telefon belgisi foydalanuvchining O'Z ichki raqamini koʻrsatadi (ilgari maketdan qolgan "101" edi);
// tizim holati / dialplan reviziyasi faqat adminga (operatorga endpoint 403 — abadiy "yuklanmoqda" boʻlib qolardi).
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { formatDateTimeShort } from '@/lib/time';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { AppShellPage } = await import('./AppShellPage');

describe('AppShellPage', () => {
  afterEach(() => useSession.getState().clear());

  it('operator: oʻz raqami (102) koʻrinadi, tizim holati va reviziya yashirin', async () => {
    await loginAs(client, 'operator'); // SEED_OPERATOR — 102 ga bogʻlangan.
    const health = vi.spyOn(client, 'systemHealth');
    renderPage(<AppShellPage title="Test">x</AppShellPage>);

    const chip = await screen.findByRole('button', { name: /softfon|softphone|telefon/i });
    expect(chip).toHaveTextContent('102');
    expect(screen.queryByText('101')).toBeNull();
    expect(screen.queryByText(/Dialplan/)).toBeNull();
    expect(health).not.toHaveBeenCalled();
  });

  it('admin ichki raqamsiz: telefon belgisi yoʻq', async () => {
    await loginAs(client, 'admin'); // SEED_ADMIN hech qaysi ichki raqamga bogʻlanmagan.
    renderPage(<AppShellPage title="Test">x</AppShellPage>);

    expect(await screen.findByText(/Dialplan/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /softfon|softphone|telefon/i })).toBeNull();
  });

  it('reviziya belgisi sana, vaqt va vaqt zonasini koʻrsatadi', async () => {
    await loginAs(client, 'admin');
    const createdAt = (await client.configRevisions(1)).items[0]!.created_at;
    renderPage(<AppShellPage title="Test">x</AppShellPage>);

    const zone = await screen.findByText('UTC+5');
    expect(zone).toHaveAttribute('title', 'Asia/Tashkent');
    expect(zone.closest('a')).toHaveTextContent(`${formatDateTimeShort(createdAt)} UTC+5`);
  });
});
