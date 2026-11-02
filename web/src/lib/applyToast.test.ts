import { describe, expect, it } from 'vitest';
import { applyToast } from './applyToast';
import type { ApplyResult } from '@/api/types';

describe('applyToast', () => {
  it("'applied' — muvaffaqiyat toast, reviziya raqami bilan", () => {
    const apply: ApplyResult = { status: 'applied', revision: 42, message: null };
    expect(applyToast(apply)).toMatchObject({ kind: 'success', title: 'Saqlandi', description: 'Reviziya r42' });
  });

  it("'unchanged' — info toast", () => {
    const apply: ApplyResult = { status: 'unchanged', revision: null, message: "O'zgarishlar yo'q edi" };
    expect(applyToast(apply)).toMatchObject({ kind: 'info', title: 'Oʻzgarish yoʻq', description: "O'zgarishlar yo'q edi" });
  });

  it("'rolled_back' — doim xato toast, status muvaffaqiyat bo'lmasligi kerak", () => {
    const apply: ApplyResult = { status: 'rolled_back', revision: 42, message: 'Dialplan xato' };
    const toast = applyToast(apply);
    expect(toast.kind).toBe('not-applied');
    expect(toast.title).toBe('PBXʼga qoʻllanmadi');
    expect(toast.description).toBe('Dialplan xato');
  });

  it("'realtime' — muvaffaqiyat toast, maxsus sarlavha bilan ham ishlaydi", () => {
    const apply: ApplyResult = { status: 'realtime', revision: 7, message: 'Darhol qo\'llandi' };
    expect(applyToast(apply, 'Yangilandi')).toMatchObject({ kind: 'success', title: 'Yangilandi' });
  });

  it("reviziya yo'q bo'lsa — message description sifatida ishlatiladi", () => {
    const apply: ApplyResult = { status: 'applied', revision: null, message: 'Tayyor' };
    expect(applyToast(apply).description).toBe('Tayyor');
  });
});
