import type { Config } from 'tailwindcss';
import plugin from 'tailwindcss/plugin';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Rol nomlari tokens.json dan olinadi — yangi rol qo'shilsa, klass avtomatik paydo bo'ladi.
const tokens = JSON.parse(
  readFileSync(resolve(process.cwd(), '../replica/design/tokens.json'), 'utf8'),
) as {
  color: Record<string, string>;
  type: Record<string, { size: number; line: number; weight?: number; tracking?: string }>;
  radius: Record<string, number>;
  layout: Record<string, number | Record<string, number>> & { breakpoints: Record<string, number> };
  z: Record<string, number>;
};

// Tailwind klass nomi qisqa va o'qiladigan bo'lsin: text-muted, border-line, border-input.
const ALIAS: Record<string, string> = {
  text: 'fg',
  'text-muted': 'muted',
  'text-disabled': 'disabled',
  border: 'line',
  'border-strong': 'line-strong',
  'border-input': 'input',
};

const colors = Object.fromEntries(
  Object.keys(tokens.color)
    .filter((k) => !k.startsWith('_'))
    .map((k) => [ALIAS[k] ?? k, `rgb(var(--c-${k}) / <alpha-value>)`]),
);

type FontSpec = [string, { lineHeight: string; letterSpacing?: string; fontWeight?: string }];
const fontSize: Record<string, FontSpec> = Object.fromEntries(
  Object.entries(tokens.type).map(([k, t]): [string, FontSpec] => [
    k,
    [
      `${t.size / 16}rem`,
      {
        lineHeight: `${t.line / 16}rem`,
        ...(t.tracking ? { letterSpacing: t.tracking } : {}),
        ...(t.weight && t.weight !== 400 ? { fontWeight: String(t.weight) } : {}),
      },
    ],
  ]),
);

const radius = Object.fromEntries(Object.keys(tokens.radius).map((k) => [k, `var(--radius-${k})`]));
const layoutVar = (k: string) => `var(--layout-${k})`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    screens: Object.fromEntries(
      Object.entries(tokens.layout.breakpoints).map(([k, v]) => [k, `${v}px`]),
    ),
    // `nav` — joriy menyu guruhining aksenti: guruh o'ralmasi `--nav-accent`ga `nav-*` tokenini beradi.
    colors: { transparent: 'transparent', current: 'currentColor', ...colors, nav: 'rgb(var(--nav-accent) / <alpha-value>)' },
    fontFamily: {
      sans: 'var(--font-sans)',
      display: 'var(--font-display)',
      mono: 'var(--font-mono)',
    },
    fontSize,
    borderRadius: { none: '0', DEFAULT: 'var(--radius-md)', full: '9999px', ...radius },
    boxShadow: {
      none: 'none',
      card: 'var(--shadow-card)',
      pop: 'var(--shadow-pop)',
      modal: 'var(--shadow-modal)',
      inset: 'var(--shadow-inset)',
    },
    zIndex: { auto: 'auto', 0: '0', 10: '10', ...Object.fromEntries(Object.entries(tokens.z).map(([k, v]) => [k, String(v)])) },
    extend: {
      borderColor: { DEFAULT: 'rgb(var(--c-border) / <alpha-value>)' },
      ringColor: { DEFAULT: 'rgb(var(--c-focus-ring) / <alpha-value>)' },
      spacing: {
        sidebar: layoutVar('sidebar'),
        'sidebar-collapsed': layoutVar('sidebar-collapsed'),
        header: layoutVar('header'),
        drawer: layoutVar('drawer'),
        'ctl-sm': 'var(--control-sm)',
        'ctl-md': 'var(--control-md)',
        'ctl-lg': 'var(--control-lg)',
      },
      maxWidth: {
        content: layoutVar('content-max'),
        form: layoutVar('form-max'),
        'modal-sm': layoutVar('modal-sm'),
        'modal-md': layoutVar('modal-md'),
        drawer: layoutVar('drawer'),
      },
      transitionDuration: { DEFAULT: 'var(--motion-base)', fast: 'var(--motion-fast)', base: 'var(--motion-base)', slow: 'var(--motion-slow)' },
      transitionTimingFunction: { DEFAULT: 'var(--motion-ease)', out: 'var(--motion-ease)', in: 'var(--motion-ease-in)' },
      keyframes: {
        'live-pulse': { '0%': { transform: 'scale(1)', opacity: '.55' }, '100%': { transform: 'scale(2.6)', opacity: '0' } },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'pop-in': { from: { opacity: '0', transform: 'translateY(4px) scale(.98)' }, to: { opacity: '1', transform: 'none' } },
        'slide-in-right': { from: { transform: 'translateX(100%)' }, to: { transform: 'none' } },
        shimmer: { from: { backgroundPosition: '-200% 0' }, to: { backgroundPosition: '200% 0' } },
      },
      animation: {
        'live-pulse': 'live-pulse 1.6s var(--motion-ease) infinite',
        'fade-in': 'fade-in var(--motion-base) var(--motion-ease)',
        'pop-in': 'pop-in var(--motion-base) var(--motion-ease)',
        'slide-in-right': 'slide-in-right var(--motion-slow) var(--motion-ease)',
        shimmer: 'shimmer 1.4s linear infinite',
      },
    },
  },
  plugins: [
    // `rail:` — desktop'da yig'ilgan (faqat ikonali) yon menyu ichida: `<aside data-compact="true">` avlodlari.
    // Mobil drawer'ga ta'sir qilmaydi (u doim to'liq).
    plugin(({ addVariant }) => {
      addVariant('rail', `@media (min-width: ${tokens.layout.breakpoints.lg}px) { [data-compact="true"] & }`);
    }),
  ],
} satisfies Config;
