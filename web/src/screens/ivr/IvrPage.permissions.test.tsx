// M7 (replica/m7-roles-contract.md §4): maxsus rolda hudud ruxsati bo'yicha «faqat ko'rish» rejimi.
// Ilgari sahifa `usePermission('routes.manage')` ishlatardi — bunday satr hech bir rolda yo'q,
// shuning uchun `routing:edit` li foydalanuvchida ham tugmalar yashirin qolardi.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { IvrPage } = await import('./IvrPage');

const READ_ONLY = /faqat koʻrish mumkin/;

function withPermissions(permissions: string[]) {
  const user = useSession.getState().user!;
  useSession.getState().setUser({ ...user, role: 'Nazoratchi', permissions });
}

describe('IvrPage — hudud ruxsatlari', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('routing:view — faqat koʻrish ogohlantirishi, «Yangi IVR» yoʻq', async () => {
    withPermissions(['routing:view']);
    renderPage(<IvrPage />);
    expect(await screen.findByText(READ_ONLY)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Yangi IVR/ })).toBeNull();
  });

  it('routing:edit — boshqarish mumkin (ogohlantirish yoʻq)', async () => {
    withPermissions(['routing:edit']);
    renderPage(<IvrPage />);
    expect(await screen.findByRole('button', { name: /Yangi IVR/ })).toBeTruthy();
    expect(screen.queryByText(READ_ONLY)).toBeNull();
  });

  it('boshqa hududda edit — routing sahifasida baribir faqat koʻrish', async () => {
    withPermissions(['connect:edit', 'routing:view']);
    renderPage(<IvrPage />);
    expect(await screen.findByText(READ_ONLY)).toBeTruthy();
  });
});
