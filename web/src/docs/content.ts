// `docs/qollanma/*.md` (uz asli) va `docs/qollanma/{ru,en}/*.md` (tarjimalar) ni qurish vaqtida xom matn sifatida
// kiritadi (`@docs` — vite.config.ts/tsconfig.json). Faqat `DocsPage` (lazy chunk) import qiladi — asosiy bundle'ga kirmaydi.
import type { Lang } from '@/lib/i18n';
import { buildCatalog, overlayByName, type Catalog } from './catalog';

const glob = {
  uz: import.meta.glob<string>('@docs/*.md', { query: '?raw', import: 'default', eager: true }),
  ru: import.meta.glob<string>('@docs/ru/*.md', { query: '?raw', import: 'default', eager: true }),
  en: import.meta.glob<string>('@docs/en/*.md', { query: '?raw', import: 'default', eager: true }),
};

/** Tilma-til katalog; tarjimasi yo'q bo'lim uzbekcha ko'rsatiladi. */
export const CATALOGS: Record<Lang, Catalog> = {
  uz: buildCatalog(glob.uz),
  ru: buildCatalog(overlayByName(glob.uz, glob.ru)),
  en: buildCatalog(overlayByName(glob.uz, glob.en)),
};

/** Qaysi bo'limlar shu tilga haqiqatan tarjima qilingan (test tekshiradi). */
export const TRANSLATED: Record<'ru' | 'en', Set<string>> = {
  ru: new Set(buildCatalog(glob.ru).byId.keys()),
  en: new Set(buildCatalog(glob.en).byId.keys()),
};

export function catalogFor(lang: string | undefined): Catalog {
  return lang && lang in CATALOGS ? CATALOGS[lang as Lang] : CATALOGS.uz;
}
