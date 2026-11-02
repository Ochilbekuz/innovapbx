/**
 * Demo (fake) klient uchun FreePBX ko'chirish (M5a) qoidalari: sinov to'plami rejasi (reja elementlari,
 * e'tiborsiz qoldirilganlar, global ogohlantirishlar) + reja-amal o'tish qoidasi + ish bosqichi hisob-kitobi.
 * `fakeBackup.ts`dagi `jobStep()` naqshi takrorlanadi — vaqtga asoslangan, `setTimeout` zanjirisiz.
 */
import type {
  MigrationAction, MigrationIgnoredItem, MigrationPatchAction, MigrationPlanItem, MigrationSummary, MigrationWarning,
} from './types';

/** `innova-fpbx-export.sh` orqali olinadigan sinov to'plamidagi FreePBX obyektlari — §1 moslik jadvaliga mos. */
export const FREEPBX_FIXTURE_PLAN: MigrationPlanItem[] = [
  { kind: 'audio', source_ref: 'recordings:1', name: 'Salomlashuv', number: null, action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'moh', source_ref: 'music:1', name: 'sinov-moh', number: null, action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'moh', source_ref: 'music:default', name: 'default', number: null, action: 'skip', reason: "Ichki sinf — fayllari qo'shilmaydi.", warnings: [{ code: 'builtin', message: "`default` MOH sinfi Innova'da allaqachon bor." }], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'time_group', source_ref: 'timegroups_groups:1', name: 'Ish vaqti', number: null, action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'holiday', source_ref: 'timegroups_details:2', name: '1-yanvar', number: null, action: 'create', reason: null, warnings: [{ code: 'holiday_from_timegroup', message: "Vaqt guruhidan bayram sifatida chiqarildi." }], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'extension', source_ref: 'users:101', name: 'Alisher Yusupov', number: '101', action: 'conflict', reason: "101 raqami Innova'da allaqachon band.", warnings: [], depends_on: [], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'extension', source_ref: 'users:102', name: 'Nodira Ergasheva', number: '102', action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'extension', source_ref: 'users:103', name: 'Rustam Qodirov', number: '103', action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'extension', source_ref: 'users:105', name: 'Shahnoza Yoldasheva', number: '105', action: 'create', reason: null, warnings: [{ code: 'weak_secret', message: "SIP siri zaif (12 belgidan kam)." }], depends_on: [], replaceable: false, has_secret: true, weak_secret: true },
  { kind: 'extension', source_ref: 'users:106', name: 'Javlon Tursunov', number: '106', action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'extension', source_ref: 'users:107', name: 'Gulnora Saidova', number: '107', action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'voicemail', source_ref: 'voicemail.conf:105', name: 'Shahnoza Yoldasheva pochta qutisi', number: '105', action: 'create', reason: null, warnings: [], depends_on: ['users:105'], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'trunk', source_ref: 'trunks:1', name: 'Beeline — registratsiya', number: null, action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'trunk', source_ref: 'trunks:2', name: 'Ucell — IP', number: null, action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'ring_group', source_ref: 'ringgroups:600', name: 'Qabul guruhi', number: '600', action: 'create', reason: null, warnings: [], depends_on: ['users:102', 'users:103', 'users:106'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'queue', source_ref: 'queues_config:700', name: "Qo'llab-quvvatlash navbati", number: '700', action: 'create', reason: null, warnings: [], depends_on: ['music:1'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'conference', source_ref: 'meetme:8000', name: 'Konferensiya 8000', number: '8000', action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: true, weak_secret: false },
  { kind: 'announcement', source_ref: 'announcement:1', name: 'Tanaffus xabari', number: null, action: 'create', reason: null, warnings: [], depends_on: ['recordings:1'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'ivr', source_ref: 'ivr_details:1', name: 'Asosiy IVR', number: null, action: 'create', reason: null, warnings: [], depends_on: ['recordings:1'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'time_condition', source_ref: 'timeconditions:1', name: 'Ish vaqti sharti', number: null, action: 'create', reason: null, warnings: [], depends_on: ['timegroups_groups:1'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'inbound_route', source_ref: 'incoming:1', name: '998712345601', number: '998712345601', action: 'create', reason: null, warnings: [], depends_on: ['ivr_details:1'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'inbound_route', source_ref: 'incoming:2', name: '998712345602', number: '998712345602', action: 'create', reason: null, warnings: [], depends_on: ['ringgroups:600'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'inbound_route', source_ref: 'incoming:3', name: "Har qanday DID", number: null, action: 'create', reason: null, warnings: [], depends_on: ['queues_config:700'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'outbound_route', source_ref: 'outbound_routes:1', name: 'Mobil', number: null, action: 'create', reason: null, warnings: [], depends_on: ['trunks:1', 'trunks:2'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'outbound_route', source_ref: 'outbound_routes:2', name: 'Xalqaro', number: null, action: 'create', reason: null, warnings: [], depends_on: ['trunks:1'], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'blacklist', source_ref: 'astdb:blacklist/998900000000', name: '+998900000000', number: '998900000000', action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
  { kind: 'feature_code', source_ref: 'featurecodes:voicemail', name: 'Ovozli pochta (*970)', number: '*970', action: 'create', reason: null, warnings: [], depends_on: [], replaceable: false, has_secret: false, weak_secret: false },
];

/** Manbadagi har qator rejada yoki shu yerda — jim yo'qolish yo'q (shartnoma §1). */
export const FREEPBX_FIXTURE_IGNORED: MigrationIgnoredItem[] = [
  { table: 'voicemail.conf', key: '1234', reason: 'vm_without_extension' },
  { table: 'kvstore', key: '*', reason: 'system_table' },
];

/** Tarjima qilinmaydi (shartnoma §1 — oxirgi qator): fayl nomi/kontekstlar texnik, serverga xos. */
export const FREEPBX_FIXTURE_WARNINGS: MigrationWarning[] = [
  { code: 'custom_dialplan_present', message: "extensions_custom.conf topildi (kontekstlar: ext-local-custom, from-internal-custom).", source_ref: null },
];

export const SSH_HOST_KEY_FINGERPRINT = 'SHA256:4b7c1a9e2d3f5c6b7a8d9e0f1c2b3a4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b';

/** Reja elementlarini FreePBX fixture asosida chuqur nusxalab qaytaradi — har ish o'ziga alohida holat. */
export function cloneFixturePlan(): MigrationPlanItem[] {
  return FREEPBX_FIXTURE_PLAN.map((item) => ({ ...item, warnings: [...item.warnings], depends_on: [...item.depends_on] }));
}

/** `by_kind`/`warnings`/`ignored`/`weak_secrets` — reja elementlari + global ogohlantirishlar + e'tiborsizlar sonidan hisoblanadi. */
export function summarizePlan(items: MigrationPlanItem[], ignoredCount: number, globalWarnings: number): MigrationSummary {
  const by_kind: MigrationSummary['by_kind'] = {};
  let itemWarnings = 0;
  let weakSecrets = 0;
  for (const item of items) {
    const row = by_kind[item.kind] ?? { create: 0, skip: 0, conflict: 0, unsupported: 0 };
    row[item.action] += 1;
    by_kind[item.kind] = row;
    itemWarnings += item.warnings.length;
    if (item.weak_secret) weakSecrets += 1;
  }
  return { by_kind, warnings: itemWarnings + globalWarnings, ignored: ignoredCount, weak_secrets: weakSecrets };
}

/** PATCH qoidasi (shartnoma §3/§4): conflict→skip|replace (replace faqat replaceable), create→skip, skip→create; aks holda ruxsat yo'q. */
export function migrationPatchAllowed(current: MigrationAction, next: MigrationPatchAction, replaceable: boolean): boolean {
  if (current === 'conflict') return next === 'skip' || (next === 'replace' && replaceable);
  if (current === 'create') return next === 'skip';
  if (current === 'skip') return next === 'create';
  return false;
}

/** Progress (0–100) bo'yicha joriy bosqich nomi — `fakeBackup.ts`dagi `jobStep()` bilan bir xil shakl. */
export function jobStep(steps: readonly string[], progress: number): string {
  const idx = Math.min(steps.length - 1, Math.floor((progress / 100) * steps.length));
  return steps[Math.max(0, idx)] ?? '';
}
