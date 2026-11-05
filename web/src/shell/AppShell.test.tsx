// Yon menyu: akkordeon (bir vaqtda bitta guruh ochiq), «qotirilgan»/«yig'ilgan» (rail) rejim
// `localStorage['innova.nav.mode']`'da saqlanadi, Ctrl/⌘+B almashtiradi.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link } from 'react-router-dom';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { AppShellPage } = await import('./AppShellPage');

const groupBtn = (name: RegExp) => screen.getByRole('button', { name });
const expanded = (name: RegExp) => groupBtn(name).getAttribute('aria-expanded');

async function renderShell(route = '/dashboard', children: React.ReactNode = 'x') {
  await loginAs(client, 'admin');
  const view = renderPage(<AppShellPage title="Test">{children}</AppShellPage>, route);
  await screen.findByRole('button', { name: /^tizim/i });
  return view;
}

describe('AppShell — akkordeon menyu', () => {
  afterEach(() => {
    useSession.getState().clear();
    localStorage.clear();
  });

  it('faol sahifa guruhi ochiq, qolganlari yopiq', async () => {
    await renderShell('/dashboard');
    expect(expanded(/^umumiy/i)).toBe('true');
    expect(expanded(/^tizim/i)).toBe('false');
    expect(expanded(/^ulanish/i)).toBe('false');
  });

  it('bitta guruh ochilsa — boshqasi yopiladi; ochiq guruhni bosish uni yopadi', async () => {
    const user = userEvent.setup();
    await renderShell('/dashboard');

    await user.click(groupBtn(/^tizim/i));
    expect(expanded(/^tizim/i)).toBe('true');
    expect(expanded(/^umumiy/i)).toBe('false');
    expect(screen.getAllByRole('button', { expanded: true })).toHaveLength(1);

    await user.click(groupBtn(/^tizim/i));
    expect(screen.queryAllByRole('button', { expanded: true })).toHaveLength(0);
  });

  it('boshqa guruhdagi sahifaga oʻtilsa — oʻsha guruh avtomatik ochiladi', async () => {
    const user = userEvent.setup();
    await renderShell('/dashboard', <Link to="/trunks">trunklarga</Link>);

    await user.click(screen.getByRole('link', { name: 'trunklarga' }));
    await waitFor(() => expect(expanded(/^ulanish/i)).toBe('true'));
    expect(expanded(/^umumiy/i)).toBe('false');
  });

  it('faol sahifali guruh yopilsa ham sarlavhada belgilanadi', async () => {
    const user = userEvent.setup();
    await renderShell('/dashboard');
    await user.click(groupBtn(/^umumiy/i));
    expect(groupBtn(/^umumiy/i)).toHaveAccessibleName(/joriy sahifa/i);
    expect(groupBtn(/^tizim/i)).not.toHaveAccessibleName(/joriy sahifa/i);
  });

  it('eski `innova.nav.collapsed` kaliti eʼtiborsiz qoladi', async () => {
    localStorage.setItem('innova.nav.collapsed', JSON.stringify(['overview']));
    await renderShell('/dashboard');
    expect(expanded(/^umumiy/i)).toBe('true');
  });
});

describe('AppShell — sidebar rejimi (qotirilgan / rail)', () => {
  afterEach(() => {
    useSession.getState().clear();
    localStorage.clear();
  });

  it('sukut — qotirilgan; yigʻish tugmasi rail rejimiga oʻtkazadi va saqlaydi', async () => {
    const user = userEvent.setup();
    await renderShell();
    expect(screen.getByRole('link', { name: 'Boshqaruv paneli' })).not.toHaveAttribute('aria-label');

    await user.click(screen.getByRole('button', { name: /menyuni yigʻish/i }));
    expect(localStorage.getItem('innova.nav.mode')).toBe('rail');
    const link = screen.getByRole('link', { name: 'Boshqaruv paneli' });
    expect(link).toHaveAttribute('aria-label', 'Boshqaruv paneli');
    expect(link).toHaveAttribute('title', 'Boshqaruv paneli');

    await user.click(screen.getByRole('button', { name: /menyuni qotirish/i }));
    expect(localStorage.getItem('innova.nav.mode')).toBe('pinned');
  });

  it('saqlangan rail rejimi qayta yuklanganda tiklanadi', async () => {
    localStorage.setItem('innova.nav.mode', 'rail');
    await renderShell();
    expect(screen.getByRole('button', { name: /menyuni qotirish/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Boshqaruv paneli' })).toHaveAttribute('aria-label');
  });

  it('buzilgan qiymat — qotirilgan rejim', async () => {
    localStorage.setItem('innova.nav.mode', 'garbage');
    await renderShell();
    expect(screen.getByRole('button', { name: /menyuni yigʻish/i })).toBeInTheDocument();
  });

  it('Ctrl+B rejimni almashtiradi, matn maydonida esa yoʻq', async () => {
    const user = userEvent.setup();
    await renderShell('/dashboard', <input aria-label="maydon" />);

    await user.keyboard('{Control>}b{/Control}');
    expect(localStorage.getItem('innova.nav.mode')).toBe('rail');

    await user.click(screen.getByRole('textbox', { name: 'maydon' }));
    await user.keyboard('{Control>}b{/Control}');
    expect(localStorage.getItem('innova.nav.mode')).toBe('rail');

    fireEvent.keyDown(document.body, { key: 'b', code: 'KeyB', metaKey: true });
    expect(localStorage.getItem('innova.nav.mode')).toBe('pinned');
  });

  it('rail: sichqoncha kelsa vaqtincha toʻliq ochiladi, ketsa yopiladi', async () => {
    localStorage.setItem('innova.nav.mode', 'rail');
    const user = userEvent.setup();
    await renderShell();
    const aside = screen.getByRole('complementary', { name: /asosiy menyu/i });
    expect(aside).toHaveAttribute('data-compact', 'true');

    await user.hover(aside);
    await waitFor(() => expect(aside).toHaveAttribute('data-compact', 'false'));

    await user.unhover(aside);
    await waitFor(() => expect(aside).toHaveAttribute('data-compact', 'true'));
  });
});

describe('AppShell — foydalanuvchi menyusi', () => {
  afterEach(() => useSession.getState().clear());

  it('menyuda «Profil va xavfsizlik» havolasi bor — parol va 2FA sahifasiga (/me) olib boradi', async () => {
    const user = userEvent.setup();
    await renderShell('/dashboard');
    await user.click(screen.getByRole('button', { name: /^Foydalanuvchi menyusi/ }));
    const link = await screen.findByRole('link', { name: 'Profil va xavfsizlik' });
    expect(link).toHaveAttribute('href', '/me');
  });
});
