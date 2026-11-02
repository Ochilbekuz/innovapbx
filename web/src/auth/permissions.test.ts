import { describe, expect, it, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { hasPermission, usePermission } from './permissions';
import { useSession } from '@/api/session';

// Regressiya: haqiqiy backend `admin` roli uchun `permissions: ["*"]` qaytaradi
// (qarang `api/app/core/permissions.py`), aniq satrlar ro'yxatini EMAS.
describe('hasPermission', () => {
  it('"*" ro\'yxatda bo\'lsa — har qanday aniq ruxsat uchun true qaytaradi', () => {
    expect(hasPermission(['*'], 'pbx.manage')).toBe(true);
    expect(hasPermission(['*'], 'anything.else')).toBe(true);
  });

  it('aniq ruxsat ro\'yxatda bo\'lsa — true qaytaradi', () => {
    expect(hasPermission(['pbx.manage'], 'pbx.manage')).toBe(true);
  });

  it('na "*" na aniq ruxsat yo\'q bo\'lsa — false qaytaradi', () => {
    expect(hasPermission(['calls:read:own'], 'pbx.manage')).toBe(false);
  });

  it('ruxsatlar ro\'yxati berilmagan bo\'lsa (foydalanuvchi yo\'q) — false qaytaradi', () => {
    expect(hasPermission(undefined, 'pbx.manage')).toBe(false);
  });
});

describe('usePermission', () => {
  afterEach(() => { useSession.getState().clear(); });

  it('foydalanuvchi yo\'q bo\'lsa — false qaytaradi', () => {
    const { result } = renderHook(() => usePermission('pbx.manage'));
    expect(result.current).toBe(false);
  });

  it('foydalanuvchida "*" ruxsati bo\'lsa — true qaytaradi', () => {
    useSession.setState({
      user: { id: 'u-1', login: 'admin', full_name: 'Admin', role: 'admin', permissions: ['*'], language: 'uz' },
    });
    const { result } = renderHook(() => usePermission('pbx.manage'));
    expect(result.current).toBe(true);
  });
});
