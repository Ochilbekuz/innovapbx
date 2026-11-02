import { create } from 'zustand';
import type { User } from './types';

const REFRESH_KEY = 'innova.refresh';

type SessionState = {
  access: string | null;
  refresh: string | null;
  user: User | null;
  /** Bir martalik xabar login sahifasi uchun (masalan, zaxiradan tiklangandan keyin) — `clear(notice)` o'rnatadi, `setSession` o'chiradi. */
  notice: string | null;
  setSession: (access: string, refresh: string, user: User) => void;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: User) => void;
  clear: (notice?: string) => void;
};

function loadRefresh(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

/** Access token faqat xotirada (sahifa yangilansa yo'qoladi — /auth/me + refresh bilan tiklanadi). */
export const useSession = create<SessionState>((set) => ({
  access: null,
  refresh: loadRefresh(),
  user: null,
  notice: null,
  setSession: (access, refresh, user) => {
    window.localStorage.setItem(REFRESH_KEY, refresh);
    set({ access, refresh, user, notice: null });
  },
  setTokens: (access, refresh) => {
    window.localStorage.setItem(REFRESH_KEY, refresh);
    set({ access, refresh });
  },
  setUser: (user) => set({ user }),
  clear: (notice) => {
    window.localStorage.removeItem(REFRESH_KEY);
    set({ access: null, refresh: null, user: null, notice: notice ?? null });
  },

}));

export const getRefreshToken = () => useSession.getState().refresh;
export const getAccessToken = () => useSession.getState().access;
