// CDR kengaytirilgan qidiruv shablonlari — nom bilan saqlab, keyin bir bosishda qo'llash.
// Ro'yxat ustidagi amallar (`addSearchTemplate`/`removeSearchTemplate`) sof funksiyalar — `localStorage`
// faqat `loadSearchTemplates`/`saveSearchTemplates` ichida (naqsh: `shell/navMode.ts`).
import { newId } from '@/lib/browser';
import type { AdvancedSearchForm } from './advancedSearch';

export type SearchTemplate = { id: string; name: string; form: AdvancedSearchForm };

const KEY = 'innova.cdr.searchTemplates';

function isAdvancedSearchForm(v: unknown): v is AdvancedSearchForm {
  return typeof v === 'object' && v !== null && 'src' in v && 'disposition' in v;
}

function isSearchTemplate(v: unknown): v is SearchTemplate {
  return typeof v === 'object' && v !== null
    && typeof (v as SearchTemplate).id === 'string'
    && typeof (v as SearchTemplate).name === 'string'
    && isAdvancedSearchForm((v as SearchTemplate).form);
}

/** Buzilgan/yo'q qiymat — xavfsiz bo'sh ro'yxat qaytaradi. */
export function loadSearchTemplates(): SearchTemplate[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isSearchTemplate) : [];
  } catch {
    return [];
  }
}

/** Xususiy rejim/kvota tolasa ham UI ishlashda davom etadi — holat shu sessiyada xotirada qoladi. */
export function saveSearchTemplates(templates: SearchTemplate[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(templates));
  } catch {
    // Saqlab bo'lmadi — jim o'tamiz.
  }
}

/** Bir xil nomdagi eski shablonni almashtiradi (qayta saqlash), aks holda yangisini qo'shadi. */
export function addSearchTemplate(templates: SearchTemplate[], name: string, form: AdvancedSearchForm): SearchTemplate[] {
  const trimmed = name.trim();
  const next: SearchTemplate = { id: newId(), name: trimmed, form };
  const withoutSameName = templates.filter((t) => t.name !== trimmed);
  return [...withoutSameName, next];
}

export function removeSearchTemplate(templates: SearchTemplate[], id: string): SearchTemplate[] {
  return templates.filter((t) => t.id !== id);
}
