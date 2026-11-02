// Qo'ng'iroq oqimi: manzildan boshlab daraxt. Halqa (ota yo'lida takrorlangan obyekt) va singan havolalar belgilanadi.
import { resolveDestination, type Catalog, type DestKind, type Destination, type Resolved, type TargetKind } from './destination';

export type FlowState = 'ok' | 'loop' | 'broken' | 'empty' | 'invalid';

export type FlowNode = {
  key: string;
  edgeLabel?: string;
  resolved: Resolved;
  state: FlowState;
  children: FlowNode[];
};

const MAX_DEPTH = 12;

function nodeState(r: Resolved, seen: ReadonlySet<string>): FlowState {
  if (r.state !== 'ok') return r.state;
  return r.target && seen.has(r.target.id) ? 'loop' : 'ok';
}

function walk(dest: Destination | null, catalog: Catalog, path: ReadonlySet<string>, key: string, edgeLabel?: string): FlowNode {
  const resolved = resolveDestination(dest, catalog);
  const state = nodeState(resolved, path);
  const target = resolved.state === 'ok' ? resolved.target : undefined;
  const expand = state === 'ok' && target && path.size < MAX_DEPTH;
  const nextPath = target ? new Set(path).add(target.id) : path;
  const children = expand
    ? (target.next ?? []).map((e, i) => walk(e.dest, catalog, nextPath, `${key}.${i}`, e.label))
    : [];
  return { key, edgeLabel, resolved, state, children };
}

export function buildFlow(root: Destination | null, catalog: Catalog): FlowNode {
  return walk(root, catalog, new Set(), 'root');
}

export function flowIssues(node: FlowNode): { loops: number; broken: number } {
  return node.children.map(flowIssues).reduce(
    (acc, c) => ({ loops: acc.loops + c.loops, broken: acc.broken + c.broken }),
    { loops: node.state === 'loop' ? 1 : 0, broken: node.state === 'broken' ? 1 : 0 },
  );
}

export type FlowIssue = { state: 'loop' | 'broken'; key: string; path: string[] };

/** Halqa va singan tugunlar — chuqurlik bo'yicha tartibda, ildizdan tarmoq yorliqlari bilan. */
export function issueList(node: FlowNode, path: string[] = []): FlowIssue[] {
  const here = node.edgeLabel === undefined ? path : [...path, node.edgeLabel];
  const own: FlowIssue[] = node.state === 'loop' || node.state === 'broken' ? [{ state: node.state, key: node.key, path: here }] : [];
  return [...own, ...node.children.flatMap((c) => issueList(c, here))];
}

// --- Server tomonidan hisoblangan oqim (GET /flow/{id}) ---
// Bu qism `fake.ts`/`real.ts` ikkisi uchun ham umumiy: backend allaqachon bosib chiqqan daraxtni
// (Target + edge + loop/broken belgilari) tasvirlash uchun ishlatiladi. Katalogga bog'liq emas — sof.

export type FlowRef = { kind: string; id: string };
export type FlowEdgeOut = { edge: string; ref: FlowRef };
export type FlowTargetSummary = { id: string; kind: string; label: string; number: string | null; broken: boolean };
export type FlowLookupResult = { target: FlowTargetSummary; edges: FlowEdgeOut[] };
export type FlowLookup = (ref: FlowRef) => FlowLookupResult | null;
export type FlowGraphNode = { target: FlowTargetSummary; edge: string | null; children: FlowGraphNode[]; loop: boolean; broken: boolean };

const FLOW_GRAPH_MAX_DEPTH = 12;

/** `fake.ts` va (kelajakda) haqiqiy backend bilan bir xil qoida: chuqurlik ≤ 12, takrorlangan tugun bolasiz to'xtaydi. */
export function buildFlowGraph(
  root: FlowRef,
  lookup: FlowLookup,
  edge: string | null = null,
  visited: ReadonlySet<string> = new Set(),
  depth = 0,
): FlowGraphNode {
  const found = lookup(root);
  if (!found) return { target: { id: root.id, kind: root.kind, label: root.id, number: null, broken: true }, edge, children: [], loop: false, broken: true };
  const key = `${root.kind}:${root.id}`;
  if (visited.has(key)) return { target: found.target, edge, children: [], loop: true, broken: found.target.broken };
  const nextVisited = new Set(visited).add(key);
  const children = found.target.broken || depth >= FLOW_GRAPH_MAX_DEPTH
    ? []
    : found.edges.map((e) => buildFlowGraph(e.ref, lookup, e.edge, nextVisited, depth + 1));
  return { target: found.target, edge, children, loop: false, broken: found.target.broken };
}

/** `FlowGraphNode` (server shakli) → `FlowNode` (bu modul ko'rish uchun ishlatadigan shakl), CallFlowTree uchun. */
export function fromApiFlow(node: FlowGraphNode, key = 'root'): FlowNode {
  const t = node.target;
  const resolved: Resolved = t.broken
    ? { state: 'broken', kind: t.kind as TargetKind, targetId: t.id }
    : { state: 'ok', kind: t.kind as DestKind, label: t.label, number: t.number ?? undefined, target: { id: t.id, kind: t.kind as TargetKind, name: t.label, number: t.number ?? undefined } };
  const state: FlowState = node.loop ? 'loop' : resolved.state;
  return {
    key,
    edgeLabel: key === 'root' ? undefined : (node.edge ?? undefined),
    resolved,
    state,
    children: node.children.map((c, i) => fromApiFlow(c, `${key}.${i}`)),
  };
}
