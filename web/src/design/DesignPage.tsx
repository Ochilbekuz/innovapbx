import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useTheme } from '@/lib/theme';
import { AppShell, BrandMark, type Revision } from '@/shell/AppShell';
import { Segmented } from '@/ui/Field';
import { HealthList } from '@/ui/Health';
import { Kpi } from '@/ui/Kpi';
import { StatusPill } from '@/ui/Status';
import { ColorSection, ScaleSection, TypeSection } from './Foundations';
import {
  ButtonSection, DialogSection, FormSection, HealthKpiSection, StatusSection, TableSection, TabsSection, ToastSection, ToggleSection,
} from './Primitives';
import {
  AudioSection, FlowSection, LogSection, PatternSection, PickerSection, SoftphoneSection, SortSection, WeekSection,
} from './PbxSections';
import { extensions, health } from './demo';
import { Section } from './Section';

const TOC: { group: string; items: [string, string][] }[] = [
  { group: 'Asos', items: [['ranglar', 'Ranglar'], ['tipografika', 'Tipografika'], ['olchamlar', 'Oʻlchamlar']] },
  {
    group: 'Primitivlar',
    items: [['tugma', 'Tugma'], ['forma', 'Forma'], ['toggle', 'Toggle'], ['tablar', 'Tablar'], ['holat', 'Holat belgisi'], ['soglik', 'Sogʻlik va KPI'], ['jadval', 'Jadval'], ['modal', 'Modal va panel'], ['toast', 'Toast']],
  },
  {
    group: 'PBX komponentlari',
    items: [['manzil', 'Manzil tanlagich'], ['oqim', 'Qoʻngʻiroq yoʻli'], ['hafta', 'Hafta setkasi'], ['audio', 'Audio pleer'], ['naqsh', 'Naqsh muharriri'], ['tartib', 'Tartib roʻyxati'], ['softfon', 'Softfon'], ['log', 'Log koʻruvchi']],
  },
  { group: 'Kompozitsiya', items: [['shell', 'App shell']] },
];

function useActiveSection(ids: string[]) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: '-20% 0px -70% 0px' },
    );
    ids.forEach((id) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [ids]);
  return active;
}

const ALL_IDS = TOC.flatMap((g) => g.items.map(([id]) => id));

/** Belgining faset motivi — gero burchagida, faqat dekor. */
function Facets() {
  return (
    <svg aria-hidden viewBox="0 0 240 240" className="h-full w-full">
      <polygon points="120,8 217,64 217,176 120,232 23,176 23,64" className="fill-sidebar-bg" />
      <polygon points="120,8 217,64 150,110" className="fill-chart-2" />
      <polygon points="23,64 120,8 92,96" className="fill-sidebar-surface" />
      <polygon points="92,96 150,110 120,150 60,140" className="fill-brand" />
      <polygon points="150,110 217,64 217,176 168,150" className="fill-chart-4" />
      <polygon points="120,150 150,110 168,150 140,196" className="fill-live" />
      <polygon points="60,140 120,150 140,196 120,232 23,176" className="fill-sidebar-active" />
      <polygon points="140,196 168,150 217,176 120,232" className="fill-brand-fire" />
      <polygon points="23,64 92,96 60,140 23,176" className="fill-chart-4/70" />
    </svg>
  );
}

function Hero() {
  return (
    <header className="relative grid gap-10 pb-12 pt-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:items-end">
      <div>
        <p className="eyebrow">Dizayn tizimi · v0.1 · 2026-oktabr</p>
        <h1 className="mt-4 max-w-[16ch] font-display text-display text-fg">
          Har kuni ochiladigan panel uchun <span className="text-brand">aniq</span> interfeys.
        </h1>
        <p className="mt-5 max-w-[58ch] text-md text-muted">
          Innova PBX — Asterisk ustidagi boshqaruv paneli. Bu sahifa uning qurilish bloklari: tokenlar, primitivlar va
          telefoniyaga xos komponentlar — hammasi izolyatsiyada, barcha holatlari bilan. Ekranlar shu bloklardan yigʻiladi.
        </p>
        <dl className="mt-8 grid max-w-xl grid-cols-3 gap-px overflow-hidden rounded-md border border-line bg-line text-sm">
          {[['Shrift', 'IBM Plex'], ['Asos', '4 px'], ['Kontrast', 'AA · 106/106']].map(([k, v]) => (
            <div key={k} className="bg-surface px-3 py-2.5">
              <dt className="eyebrow">{k}</dt>
              <dd className="num mt-0.5 text-fg">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="relative ml-auto hidden aspect-square w-full max-w-[300px] lg:block">
        <div aria-hidden className="hairline-grid absolute -inset-6 rounded-lg [mask-image:radial-gradient(closest-side,black,transparent)]" />
        <div className="relative h-full w-full drop-shadow-[0_24px_40px_rgb(var(--c-scrim)/0.25)]"><Facets /></div>
      </div>
    </header>
  );
}

function ShellSection() {
  const [rev, setRev] = useState<Revision['state']>('applied');
  return (
    <Section
      id="shell"
      index="21"
      title="App shell"
      lead="Yon menyu vazifa boʻyicha guruhlangan, «Apply Config» tugmasi yoʻq — har saqlash darhol qoʻllanadi. Headerʼda faqat dialplan reviziyasi holati: qoʻllandi, qoʻllanmoqda yoki qaytarildi."
      used="hammasi"
    >
      <div className="mb-3 flex items-center gap-3">
        <span className="text-sm text-muted">Reviziya:</span>
        <Segmented label="Reviziya holati" value={rev} onChange={setRev} options={[{ value: 'applied', label: 'Qoʻllandi' }, { value: 'applying', label: 'Qoʻllanmoqda' }, { value: 'rolled_back', label: 'Qaytarildi' }]} />
      </div>
      <div className="h-[720px] overflow-hidden rounded-lg border border-line-strong shadow-modal">
        <AppShell
          system={{ name: 'pbx-toshkent-01', detail: 'Asterisk 22.4 · 14 kun' }}
          embedded
          active="dashboard"
          title="Boshqaruv paneli"
          crumbs={['pbx-toshkent-01', 'Umumiy']}
          health={health}
          revision={{ number: rev === 'rolled_back' ? 142 : 143, state: rev, at: '12:04' }}
          call="talking"
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Kpi label="Bugungi qoʻngʻiroqlar" value="1 284" delta={12} series={[22, 30, 28, 41, 38, 52, 49, 61]} />
                <Kpi label="Javobsiz" value="37" delta={-8} />
                <Kpi label="Faol kanallar" value="18" unit="/ 50" />
                <Kpi label="Navbatda" value="4" />
            </div>
            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
                <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                  <h3 className="font-display text-base font-semibold">Hozir gaplashayotganlar</h3>
                  <span className="num text-sm text-muted">5</span>
                </div>
                <ul className="divide-y divide-line">
                  {extensions.slice(0, 5).map((e, i) => (
                    <li key={e.num} className="flex h-14 items-center gap-4 px-4 text-sm">
                      <span className="num w-10 font-medium">{e.num}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-fg">{e.name}</span>
                        <span className="num block truncate text-xs text-muted">+998 9{i} 4{i}1 2{i} 0{i}</span>
                      </span>
                      <StatusPill status={i === 3 ? 'error' : 'online'} live={i === 0}>{i === 3 ? 'Jitter 48 ms' : 'Suhbat'}</StatusPill>
                      <span className="num w-12 text-right text-muted">0{i}:{(17 + i * 9) % 60}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <HealthList items={health} />
            </div>
          </div>
        </AppShell>
      </div>
    </Section>
  );
}

export function DesignPage() {
  const { theme, setTheme } = useTheme();
  const active = useActiveSection(ALL_IDS);
  return (
    <div className="min-h-dvh bg-bg">
      <a href="#ranglar" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-toast focus:rounded-md focus:bg-surface focus:px-3 focus:py-2">Kontentga oʻtish</a>
      <header className="sticky top-0 z-header border-b border-line bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-header max-w-content items-center gap-4 px-6">
          <BrandMark onDark={false} />
          <span aria-hidden className="h-5 w-px bg-line-strong" />
          <span className="text-sm text-muted">Dizayn tizimi</span>
          <div className="ml-auto flex items-center gap-3">
            <span className="num hidden text-xs text-muted sm:inline">tokens.json → tokens.css → Tailwind</span>
            <Segmented
              label="Rejim"
              size="md"
              value={theme}
              onChange={setTheme}
              options={[{ value: 'light', label: <><Sun aria-hidden />Yorugʻ</> }, { value: 'dark', label: <><Moon aria-hidden />Qorongʻi</> }]}
            />
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-content gap-10 px-6 lg:grid-cols-[200px_minmax(0,1fr)]">
        <nav aria-label="Boʻlimlar" className="sticky top-header hidden h-[calc(100dvh-var(--layout-header))] overflow-y-auto py-8 lg:block">
          {TOC.map((g) => (
            <div key={g.group} className="mb-5">
              <p className="eyebrow mb-1.5">{g.group}</p>
              <ul className="border-l border-line">
                {g.items.map(([id, label]) => (
                  <li key={id}>
                    <a
                      href={`#${id}`}
                      aria-current={active === id ? 'true' : undefined}
                      className={cn(
                        '-ml-px block border-l-2 py-1 pl-3 text-sm transition-colors duration-fast',
                        active === id ? 'border-brand font-medium text-fg' : 'border-transparent text-muted hover:text-fg',
                      )}
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <main className="min-w-0 space-y-14 pb-24">
          <Hero />
          <ColorSection />
          <TypeSection />
          <ScaleSection />
          <ButtonSection />
          <FormSection />
          <ToggleSection />
          <TabsSection />
          <StatusSection />
          <HealthKpiSection />
          <TableSection />
          <DialogSection />
          <ToastSection />
          <PickerSection />
          <FlowSection />
          <WeekSection />
          <AudioSection />
          <PatternSection />
          <SortSection />
          <SoftphoneSection />
          <LogSection />
          <ShellSection />
        </main>
      </div>
    </div>
  );
}
