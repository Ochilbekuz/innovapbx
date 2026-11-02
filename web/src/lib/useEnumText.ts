import { useTranslation } from 'react-i18next';

/**
 * Enum/holat qiymatlarini tarjima qilingan matnlarga aylantiradigan umumiy yordamchi.
 * Har bir `keys` elementi uchun `${prefix}.${key}` kaliti `ns` nomfazosidan olinadi.
 * Masalan: `useEnumText('common', 'status', ['online', 'offline'])` →
 * `{ online: t('status.online'), offline: t('status.offline') }`.
 */
export function useEnumText<K extends string>(ns: string, prefix: string, keys: readonly K[]): Record<K, string> {
  const { t } = useTranslation(ns);
  return keys.reduce((acc, key) => {
    acc[key] = t(`${prefix}.${key}`);
    return acc;
  }, {} as Record<K, string>);
}
