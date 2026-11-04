import { describe, expect, it } from 'vitest';
import {
  appendUpdateLog, classifyMdLine, EMPTY_LOG, isRestartingDuringUpdate, isScrolledAwayFromEnd, parseMarkdownLite,
  phaseStatus, scrollToEnd, shouldShowUpdateLog, tokenizeInline, updateLogPollMs, updateStatePollMs,
} from './update';

describe('update — updateStatePollMs', () => {
  it('no data — no polling', () => {
    expect(updateStatePollMs(undefined)).toBe(false);
  });
  it('checking/updating — 2s', () => {
    expect(updateStatePollMs({ state: 'checking', pending: null })).toBe(2000);
    expect(updateStatePollMs({ state: 'updating', pending: null })).toBe(2000);
  });
  it('idle + pending — 2s', () => {
    expect(updateStatePollMs({ state: 'idle', pending: 'check' })).toBe(2000);
  });
  it('idle, no pending — no polling', () => {
    expect(updateStatePollMs({ state: 'idle', pending: null })).toBe(false);
  });
  it('done/failed, no pending — no polling', () => {
    expect(updateStatePollMs({ state: 'done', pending: null })).toBe(false);
    expect(updateStatePollMs({ state: 'failed', pending: null })).toBe(false);
  });
});

describe('update — updateLogPollMs / shouldShowUpdateLog', () => {
  it('log faqat updating paytida pollanadi', () => {
    expect(updateLogPollMs('updating')).toBe(2000);
    expect(updateLogPollMs('idle')).toBe(false);
    expect(updateLogPollMs('done')).toBe(false);
    expect(updateLogPollMs(undefined)).toBe(false);
  });
  it('log updating/done/failed holatlarida ko‘rsatiladi', () => {
    expect(shouldShowUpdateLog('updating')).toBe(true);
    expect(shouldShowUpdateLog('done')).toBe(true);
    expect(shouldShowUpdateLog('failed')).toBe(true);
    expect(shouldShowUpdateLog('idle')).toBe(false);
    expect(shouldShowUpdateLog('checking')).toBe(false);
  });
});

describe('update — isRestartingDuringUpdate', () => {
  it('updating + 502/503/tarmoq xatosi — qayta ishga tushish, xato emas', () => {
    expect(isRestartingDuringUpdate('updating', 502)).toBe(true);
    expect(isRestartingDuringUpdate('updating', 503)).toBe(true);
    expect(isRestartingDuringUpdate('updating', null)).toBe(true);
  });
  it('updating + boshqa status — haqiqiy xato', () => {
    expect(isRestartingDuringUpdate('updating', 500)).toBe(false);
    expect(isRestartingDuringUpdate('updating', 403)).toBe(false);
  });
  it('updating emas — hech qachon restart emas', () => {
    expect(isRestartingDuringUpdate('idle', 502)).toBe(false);
    expect(isRestartingDuringUpdate('done', null)).toBe(false);
    expect(isRestartingDuringUpdate(undefined, 502)).toBe(false);
  });
});

describe('update — appendUpdateLog', () => {
  it('bo‘sh javob — oʻzgarmaydi', () => {
    expect(appendUpdateLog(EMPTY_LOG, { offset: 0, text: '' })).toEqual(EMPTY_LOG);
  });
  it('odatiy holat — qoʻshib boradi', () => {
    const r1 = appendUpdateLog(EMPTY_LOG, { offset: 5, text: 'salom' });
    expect(r1).toEqual({ text: 'salom', offset: 5 });
    const r2 = appendUpdateLog(r1, { offset: 11, text: ' dunyo' });
    expect(r2).toEqual({ text: 'salom dunyo', offset: 11 });
  });
  it('offset kamaysa — jurnal qayta yaratilgan, tozalab qayta boshlaydi', () => {
    const prev = { text: 'eski uzun matn', offset: 14 };
    const r = appendUpdateLog(prev, { offset: 3, text: 'yan' });
    expect(r).toEqual({ text: 'yan', offset: 3 });
  });
});

describe('update — phaseStatus', () => {
  it('current yo‘q — hammasi pending', () => {
    expect(phaseStatus('backup', null)).toBe('pending');
  });
  it('oldingi bosqichlar done, joriysi current, keyingilari pending', () => {
    expect(phaseStatus('backup', 'code')).toBe('done');
    expect(phaseStatus('code', 'code')).toBe('current');
    expect(phaseStatus('install', 'code')).toBe('pending');
    expect(phaseStatus('restart', 'code')).toBe('pending');
  });
});

describe('update — parseMarkdownLite', () => {
  it('sarlavha, ro‘yxat va paragrafni ajratadi', () => {
    const blocks = parseMarkdownLite('## 1.0.13 — 2026-11-04\n\n- birinchi\n- ikkinchi\n\nOddiy paragraf.');
    expect(blocks).toEqual([
      { type: 'heading', level: 2, text: '1.0.13 — 2026-11-04' },
      { type: 'list', items: ['birinchi', 'ikkinchi'] },
      { type: 'paragraph', text: 'Oddiy paragraf.' },
    ]);
  });
  it('h3 sarlavha va ko‘p qatorli paragrafni bir blokka birlashtiradi', () => {
    const blocks = parseMarkdownLite('### Kichik sarlavha\nBirinchi qator\nikkinchi qator davomi');
    expect(blocks).toEqual([
      { type: 'heading', level: 3, text: 'Kichik sarlavha' },
      { type: 'paragraph', text: 'Birinchi qator ikkinchi qator davomi' },
    ]);
  });
  it('literal HTML teglari oddiy matn sifatida qoladi (xavfsiz)', () => {
    const blocks = parseMarkdownLite('<script>alert(1)</script> xavfsiz matn');
    expect(blocks).toEqual([{ type: 'paragraph', text: '<script>alert(1)</script> xavfsiz matn' }]);
  });
  it('boʻsh matn — boʻsh roʻyxat', () => {
    expect(parseMarkdownLite('')).toEqual([]);
    expect(parseMarkdownLite('\n\n\n')).toEqual([]);
  });
});

describe('update — classifyMdLine', () => {
  it('h2/h3 sarlavhani taniydi', () => {
    expect(classifyMdLine('## sarlavha')).toEqual({ kind: 'heading', level: 2, text: 'sarlavha' });
    expect(classifyMdLine('### kichik')).toEqual({ kind: 'heading', level: 3, text: 'kichik' });
  });
  it('roʻyxat qatorini taniydi', () => {
    expect(classifyMdLine('- band')).toEqual({ kind: 'list', text: 'band' });
    expect(classifyMdLine('* band')).toEqual({ kind: 'list', text: 'band' });
  });
  it('boʻsh qatorni taniydi', () => {
    expect(classifyMdLine('   ')).toEqual({ kind: 'blank' });
  });
  it('oddiy matnni taniydi', () => {
    expect(classifyMdLine('  oddiy matn  ')).toEqual({ kind: 'text', text: 'oddiy matn' });
  });
});

describe('update — isScrolledAwayFromEnd / scrollToEnd', () => {
  it('element yoʻq — toʻxtatilmaydi', () => {
    expect(isScrolledAwayFromEnd(null)).toBe(false);
  });
  it('pastda (farq <= 24) — toʻxtatilmaydi', () => {
    expect(isScrolledAwayFromEnd({ scrollHeight: 100, scrollTop: 80, clientHeight: 20 })).toBe(false);
  });
  it('yuqoriga aylantirilgan (farq > 24) — toʻxtatiladi', () => {
    expect(isScrolledAwayFromEnd({ scrollHeight: 200, scrollTop: 10, clientHeight: 20 })).toBe(true);
  });
  it('scrollToEnd — scrollTopni scrollHeightga tengla, null boʻlsa hech narsa qilmaydi', () => {
    const el = { scrollTop: 0, scrollHeight: 150 };
    scrollToEnd(el);
    expect(el.scrollTop).toBe(150);
    expect(() => scrollToEnd(null)).not.toThrow();
  });
});

describe('update — tokenizeInline', () => {
  it('qalin va kod belgilarini ajratadi', () => {
    expect(tokenizeInline('oddiy **qalin** va `kod` matn')).toEqual([
      { type: 'text', value: 'oddiy ' },
      { type: 'bold', value: 'qalin' },
      { type: 'text', value: ' va ' },
      { type: 'code', value: 'kod' },
      { type: 'text', value: ' matn' },
    ]);
  });
  it('hech qanday belgi yo‘q — bitta matn tokeni', () => {
    expect(tokenizeInline('oddiy matn')).toEqual([{ type: 'text', value: 'oddiy matn' }]);
  });
  it('<script> literal matn sifatida — HTML parse qilinmaydi', () => {
    expect(tokenizeInline('<script>alert(1)</script>')).toEqual([{ type: 'text', value: '<script>alert(1)</script>' }]);
  });
});
