import lightTokens from '@design/tokens.json';
import darkTokens from '@design/tokens.dark.json';
import { cn } from '@/lib/cn';
import { contrast } from '@/lib/contrast';
import { useTheme } from '@/lib/theme';
import { Section } from './Section';

type ColorKey = keyof typeof lightTokens.color;

const GROUPS: { title: string; note: string; keys: [ColorKey, ColorKey?][] }[] = [
  {
    title: 'Yuzalar va chiziqlar',
    note: 'Iliq qogʻoz fon, oq panel, bir pogʻona botiq yuza. Chegaralar — past kontrast, input chegarasi — 3:1.',
    keys: [['bg', 'text'], ['surface', 'text'], ['surface-2', 'text-muted'], ['raised', 'text'], ['border'], ['border-strong'], ['border-input']],
  },
  {
    title: 'Matn',
    note: 'Ikki daraja yetarli. Uchinchisi faqat oʻchirilgan holat uchun — kontrast talab qilinmaydi.',
    keys: [['text', 'surface'], ['text-muted', 'surface'], ['text-disabled', 'surface']],
  },
  {
    title: 'Brend va aksent',
    note: '#D7621D — belgi, grafik, faol chiziq. Tugma va havola uchun bir pogʻona toʻqroq ton: oq yozuv 4.5:1 dan oshadi.',
    keys: [['brand', 'surface'], ['brand-fire', 'surface'], ['accent', 'on-accent'], ['accent-hover', 'on-accent'], ['accent-soft', 'on-accent-soft'], ['focus-ring', 'surface'], ['live', 'on-live']],
  },
  {
    title: 'Holat',
    note: 'Xato — sof qizil, aksentdan uzoq. Ogohlantirish — jigarrang-oxra, oltindan farqli. Har biri ikon shakli bilan keladi.',
    keys: [['danger', 'on-danger'], ['danger-soft', 'on-danger-soft'], ['success', 'on-success'], ['success-soft', 'on-success-soft'], ['warning-soft', 'on-warning-soft'], ['info-soft', 'on-info-soft']],
  },
  {
    title: 'Yon menyu',
    note: 'Ikkala rejimda ham koʻmir: admin koʻzi navigatsiyani kontentdan darhol ajratadi.',
    keys: [['sidebar-bg', 'sidebar-text'], ['sidebar-surface', 'sidebar-text'], ['sidebar-active', 'sidebar-text'], ['sidebar-muted', 'sidebar-bg']],
  },
];

function Swatch({ k, on, palette }: { k: ColorKey; on?: ColorKey; palette: Record<string, string> }) {
  const hex = palette[k] ?? '';
  const fgHex = on ? palette[on] : undefined;
  const ratio = fgHex ? contrast(hex, fgHex) : null;
  return (
    <li className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex h-16 items-end justify-between p-2" style={{ background: `rgb(var(--c-${k}))`, color: on ? `rgb(var(--c-${on}))` : undefined }}>
        {on ? <span className="text-sm font-medium">Aa 101</span> : <span />}
        {ratio !== null && <span className="num text-xs">{ratio.toFixed(2)}</span>}
      </div>
      <div className="px-2 py-1.5">
        <p className="truncate text-sm font-medium text-fg">{k}</p>
        <p className="num text-xs text-muted">{hex}</p>
      </div>
    </li>
  );
}

export function ColorSection() {
  const { theme } = useTheme();
  const palette = (theme === 'dark' ? darkTokens.color : lightTokens.color) as Record<string, string>;
  return (
    <Section
      id="ranglar"
      index="01"
      title="Ranglar"
      lead="Ranglar rol boʻyicha nomlanadi, qiymat emas. Komponent «bg-surface text-muted» deb yozadi — xom hex yoʻq. Raqam — swatch ustidagi matn juftligining WCAG nisbati."
    >
      <div className="space-y-8">
        {GROUPS.map((g) => (
          <div key={g.title} className="grid gap-4 lg:grid-cols-[220px_1fr]">
            <div>
              <h3 className="font-display text-base font-semibold">{g.title}</h3>
              <p className="mt-1 text-sm text-muted">{g.note}</p>
            </div>
            <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
              {g.keys.map(([k, on]) => <Swatch key={k} k={k} on={on} palette={palette} />)}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  );
}

const TYPE: { token: keyof typeof lightTokens.type; sample: string; cls: string; font: string }[] = [
  { token: 'display', sample: 'Qoʻngʻiroq yoʻqolmaydi', cls: 'text-display font-display', font: 'Plex Sans Condensed 600' },
  { token: 'xl', sample: 'Kiruvchi marshrutlar', cls: 'text-xl font-display', font: 'Plex Sans Condensed 600' },
  { token: 'lg', sample: 'Navbat «Sotuv boʻlimi»', cls: 'text-lg font-display', font: 'Plex Sans Condensed 600' },
  { token: 'md', sample: 'Gʻalaba toʻgʻri sozlangan dialplandan boshlanadi; maʼlumot yoʻqolmaydi.', cls: 'text-md', font: 'Plex Sans 400' },
  { token: 'base', sample: 'Входящий звонок перенаправлен на очередь — Incoming call routed to queue', cls: 'text-base', font: 'Plex Sans 400' },
  { token: 'sm', sample: 'Oxirgi registratsiya 12:04 · 192.168.10.24:5060', cls: 'text-sm text-muted', font: 'Plex Sans 400' },
  { token: '2xs', sample: 'Ustun sarlavhasi', cls: 'text-2xs uppercase text-muted', font: 'Plex Sans 600, +0.06em' },
];

export function TypeSection() {
  return (
    <Section
      id="tipografika"
      index="02"
      title="Tipografika"
      lead="IBM Plex oilasi — ochiq litsenziya, self-hosted. Sarlavha — Condensed: zich panelda koʻp soʻz sigʻadi. Raqamlar — Plex Mono, tabular: jadval ustunida 101 va 118 bir xil enda turadi."
    >
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <ol className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface shadow-card">
          {TYPE.map((t) => {
            const spec = lightTokens.type[t.token];
            return (
              <li key={t.token} className="grid grid-cols-[72px_1fr] items-baseline gap-4 px-5 py-4 md:grid-cols-[72px_1fr_170px]">
                <span className="num text-xs text-brand">{t.token}</span>
                <span className={cn('min-w-0 text-fg', t.cls)}>{t.sample}</span>
                <span className="num hidden text-xs text-muted md:block">{spec.size}/{spec.line} · {t.font}</span>
              </li>
            );
          })}
        </ol>
        <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface-2 p-5">
          <span className="eyebrow">Mono · tabular-nums · slashed zero</span>
          <div className="num space-y-1 text-md text-fg">
            <p>+998 71 200 00 00</p>
            <p>_998[3-9]XXXXXXXX</p>
            <p>SIP/2.0 486 Busy Here</p>
            <p className="text-2xl">00:04:17</p>
          </div>
          <span className="eyebrow mt-3">Oʻzbek lotin belgilari</span>
          <p className="text-md text-fg">oʻ gʻ Oʻ Gʻ — maʼlumot, eʼlon, sanʼat</p>
          <p className="text-sm text-muted">Toʻgʻri apostrof: U+02BB (ʻ) va U+02BC (ʼ), oddiy &apos; emas.</p>
        </div>
      </div>
    </Section>
  );
}

export function ScaleSection() {
  const space = lightTokens.space.filter((s) => s > 0);
  const radius = Object.entries(lightTokens.radius);
  const shadows = ['card', 'pop', 'modal'] as const;
  return (
    <Section
      id="olchamlar"
      index="03"
      title="Oʻlcham, radius, soya, harakat"
      lead="4 px asos. Boshqaruv balandligi 28 / 32 / 40 — kuniga yuz marta bosiladigan panel uchun zich, lekin barmoqqa ham yetadi. Radius kichik: industrial, «yumshoq ilova» emas."
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-line bg-surface p-5 shadow-card">
          <span className="eyebrow">Boʻshliq shkalasi</span>
          <ul className="mt-3 space-y-1.5">
            {space.map((s) => (
              <li key={s} className="flex items-center gap-3">
                <span className="num w-8 text-right text-xs text-muted">{s}</span>
                <span className="h-2.5 rounded-[1px] bg-brand" style={{ width: s * 3 }} />
              </li>
            ))}
          </ul>
        </div>
        <div className="grid gap-4">
          <div className="rounded-lg border border-line bg-surface p-5 shadow-card">
            <span className="eyebrow">Radius</span>
            <div className="mt-3 flex flex-wrap gap-3">
              {radius.map(([k, v]) => (
                <div key={k} className="flex flex-col items-center gap-1.5">
                  <span className="size-12 border-2 border-fg bg-surface-2" style={{ borderRadius: `var(--radius-${k})` }} />
                  <span className="num text-xs text-muted">{k} · {v === 999 ? '∞' : v}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-line bg-surface-2 p-5">
            <span className="eyebrow">Soya</span>
            <div className="mt-3 flex flex-wrap gap-4">
              {shadows.map((s) => (
                <div key={s} className="flex h-16 w-28 items-end rounded-md bg-raised p-2" style={{ boxShadow: `var(--shadow-${s})` }}>
                  <span className="num text-xs text-muted">{s}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-line bg-surface p-5 shadow-card">
            <span className="eyebrow">Harakat</span>
            <p className="num mt-2 text-sm text-fg">120 · 200 · 320 ms — cubic-bezier(0.22, 1, 0.36, 1)</p>
            <p className="mt-1 text-sm text-muted">«Harakatni kamaytirish» yoqilgan boʻlsa, barcha oʻtishlar va pulsatsiya oʻchadi.</p>
          </div>
        </div>
      </div>
    </Section>
  );
}
