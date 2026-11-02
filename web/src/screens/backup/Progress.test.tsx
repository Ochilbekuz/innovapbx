import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import i18n from '@/lib/i18n';
import { useJobStepText } from './Progress';

describe('useJobStepText', () => {
  it.each([
    ['pre_restore_backup', 'Joriy holat zaxiralanmoqda'],
    ['regenerate', 'Asterisk konfiguratsiyasi qayta yaratilmoqda'],
    ['yangi_bosqich', 'yangi_bosqich'],
    ['Fayllar arxivlanmoqda', 'Fayllar arxivlanmoqda'],
    [null, ''],
    [undefined, ''],
  ])('%s -> %s', async (step, text) => {
    await i18n.changeLanguage('uz');
    expect(renderHook(() => useJobStepText(step)).result.current).toBe(text);
  });

  it('tilga mos tarjima (en)', async () => {
    await i18n.changeLanguage('en');
    expect(renderHook(() => useJobStepText('pg_restore')).result.current).toBe('Restoring the database');
    await i18n.changeLanguage('uz');
  });
});
