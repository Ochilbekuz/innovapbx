// `docs/qollanma/*.md` ni qurish vaqtida xom matn sifatida kiritadi (`@docs` — vite.config.ts/tsconfig.json).
// Faqat `DocsPage` (lazy chunk) import qiladi — asosiy bundle'ga qo'shilmaydi.
import { buildCatalog } from './catalog';

const files = import.meta.glob<string>('@docs/*.md', { query: '?raw', import: 'default', eager: true });

export const CATALOG = buildCatalog(files);
