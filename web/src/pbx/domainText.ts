// Domen qatlami (src/domain) tilsiz ma'lumot qaytaradi; uni tanlangan tildagi matnga shu yer aylantiradi.
// Kalitlar `common` namespace'da — har qanday namespace'dagi `t` bilan ishlashi uchun `common:` prefiksi bilan.
import type { TFunction } from 'i18next';
import type { PatternDescription, PatternErrorCode } from '@/domain/pattern';

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;

/** Dushanbadan boshlab 7 kun nomi: `short` — «Du», `long` — «Dushanba». */
export function dayLabels(t: TFunction, form: 'short' | 'long'): string[] {
  return DAY_KEYS.map((day) => t(`common:day.${form}.${day}`));
}

const ERROR_KEY: Record<PatternErrorCode, string> = {
  empty: 'empty',
  'bad-char': 'badChar',
  'unclosed-class': 'unclosedClass',
  'empty-class': 'emptyClass',
  'bad-range': 'badRange',
  'wildcard-not-last': 'wildcardNotLast',
};

export function patternText(desc: PatternDescription, t: TFunction): string {
  if (!desc.ok) return t(`common:pattern.error.${ERROR_KEY[desc.code]}`);
  const len = t(desc.open ? 'common:pattern.describe.lenAtLeast' : 'common:pattern.describe.lenExact', { n: desc.minLength });
  return desc.prefix
    ? t('common:pattern.describe.withPrefix', { len, prefix: desc.prefix })
    : t('common:pattern.describe.plain', { len });
}
