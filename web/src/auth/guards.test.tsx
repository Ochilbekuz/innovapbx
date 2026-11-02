import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';

const boot = { ready: true, setupNeeded: false };
const session: { user: object | null } = { user: null };
vi.mock('./useAuthBootstrap', () => ({ useAuthBootstrap: () => boot }));
vi.mock('@/api', () => ({ useSession: () => session }));
vi.mock('@/lib/i18n', () => ({ syncLanguageFromUser: () => undefined }));

import { RedirectIfAuthed, RedirectIfSetupDone } from './guards';

function at(guard: (p: { children: ReactNode }) => ReactNode) {
  const Guard = guard as (p: { children: ReactNode }) => JSX.Element;
  render(
    <MemoryRouter initialEntries={['/start']}>
      <Routes>
        <Route path="/start" element={<Guard><p>ichki</p></Guard>} />
        <Route path="/login" element={<p>login</p>} />
        <Route path="/setup" element={<p>setup</p>} />
        <Route path="/dashboard" element={<p>dashboard</p>} />
        <Route path="/me" element={<p>me</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('auth guards', () => {
  beforeEach(() => {
    boot.ready = true;
    boot.setupNeeded = false;
    session.user = null;
  });

  it('shows the loader until bootstrap is ready', () => {
    boot.ready = false;
    at(RedirectIfAuthed);
    expect(screen.getByRole('status')).toBeTruthy();
  });

  it('RedirectIfSetupDone: renders children while setup is needed, else /login', () => {
    boot.setupNeeded = true;
    at(RedirectIfSetupDone);
    expect(screen.getByText('ichki')).toBeTruthy();
  });

  it('RedirectIfSetupDone: setup done → /login', () => {
    at(RedirectIfSetupDone);
    expect(screen.getByText('login')).toBeTruthy();
  });

  it('RedirectIfAuthed: setup needed → /setup', () => {
    boot.setupNeeded = true;
    at(RedirectIfAuthed);
    expect(screen.getByText('setup')).toBeTruthy();
  });

  it('RedirectIfAuthed: "*" ruxsati bor foydalanuvchi → /dashboard', () => {
    session.user = { id: 1, permissions: ['*'] };
    at(RedirectIfAuthed);
    expect(screen.getByText('dashboard')).toBeTruthy();
  });

  it('RedirectIfAuthed: "monitor:view" bor foydalanuvchi → /dashboard', () => {
    session.user = { id: 1, permissions: ['monitor:view'] };
    at(RedirectIfAuthed);
    expect(screen.getByText('dashboard')).toBeTruthy();
  });

  it('RedirectIfAuthed: hech qanday ko\'rinadigan ekrani yo\'q foydalanuvchi → /me', () => {
    session.user = { id: 1, permissions: [] };
    at(RedirectIfAuthed);
    expect(screen.getByText('me')).toBeTruthy();
  });

  it('RedirectIfAuthed: anonymous → children', () => {
    at(RedirectIfAuthed);
    expect(screen.getByText('ichki')).toBeTruthy();
  });
});
