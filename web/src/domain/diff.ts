// Oddiy qator-asosidagi unified diff — konfiguratsiya reviziyalari uchun (qarang
// ../../replica/m1b-contract.md §7). Matnlar kichik (dialplan parchasi) — LCS yetarli tez.

type DiffOp = { kind: 'ctx' | 'del' | 'add'; line: string };

/** Ikki qator ro'yxatining eng uzun umumiy ketma-ketligi (LCS) uzunlik jadvali. */
function lcsTable(a: string[], b: string[]): number[][] {
  const table: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      table[i]![j] = a[i] === b[j] ? table[i + 1]![j + 1]! + 1 : Math.max(table[i + 1]![j]!, table[i]![j + 1]!);
    }
  }
  return table;
}

function buildOps(a: string[], b: string[]): DiffOp[] {
  const table = lcsTable(a, b);
  const ops: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      ops.push({ kind: 'ctx', line: a[i]! });
      i += 1;
      j += 1;
    } else if (table[i + 1]![j]! >= table[i]![j + 1]!) {
      ops.push({ kind: 'del', line: a[i]! });
      i += 1;
    } else {
      ops.push({ kind: 'add', line: b[j]! });
      j += 1;
    }
  }
  while (i < a.length) { ops.push({ kind: 'del', line: a[i]! }); i += 1; }
  while (j < b.length) { ops.push({ kind: 'add', line: b[j]! }); j += 1; }
  return ops;
}

const PREFIX: Record<DiffOp['kind'], string> = { ctx: ' ', del: '-', add: '+' };

/** `oldText` → `newText` unified diff matni (`---`/`+++` sarlavha, so'ng +/- qatorlar). */
export function unifiedDiff(oldText: string, newText: string, oldLabel: string, newLabel: string): string {
  const a = oldText.split('\n');
  const b = newText.split('\n');
  const ops = buildOps(a, b);
  const body = ops.map((op) => `${PREFIX[op.kind]}${op.line}`).join('\n');
  return `--- ${oldLabel}\n+++ ${newLabel}\n${body}`;
}
