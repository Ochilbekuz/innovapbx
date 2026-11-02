import { create } from 'zustand';

export type Theme = 'light' | 'dark';
const KEY = 'innova.theme';

function initialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  const fromUrl = new URLSearchParams(window.location.search).get('theme');
  if (fromUrl === 'light' || fromUrl === 'dark') return fromUrl;
  const saved = window.localStorage.getItem(KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function apply(theme: Theme) {
  if (typeof document !== 'undefined') document.documentElement.dataset.theme = theme;
}

type ThemeState = { theme: Theme; setTheme: (t: Theme) => void; toggle: () => void };

export const useTheme = create<ThemeState>((set, get) => {
  const theme = initialTheme();
  apply(theme);
  const setTheme = (t: Theme) => {
    apply(t);
    window.localStorage.setItem(KEY, t);
    set({ theme: t });
  };
  return { theme, setTheme, toggle: () => setTheme(get().theme === 'dark' ? 'light' : 'dark') };
});
