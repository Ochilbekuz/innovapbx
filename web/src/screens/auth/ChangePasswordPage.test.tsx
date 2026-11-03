// Xatti-harakat testi — majburiy parol almashtirish oqimi: `must_change_password: true` boʻlsa `RequireAuth`
// boshqa marshrutlardan shu yerga qaytaradi; toʻgʻri yangi parol kiritilgach rolga mos sahifaga oʻtadi va
// flag tozalanadi (M2b §3). Qarang ../../../replica/m2b-contract.md §3.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { ChangePasswordPage } = await import('./ChangePasswordPage');
const { RequireAuth } = await import('@/auth/guards');

function renderWithRoutes(initialPath: string) {
  // `staleTime: Infinity` — pastda bergan "sehrgar bajarilgan" keshi orqa fonda qayta soʻralib,
  // fake klientning haqiqiy (hali `setup()` chaqirilmagan) `needed: true` holati bilan ustidan
  // yozilib ketmasligi uchun kerak.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  // Sehrgar (`/setup`) seed maʼlumotda allaqachon bajarilgan deb hisoblanadi — bu test faqat
  // `must_change_password` yoʻnalishini tekshiradi, `client.setup()`ni chaqirish esa fake klientda
  // yangi adminga qattiq yozilgan `u-admin` id orqali SEED_ADMIN parolini ustidan yozib yuboradi
  // (alohida xato, M2b doirasidan tashqarida — hisobotda qayd etiladi).
  queryClient.setQueryData(['setup-state'], { needed: false });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/change-password" element={<RequireAuth><ChangePasswordPage /></RequireAuth>} />
          <Route path="/me" element={<RequireAuth><div>Mening kabinetim</div></RequireAuth>} />
          <Route path="/dashboard" element={<RequireAuth><div>Boshqaruv paneli</div></RequireAuth>} />
          <Route path="/cdr" element={<RequireAuth><div>Qoʻngʻiroqlar tarixi</div></RequireAuth>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Admin sifatida yangi (operator) foydalanuvchi yaratadi — fake klientda u `must_change_password: true` bilan tug'iladi — va unga kiradi. */
async function createAndLoginAsFreshUser(username: string) {
  await loginAs(client, 'admin');
  await client.createUser({
    username, full_name: 'Yangi Foydalanuvchi', password: 'Boshlangich12!',
    role: 'operator', extension_id: null, language: 'uz', email: null,
  });
  const res = await client.login(username, 'Boshlangich12!');
  if (res.status !== 'ok') throw new Error('2FA kutilmagan edi');
  expect(res.user.must_change_password).toBe(true);
  useSession.setState({ access: res.access, refresh: res.refresh, user: res.user });
}

describe('ChangePasswordPage — majburiy parol almashtirish', () => {
  afterEach(() => useSession.getState().clear());

  it('must_change_password=true boʻlsa — boshqa marshrutga oʻtishga urinish /change-password ga qaytaradi', async () => {
    await createAndLoginAsFreshUser('yangi1');
    renderWithRoutes('/dashboard');

    expect(await screen.findByText('Parolni oʻzgartirish')).toBeTruthy();
    expect(screen.queryByText('Boshqaruv paneli')).toBeNull();
  });

  it('toʻgʻri joriy va yangi parol kiritilgach — rolga mos boshlangʻich sahifaga oʻtadi, flag tozalanadi', async () => {
    await createAndLoginAsFreshUser('yangi2');
    const user = userEvent.setup();
    renderWithRoutes('/change-password');

    await user.type(await screen.findByLabelText(/^Joriy parol/), 'Boshlangich12!');
    await user.type(screen.getByLabelText(/^Yangi parol/), 'YangiParol123!');
    await user.click(screen.getByRole('button', { name: 'Parolni oʻzgartirish va davom etish' }));

    // "yangi" — operator (`calls:read:own`); M7dan keyin boshlangʻich sahifa — birinchi koʻrinadigan
    // ekran, bu operator uchun /cdr (qarang ../../../replica/m7-roles-contract.md §4, `homeFor`).
    expect(await screen.findByText('Qoʻngʻiroqlar tarixi')).toBeTruthy();
    expect(useSession.getState().user?.must_change_password).toBe(false);
  });

  it('parol almashgach — server qaytargan YANGI refresh saqlanadi (eskisi bekor, sessiya chiqib ketmaydi)', async () => {
    await createAndLoginAsFreshUser('yangi3');
    const oldRefresh = useSession.getState().refresh;
    const user = userEvent.setup();
    renderWithRoutes('/change-password');

    await user.type(await screen.findByLabelText(/^Joriy parol/), 'Boshlangich12!');
    await user.type(screen.getByLabelText(/^Yangi parol/), 'YangiParol123!');
    await user.click(screen.getByRole('button', { name: 'Parolni oʻzgartirish va davom etish' }));

    expect(await screen.findByText('Qoʻngʻiroqlar tarixi')).toBeTruthy();
    const { refresh } = useSession.getState();
    expect(refresh).toBeTruthy();
    expect(refresh).not.toBe(oldRefresh);
    expect(window.localStorage.getItem('innova.refresh')).toBe(refresh);
  });
});
