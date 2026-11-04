// Fake klient uchun boshlang'ich ma'lumot. Xotirada — sahifa yangilansa qayta tiklanadi (demo/test uchun yetarli).
import type {
  AlertLogEntry, AlertSettings, AuditEntry, Audio, BlacklistEntry, Call, Conference, ConfigRevision, Extension,
  FeatureCode, FeatureName,
  Holiday, InboundRoute, IpBan, Ivr, ManagedUser, MohClass, NotifySettings,
  OutboundRoute, Parking, Queue, RingGroup, SecurityEvent, SecuritySettings, SecurityStatsHour, SecurityStatsTopIp,
  SipSettings, SipTls, Target, TimeCondition, TimeGroup, Trunk, User,
  VoicemailBox, VoicemailMessage,
  // M3b — qarang ../../replica/m3b-contract.md
  AmoConfigResult, ApiKey, BitrixConfigResult, IntegrationsSettings, OneCSample, RecordingSettings, Webhook,
  WebhookDelivery,
  // M4a — qarang ../../replica/m4a-contract.md
  Device, DeviceKey, DeviceModel, DiscoveredDevice, ProvisionRequest, ProvisioningSettings,
  // M4b — qarang ../../replica/m4b-contract.md
  Backup, BackupSettings, RestoreJob,
  // M5a — qarang ../../replica/m5a-contract.md
  MigrationJob,
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  Announcement, CidSource, Contact, MiscApplication, MiscDestination, PageGroup, ParkingSettings, PinSet,
  // M12 A1/A2 — qarang ../../replica/m12-contract.md §A1/§A2
  DayNight, Disa,
} from './types';

export const SIM_ROLLBACK_MARK = 'SIMULYATSIYA_XATO';

// M7 §1 — admin haqiqiy backendda `permissions: ["*"]` qaytaradi (qarang `auth/permissions.ts` izohi);
// operatorning haqiqiy ruxsati `calls:read:own` — faqat shaxsiy kabinet va o'z qo'ng'iroqlari.
export const SEED_ADMIN: User = {
  id: 'u-admin', login: 'admin', full_name: 'Administrator', role: 'admin',
  permissions: ['*'], language: 'uz',
};
export const SEED_ADMIN_PASSWORD = 'Admin12345!';

export const SEED_OPERATOR: User = {
  id: 'u-operator', login: 'operator', full_name: 'Operator Olimova', role: 'operator',
  permissions: ['calls:read:own'], language: 'uz',
};
export const SEED_OPERATOR_PASSWORD = 'Operator12345!';

/** M7 — maxsus rol namunasi (isbot §5dagi "routing:edit + reports:view" bilan bir xil). */
export const SEED_CUSTOM_ROLE_ID = 'role-nazoratchi';
export const SEED_CUSTOM_ROLE_NAME = 'Nazoratchi';
export const SEED_CUSTOM_USER: User = {
  id: 'u-nazoratchi', login: 'nazoratchi', full_name: 'Nilufar Qosimova', role: SEED_CUSTOM_ROLE_NAME,
  permissions: ['routing:edit', 'reports:view'], language: 'uz',
};
export const SEED_CUSTOM_USER_PASSWORD = 'Nazoratchi12345!';

export type FakeRoleSeed = { id: string; name: string; permissions: string[]; is_system: boolean; updated_at: string };

export function seedRoles(): FakeRoleSeed[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'role-admin', name: 'admin', permissions: ['*'], is_system: true, updated_at: now },
    { id: 'role-operator', name: 'operator', permissions: ['calls:read:own'], is_system: true, updated_at: now },
    { id: SEED_CUSTOM_ROLE_ID, name: SEED_CUSTOM_ROLE_NAME, permissions: [...SEED_CUSTOM_USER.permissions], is_system: false, updated_at: now },
  ];
}

export function seedExtensions(): Extension[] {
  const now = '2026-10-27T05:00:00Z';
  const base = {
    dnd: false, forward_always: null, forward_busy: null, pickup_group: null, outbound_allowed: true, outbound_callerid: null,
    toll_blocked_at: null, toll_block_reason: null, webrtc: false, codecs: [] as string[],
    // M3c §1 — demo: 101 kiruvchi "always", chiquvchi "on_demand" (ikkisi mustaqil ekanini ko'rsatadi).
    recording: 'never' as const, recording_in: 'never' as const, recording_out: 'never' as const,
    // M9 A5 — qarang ../../replica/m9-freepbx-gaps-contract.md §A5. Sukut — yoqilgan.
    call_waiting: true,
  };
  // M3a §4 — demo uchun 101 va 102 brauzer softfoni (webrtc); operator (102) ham shu bilan sinaladi.
  const webrtcCodecs = ['opus', 'ulaw', 'alaw'];
  return [
    // M3b §1 — 101 "always" (yozib olish demo'si), 104 "on_demand" (*1), qolganlari "never".
    { id: 'e-101', number: '101', name: 'Dilnoza Karimova', enabled: true, status: 'online', contact: 'sip:101@10.0.0.12:5060', user_agent: 'Zoiper 5', updated_at: now, ...base, pickup_group: 'sales', webrtc: true, codecs: webrtcCodecs, recording: 'always', recording_in: 'always', recording_out: 'on_demand' },
    { id: 'e-102', number: '102', name: 'Sherzod Yusupov', enabled: true, status: 'offline', contact: null, user_agent: null, updated_at: now, ...base, webrtc: true, codecs: webrtcCodecs },
    { id: 'e-103', number: '103', name: 'Aziz Rahimov', enabled: true, status: 'unknown', contact: null, user_agent: null, updated_at: now, ...base },
    { id: 'e-104', number: '104', name: 'Malika Tosheva', enabled: true, status: 'online', contact: 'sip:104@10.0.0.18:5060', user_agent: 'MicroSIP', updated_at: now, ...base, forward_busy: '103', pickup_group: 'sales', recording: 'on_demand', recording_in: 'on_demand', recording_out: 'never' },
    // M2c §3 — toll-fraud demo: soatiga limitdan oshgani uchun bloklangan (Hodisalar/Toll-fraud bo'limlari bo'sh ko'rinmasin).
    { id: 'e-105', number: '105', name: 'Jahongir Mirzayev', enabled: true, status: 'offline', contact: null, user_agent: null, updated_at: now, ...base, toll_blocked_at: callAt(3), toll_block_reason: 'per_hour' },
    { id: 'e-106', number: '106', name: 'Zarina Nazarova', enabled: true, status: 'online', contact: 'sip:106@10.0.0.21:5061', user_agent: 'Grandstream GXP2170', updated_at: now, ...base, dnd: true },
    { id: 'e-107', number: '107', name: 'Bekzod Aliyev', enabled: false, status: 'offline', contact: null, user_agent: null, updated_at: now, ...base },
    { id: 'e-108', number: '108', name: 'Qabulxona — markaziy ofis, bosh kirish eshigi yonidagi umumiy telefon', enabled: true, status: 'online', contact: 'sip:108@10.0.0.9:5060', user_agent: 'Yealink T46U', updated_at: now, ...base, forward_always: '+998712000111' },
  ];
}

export function seedTrunks(): Trunk[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 't-uztelecom', name: 'Uztelecom — asosiy', host: 'sip.uztelecom.uz', port: 5060,
      match: ['195.158.0.0/16'], codecs: ['alaw', 'ulaw'], max_channels: 30, enabled: true,
      auth_mode: 'ip', username: null, has_password: false, from_domain: null, outbound_callerid: '998712000000',
      health: { state: 'ok', rtt_ms: 24, checked_at: now, registration: null, reason: null }, updated_at: now,
    },
    {
      id: 't-beeline', name: 'Beeline — zaxira', host: 'sip.beeline.uz', port: 5060,
      match: ['84.54.64.0/19'], codecs: ['alaw', 'ulaw', 'g729'], max_channels: 10, enabled: true,
      auth_mode: 'register', username: 'innova_beeline', has_password: true, from_domain: 'sip.beeline.uz', outbound_callerid: null,
      health: { state: 'unreachable', rtt_ms: null, checked_at: now, registration: 'rejected', reason: 'Parol notoʻgʻri (401)' }, updated_at: now,
    },
    {
      id: 't-ucell', name: 'Ucell — sinov', host: 'sip.ucell.uz', port: 5061,
      match: ['213.230.96.0/20'], codecs: ['ulaw'], max_channels: null, enabled: false,
      auth_mode: 'ip', username: null, has_password: false, from_domain: null, outbound_callerid: null,
      health: { state: 'disabled', rtt_ms: null, checked_at: null, registration: null, reason: null }, updated_at: now,
    },
  ];
}

export function seedInboundRoutes(): InboundRoute[] {
  const now = '2026-10-27T05:00:00Z';
  // M9 B3 — qarang ../../replica/m9-freepbx-gaps-contract.md §B3. Eski qatorlar — sukut (null/null/null).
  const base = { cid_name_prefix: null, alert_info: null, cid_lookup_source: null };
  return [
    { id: 'r-1', name: 'Asosiy raqam', did: '998712000000', cid: null, target: { id: 'e-101', kind: 'extension', label: '101 · Dilnoza Karimova', number: '101', broken: false }, enabled: true, updated_at: now, ...base },
    { id: 'r-2', name: 'Qabul (hammasi)', did: null, cid: null, target: { id: 'e-108', kind: 'extension', label: '108 · Qabulxona', number: '108', broken: false }, enabled: true, updated_at: now, ...base },
    {
      id: 'r-3', name: 'VIP mijoz', did: '998712000001', cid: '998901234567', target: { id: 'e-104', kind: 'extension', label: '104 · Malika Tosheva', number: '104', broken: false }, enabled: true, updated_at: now,
      cid_name_prefix: 'VIP: ', alert_info: 'info=alert-autoanswer', cid_lookup_source: { id: 'cs-telefon-kitobi', name: 'Telefon kitobi' },
    },
    { id: 'r-4', name: 'Eski aksiya raqami', did: '998712000099', cid: null, target: { id: 'e-199', kind: 'extension', label: 'Oʻchirilgan ichki raqam', number: '199', broken: true }, enabled: true, updated_at: now, ...base },
    { id: 'r-5', name: 'Qoʻllab-quvvatlash', did: '998712000005', cid: null, target: { id: 'tc-ish-vaqti', kind: 'time_condition', label: 'Ish vaqti', number: null, broken: false }, enabled: true, updated_at: now, ...base },
  ];
}

function callAt(hoursAgo: number): string {
  const d = new Date('2026-10-27T09:00:00Z');
  d.setHours(d.getHours() - hoursAgo);
  return d.toISOString();
}

const CALLER_NAMES = ['Anvar Yusupov', 'Dildora Nazarova', 'Botir Rashidov'];
// M9 CDR — PIN-to'plam yorlig'i: faqat ba'zi chiquvchi qo'ng'iroqlarda (accountcode) bor.
const PIN_LABELS = ['Mijoz — Tashkent', 'Mijoz — Samarqand'];

export function seedCalls(): Call[] {
  const rows: Call[] = [];
  const numbers = ['101', '102', '103', '104', '105', '106', '108'];
  const dispositions: Call['disposition'][] = ['answered', 'answered', 'answered', 'no_answer', 'busy', 'failed'];
  for (let i = 0; i < 42; i += 1) {
    const dir: Call['direction'] = i % 3 === 0 ? 'in' : i % 3 === 1 ? 'out' : 'internal';
    const disposition = dispositions[i % dispositions.length] ?? 'answered';
    const duration = disposition === 'answered' ? 20 + (i % 10) * 37 : 0;
    const billsec = disposition === 'answered' ? duration : 0;
    const ext = numbers[i % numbers.length] ?? '101';
    // M3b §1 — har 4-chi javob berilgan qo'ngiroqda demo yozuv bor (ext 101 "always" siyosatiga mos).
    const hasRecording = disposition === 'answered' && i % 4 === 0;
    rows.push({
      uniqueid: `1761${550000 + i}.${i}`,
      started_at: callAt(i * 7 + 1),
      src: dir === 'in' ? `99890${1000000 + i * 37}` : dir === 'out' ? ext : ext,
      dst: dir === 'in' ? ext : dir === 'out' ? `99871${2000000 + i * 13}` : numbers[(i + 1) % numbers.length] ?? '102',
      did: dir === 'in' ? '998712000000' : null,
      direction: dir,
      disposition,
      duration,
      billsec,
      trunk: dir === 'internal' ? null : i % 5 === 0 ? 'Beeline — zaxira' : 'Uztelecom — asosiy',
      recordings: hasRecording ? [{ id: `rec-${i}`, duration_s: billsec }] : [],
      // M9 CDR — faqat kiruvchida CallerID ismi tashqi AzBook'dan tanilgan bo'lishi mumkin.
      src_name: dir === 'in' && i % 6 === 0 ? CALLER_NAMES[i % CALLER_NAMES.length] ?? null : null,
      // M9 CDR — faqat chiquvchida (PIN-to'plam ishlatilgan bo'lsa) accountcode qayd etiladi.
      pin_label: dir === 'out' && i % 5 === 0 ? PIN_LABELS[i % PIN_LABELS.length] ?? null : null,
      // M10 B1 — sifat bahosi dinamik: `fake.ts`da baholash yaratilganda bu maydon toʻldiriladi.
      qa: null,
    });
  }
  return rows;
}

export function seedRevisions(): ConfigRevision[] {
  const base = 140;
  return Array.from({ length: 5 }, (_, i) => ({
    id: String(base - i),
    sha256: `${(base - i).toString(16)}fakehash`.padEnd(16, '0'),
    status: 'applied',
    created_at: callAt(i * 6),
    message: i === 0 ? 'Boshlangʻich konfiguratsiya' : `Reviziya r${base - i}`,
    user: i === 0 ? null : { id: SEED_ADMIN.id, login: SEED_ADMIN.login },
    summary: i === 0 ? null : `Oʻzgartirish: audit yozuvi #${base - i}`,
  }));
}

// ─────────────────────────── M1a seed — qarang ../../replica/m1a-contract.md ───────────────────────────

/** Tizim manzillari — tenant uchun bittadan, o'chirib bo'lmaydi (contract: "hangup va busy — tizim manzillari"). */
export const SYS_HANGUP_TARGET: Target = { id: 'sys-hangup', kind: 'hangup', label: 'Qoʻngʻiroqni yakunlash', number: null, broken: false };
export const SYS_BUSY_TARGET: Target = { id: 'sys-busy', kind: 'busy', label: 'Band ohangi', number: null, broken: false };

export function seedAudio(): Audio[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'au-greeting', name: 'Standart salomlashuv', duration_ms: 4200, format: 'wav', created_at: now },
    { id: 'au-notice', name: 'Ish vaqtidan tashqari eʼlon', duration_ms: 6800, format: 'wav', created_at: now },
  ];
}

export function seedTimeGroups(): TimeGroup[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'tg-ish-kunlari', name: 'Ish kunlari', ranges: [{ weekdays: [1, 2, 3, 4, 5], start: '09:00', end: '18:00' }], updated_at: now },
    { id: 'tg-shanba', name: 'Shanba — qisqa kun', ranges: [{ weekdays: [6], start: '10:00', end: '14:00' }], updated_at: now },
  ];
}

export function seedHolidays(): Holiday[] {
  return [
    { id: 'hd-yangi-yil', name: 'Yangi yil', day: '2026-01-01', recurring_yearly: true },
    { id: 'hd-navruz', name: 'Navruz bayrami', day: '2026-03-21', recurring_yearly: true },
    { id: 'hd-mustaqillik', name: 'Mustaqillik kuni', day: '2026-09-01', recurring_yearly: true },
  ];
}

export function seedQueues(): Queue[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'q-sotuv', name: 'Sotuv boʻlimi', number: '600', strategy: 'leastrecent',
      agent_ring_seconds: 20, retry_seconds: 5, wrapup_seconds: 10, max_wait_seconds: 180, max_callers: 20,
      announce_position: true, announce_frequency_seconds: 30, sla_seconds: 20, join_empty: true, record: false,
      members: [
        // Statik a'zo — tizim konfiguratsiyasidan, login/logout qila olmaydi (M2b §1).
        { extension: { id: 'e-101', number: '101', name: 'Dilnoza Karimova' }, penalty: 0, dynamic: false, logged_in: true, paused: false, pause_reason: null, state_at: now },
        // Dinamik a'zo — operator portalidan login/logout/pauza qiladi.
        { extension: { id: 'e-102', number: '102', name: 'Sherzod Yusupov' }, penalty: 1, dynamic: true, logged_in: true, paused: false, pause_reason: null, state_at: now },
      ],
      timeout_target: SYS_HANGUP_TARGET,
      live: { waiting: 2, members_online: 1 },
      moh_class: { id: 'moh-default', name: 'Standart' },
      updated_at: now,
    },
  ];
}

// ─────────────────────── M2b — qarang ../../replica/m2b-contract.md ───────────────────────

/** Admin/operator foydalanuvchi profillari (S31) — login/parol seed'dan ajri, chunki ManagedUser'da parol yo'q. */
export function seedUsers(extensions: Extension[]): ManagedUser[] {
  const now = '2026-10-27T05:00:00Z';
  const opExt = extensions.find((e) => e.id === 'e-102');
  return [
    {
      id: SEED_ADMIN.id, username: SEED_ADMIN.login, full_name: SEED_ADMIN.full_name, email: null,
      role: 'admin', extension: null, is_active: true, language: 'uz', must_change_password: false,
      totp_enabled: false, last_login_at: null, updated_at: now,
    },
    {
      id: SEED_OPERATOR.id, username: SEED_OPERATOR.login, full_name: SEED_OPERATOR.full_name, email: null,
      role: 'operator', extension: opExt ? { id: opExt.id, number: opExt.number, name: opExt.name } : null,
      is_active: true, language: 'uz', must_change_password: false, totp_enabled: false, last_login_at: null, updated_at: now,
    },
    {
      id: SEED_CUSTOM_USER.id, username: SEED_CUSTOM_USER.login, full_name: SEED_CUSTOM_USER.full_name, email: null,
      role: SEED_CUSTOM_ROLE_NAME, extension: null, is_active: true, language: 'uz', must_change_password: false,
      totp_enabled: false, last_login_at: null, updated_at: now,
    },
  ];
}

export function seedRingGroups(): RingGroup[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'rg-buxgalteriya', name: 'Buxgalteriya', number: '610', strategy: 'ringall', ring_seconds: 18,
      members: [
        { position: 1, extension: { id: 'e-103', number: '103', name: 'Aziz Rahimov' }, external_number: null },
        { position: 2, extension: { id: 'e-104', number: '104', name: 'Malika Tosheva' }, external_number: null },
        { position: 3, extension: null, external_number: '998901112233' },
      ],
      no_answer_target: SYS_BUSY_TARGET,
      callerid_prefix: null,
      updated_at: now,
    },
  ];
}

export function seedIvrs(greeting: Audio): Ivr[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'ivr-asosiy', name: 'Asosiy menyu', number: '700', greeting, invalid_audio: null,
      timeout_seconds: 10, repeats: 2, direct_dial: true,
      options: [
        { digit: '1', target: { id: 'q-sotuv', kind: 'queue', label: 'Sotuv boʻlimi', number: '600', broken: false } },
        { digit: '0', target: { id: 'e-108', kind: 'extension', label: '108 · Qabulxona', number: '108', broken: false } },
      ],
      timeout_target: { id: 'rg-buxgalteriya', kind: 'ring_group', label: 'Buxgalteriya', number: '610', broken: false },
      invalid_target: SYS_HANGUP_TARGET,
      updated_at: now,
    },
  ];
}

// ─────────────────────────── M1b seed — qarang ../../replica/m1b-contract.md ───────────────────────────

export function seedOutboundRoutes(trunks: Trunk[]): OutboundRoute[] {
  const now = '2026-10-27T05:00:00Z';
  const uztelecom = trunks.find((t) => t.id === 't-uztelecom');
  const beeline = trunks.find((t) => t.id === 't-beeline');
  const trunkRefs = [uztelecom, beeline]
    .filter((t): t is Trunk => !!t)
    .map((t, i) => ({ position: i + 1, trunk: { id: t.id, name: t.name, health_state: t.health.state } }));
  return [
    {
      id: 'or-uz', name: 'Mahalliy va mobil (UZ)', priority: 1, enabled: true,
      patterns: [
        { strip_prefix: '', pattern: '998XXXXXXXXX', add_prefix: '', callerid_match: '' },
        { strip_prefix: '', pattern: 'XXXXXXXXX', add_prefix: '998', callerid_match: '' },
      ],
      trunks: trunkRefs,
      callerid: null, override_extension_callerid: false, has_pin: false, international: false,
      extensions: 'all', updated_at: now, pin_set: null,
    },
  ];
}

export function seedSipSettings(): SipSettings {
  return {
    external_ip: '203.0.113.45', external_host: null, local_nets: ['192.168.0.0/16', '10.0.0.0/8'],
    sip_udp_port: 5060, sip_tls_port: 5061, rtp_start: 10000, rtp_end: 20000,
    codecs: ['alaw', 'ulaw', 'g722', 'opus'],
    detected: { public_ip: '203.0.113.45', local_ips: ['10.0.0.5', '192.168.1.5'] },
    restart_required: false, updated_at: '2026-10-27T05:00:00Z',
  };
}

export function seedAuditLog(): AuditEntry[] {
  return [
    {
      id: 'au-1', at: callAt(2), user: { id: SEED_ADMIN.id, login: SEED_ADMIN.login }, action: 'update',
      entity: 'trunk', entity_id: 't-beeline', label: 'Beeline — zaxira',
      diff: { password: ['***', '***'], outbound_callerid: [null, null] }, ip: '10.0.0.5',
    },
    {
      id: 'au-2', at: callAt(6), user: { id: SEED_ADMIN.id, login: SEED_ADMIN.login }, action: 'create',
      entity: 'outbound_route', entity_id: 'or-uz', label: 'Mahalliy va mobil (UZ)',
      diff: { name: [null, 'Mahalliy va mobil (UZ)'] }, ip: '10.0.0.5',
    },
    {
      id: 'au-3', at: callAt(24), user: null, action: 'login_failed',
      entity: 'session', entity_id: null, label: 'admin', diff: {}, ip: '203.0.113.9',
    },
  ];
}

export function seedMohClasses(files: Audio[]): MohClass[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'moh-default', name: 'default', shuffle: false, files: files.slice(0, 1), updated_at: now },
  ];
}

// ─────────────────────────── M1c seed — qarang ../../replica/m1c-contract.md ───────────────────────────

/** Qutilarning PIN'lari — serverda hech qachon qaytarilmaydi, fake saqlashi uchun alohida. */
export const SEED_VOICEMAIL_PIN = '1234';

export function seedVoicemailBoxes(extensions: Extension[]): VoicemailBox[] {
  const now = '2026-10-27T05:00:00Z';
  const ext = extensions.find((e) => e.id === 'e-101');
  return [
    {
      id: 'vm-101', mailbox: ext?.number ?? '101',
      extension: ext ? { id: ext.id, number: ext.number, name: ext.name } : null,
      email: 'dilnoza@innova.local', email_notify: true, telegram_notify: false, telegram_chat_id: null,
      attach_audio: true, greeting: null, has_pin: true, counts: { new: 0, old: 0 }, updated_at: now,
    },
  ];
}

export function seedVoicemailMessages(): VoicemailMessage[] {
  return [
    { id: 'INBOX/msg0001', folder: 'inbox', callerid: '998901112233', duration_s: 14, received_at: '2026-10-27T08:10:00Z', heard: false },
    { id: 'INBOX/msg0000', folder: 'inbox', callerid: '998933221100', duration_s: 42, received_at: '2026-10-26T15:42:00Z', heard: false },
    { id: 'Old/msg0002', folder: 'old', callerid: '998712000005', duration_s: 9, received_at: '2026-10-24T11:05:00Z', heard: true },
  ];
}

export function seedNotifySettings(): NotifySettings {
  return {
    smtp_host: 'smtp.yandex.ru', smtp_port: 587, smtp_tls: 'starttls', smtp_user: 'noreply@innova.local',
    has_smtp_password: true, from_email: 'noreply@innova.local', has_telegram_token: false,
    telegram_api_base: 'https://api.telegram.org', updated_at: '2026-10-27T05:00:00Z',
  };
}

export function seedSipTls(): SipTls {
  return { enabled: false, port: null, certificate: null, restart_required: false };
}

export function seedTimeConditions(ivr: Ivr): TimeCondition[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'tc-ish-vaqti', name: 'Ish vaqti', number: null,
      time_group: { id: 'tg-ish-kunlari', name: 'Ish kunlari' }, honor_holidays: true,
      open_target: { id: ivr.id, kind: 'ivr', label: ivr.name, number: ivr.number, broken: false },
      closed_target: SYS_HANGUP_TARGET,
      override: 'auto', toggle_code: '*21', state_now: 'open', updated_at: now,
    },
  ];
}

// ─────────────────────── M2a — qarang ../../replica/m2a-contract.md ───────────────────────

/** Standart kodlar — shartnoma §2 (tartib shu yerdagi kabi). */
export function seedFeatureCodes(): FeatureCode[] {
  const defaults: [FeatureName, string][] = [
    ['voicemail', '*97'], ['voicemail_other', '*98'], ['dnd_toggle', '*76'],
    ['cf_always_on', '*72'], ['cf_always_off', '*73'], ['cf_busy_on', '*90'], ['cf_busy_off', '*91'],
    ['pickup_group', '*8'], ['pickup_direct', '**'], ['park', '*70'], ['echo_test', '*43'], ['speaking_clock', '*60'],
    ['followme_toggle', '*21'],
  ];
  return defaults.map(([feature, code]) => ({ feature, code, default_code: code, enabled: true }));
}

export function seedConferences(): Conference[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'conf-boss', name: 'Rahbariyat yigʻilishi', number: '600', has_pin: true, has_admin_pin: true, record: true, max_members: 12, target_id: 'conf-boss', updated_at: now, live: { members: 3 } },
    { id: 'conf-sales', name: 'Sotuv boʻlimi', number: '601', has_pin: false, has_admin_pin: false, record: false, max_members: null, target_id: 'conf-sales', updated_at: now, live: { members: 0 } },
  ];
}
export const SEED_CONFERENCE_PIN = '2468';
export const SEED_CONFERENCE_ADMIN_PIN = '9999';

// ─────────────────────── M12 A1 — Kun/Tun rejimi (*28N) ───────────────────────
export function seedDayNight(dayTarget: Target, nightTarget: Target): DayNight[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'dn-asosiy', name: 'Asosiy', code: '0', mode: 'day',
      day_target: dayTarget, night_target: nightTarget, has_pin: false, updated_at: now,
    },
  ];
}

// ─────────────────────── M12 A2 — DISA ───────────────────────
export function seedDisa(): Disa[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'disa-tashqi', name: 'Tashqi', has_pin: true, allow_no_pin: false, cid_override: null,
      digit_timeout: 5, response_timeout: 10, max_attempts: 3, enabled: true, updated_at: now,
    },
  ];
}
export const SEED_DISA_PIN = '13579';

export function seedBlacklist(): BlacklistEntry[] {
  return [
    { number: '998998887766', reason: 'Spam qoʻngʻiroqlari', created_at: '2026-10-20T09:00:00Z' },
    { number: 'anonymous', reason: 'Yashirin raqamlar bloklangan', created_at: '2026-10-21T09:00:00Z' },
  ];
}

export function seedParking(): Parking {
  return {
    lot: '700', slots: '701-720', timeout_s: 60,
    parked: [{ slot: '701', callerid: '998901112233', parked_by: '101', since: '2026-10-27T05:58:00Z' }],
  };
}

// ─────────────────────── M2c — qarang ../../replica/m2c-contract.md ───────────────────────

export function seedSecuritySettings(): SecuritySettings {
  return {
    sip_guard: { enabled: true, max_failures: 5, window_s: 60, ban_s: 3600, trusted_nets: ['10.0.0.0/8'], trust_lan: true },
    toll_fraud: { enabled: true, max_concurrent_outbound: 0, ext_max_per_hour: 60, ext_international_per_day: 20 },
    require_2fa: 'off',
    updated_at: '2026-10-27T05:00:00Z',
  };
}

export function seedIpBans(): IpBan[] {
  return [
    { id: 'ban-1', ip: '203.0.113.77', reason: 'auto', failures: 7, note: null, created_at: callAt(2), expires_at: callAt(-1), created_by: null },
    { id: 'ban-2', ip: '198.51.100.23', reason: 'manual', failures: 0, note: 'Mijoz shikoyati — tekshirilmoqda', created_at: callAt(20), expires_at: null, created_by: SEED_ADMIN.login },
  ];
}

export function seedSecurityEvents(): SecurityEvent[] {
  return [
    { id: 'sev-1', at: callAt(2), kind: 'ip_banned', ip: '203.0.113.77', extension: null, details: { failures: 7, window_s: 60 } },
    { id: 'sev-2', at: callAt(3), kind: 'toll_blocked', ip: null, extension: '105', details: { reason: 'per_hour' } },
    { id: 'sev-3', at: callAt(26), kind: 'ban_expired', ip: '185.220.101.5', extension: null, details: null },
    { id: 'sev-4', at: callAt(30), kind: 'ip_unbanned', ip: '198.51.100.9', extension: null, details: null },
    { id: 'sev-5', at: callAt(48), kind: 'concurrent_limit', ip: null, extension: '101', details: { limit: 1 } },
  ];
}

/**
 * «Holat» 24/48/168-soatlik grafigi uchun toʻla (nolsiz boʻlmagan) qator — demo rejimida ham boʻsh koʻrinmasin.
 * Naqsh indeksga bogʻliq (deterministik) — testlar barqaror qiymat kutishi mumkin.
 */
export function seedSecurityStatsHours(hours: number): SecurityStatsHour[] {
  const now = new Date('2026-10-27T09:00:00Z');
  return Array.from({ length: hours }, (_, i) => {
    const agoHours = hours - 1 - i;
    const d = new Date(now);
    d.setMinutes(0, 0, 0);
    d.setHours(d.getHours() - agoHours);
    const spike = agoHours % 7 === 2 ? 9 : agoHours % 11 === 4 ? 4 : 0;
    const failures = spike + (agoHours % 5 === 0 ? 1 : 0);
    const blocked = spike >= 9 ? 1 : 0;
    return { hour: d.toISOString(), failures, blocked };
  });
}

export function seedSecurityTopIps(): SecurityStatsTopIp[] {
  return [
    { ip: '203.0.113.77', failures: 7, last_at: callAt(2), banned: true },
    { ip: '45.33.12.9', failures: 3, last_at: callAt(9), banned: false },
    { ip: '185.220.101.5', failures: 2, last_at: callAt(26), banned: false },
  ];
}

export function seedAlertSettings(): AlertSettings {
  return {
    chat_ids: ['-1001234567890'],
    dedup_s: 600,
    events: { ip_banned: true, toll_blocked: true, concurrent_limit: true, trunk_down: true, trunk_up: true },
    has_telegram_token: false,
    updated_at: '2026-10-27T05:00:00Z',
  };
}

export function seedAlertLog(): AlertLogEntry[] {
  return [
    { id: 'al-1', at: callAt(2), kind: 'ip_banned', key: '203.0.113.77', text: 'SIP hujum: 203.0.113.77 bloklandi (7 urinish / 60 s)', status: 'sent', error: null, sent_at: callAt(2) },
    { id: 'al-2', at: callAt(3), kind: 'toll_blocked', key: '105', text: 'Toll-fraud: 105 chiquvchi bloklandi (soatiga 60 limiti)', status: 'suppressed', error: null, sent_at: null },
    { id: 'al-3', at: callAt(30), kind: 'ip_unbanned', key: '198.51.100.9', text: 'IP 198.51.100.9 blokdan chiqarildi', status: 'disabled', error: null, sent_at: null },
    { id: 'al-4', at: callAt(50), kind: 'trunk_down', key: 't-beeline', text: 'Trunk «Beeline — zaxira» ishlamayapti: 401 Unauthorized', status: 'failed', error: 'no_token', sent_at: null },
  ];
}

// ─────────────────────── M3b — qarang ../../replica/m3b-contract.md ───────────────────────

export function seedApiKeys(): ApiKey[] {
  return [
    { id: 'ak-1c', name: '1C — ulanish', prefix: 'ipk_a1b2c3d4', scopes: ['calls:read', 'recordings:read', 'calls:originate'], created_at: callAt(72), last_used_at: callAt(1), expires_at: null, revoked_at: null },
    { id: 'ak-report', name: 'Hisobot skripti', prefix: 'ipk_9f8e7d6c', scopes: ['calls:read', 'extensions:read'], created_at: callAt(200), last_used_at: null, expires_at: callAt(-24 * 30), revoked_at: null },
  ];
}

export function seedWebhooks(): Webhook[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'wh-amo', name: 'amoCRM — eski integratsiya', url: 'http://10.0.5.20:8080/innova-hook', events: ['call.ringing', 'call.answered', 'call.ended'], include_internal: false, enabled: true, has_secret: true, disabled_reason: null, created_at: callAt(500), updated_at: now },
    { id: 'wh-broken', name: 'Sinov server', url: 'https://example.invalid/hook', events: ['call.ended'], include_internal: false, enabled: false, has_secret: true, disabled_reason: '24 soat davomida yetkazib bo‘lmadi (24h continuous failure)', created_at: callAt(900), updated_at: callAt(24) },
  ];
}

export function seedWebhookDeliveries(webhookId: string): WebhookDelivery[] {
  if (webhookId === 'wh-broken') {
    return [
      { id: 'dl-1', event_type: 'call.ended', status: 'dead', http_status: null, attempts: 8, next_retry_at: null, last_error: 'connect: nomi aniqlanmadi (DNS)', created_at: callAt(25) },
      { id: 'dl-2', event_type: 'call.ended', status: 'dead', http_status: null, attempts: 8, next_retry_at: null, last_error: 'connect: nomi aniqlanmadi (DNS)', created_at: callAt(30) },
    ];
  }
  return [
    { id: 'dl-3', event_type: 'call.ended', status: 'success', http_status: 200, attempts: 1, next_retry_at: null, last_error: null, created_at: callAt(1) },
    { id: 'dl-4', event_type: 'call.answered', status: 'success', http_status: 200, attempts: 1, next_retry_at: null, last_error: null, created_at: callAt(2) },
    { id: 'dl-5', event_type: 'call.ringing', status: 'failed', http_status: 500, attempts: 3, next_retry_at: callAt(-1), last_error: 'HTTP 500 Internal Server Error', created_at: callAt(3) },
  ];
}

export function seedBitrixConfig(): BitrixConfigResult {
  return {
    enabled: false,
    config: { has_webhook_url: false, create_lead: true, popup_max_delay_s: 20, default_user_id: null, application_token_set: false, hook_token: 'bx-hook-7f3a9c' },
    status: { state: 'disabled', last_ok_at: null, last_error: null, unmapped_extensions: [] },
    user_map: [],
    updated_at: '2026-10-27T05:00:00Z',
  };
}

export function seedAmoConfig(): AmoConfigResult {
  return {
    enabled: false,
    config: { base_url: '', token_set: false, unsorted_for_unknown: true, default_user_id: null },
    status: { state: 'disabled', last_ok_at: null, last_error: null, unmapped_extensions: [] },
    user_map: [],
    updated_at: '2026-10-27T05:00:00Z',
  };
}

export function seedOneCSamples(): OneCSample[] {
  return [
    { name: 'InnovaPBX_HTTPService.xml', title: 'HTTP-xizmat moduli (vebhuk qabul qiluvchi)' },
    { name: 'InnovaPBX_Ulanish.bsl', title: 'Ulanish modeli — ВызватьИзPBX / ЗаписьРазговора' },
    { name: "O'rnatish-qollanmasi-uz.pdf", title: "O'rnatish qo'llanmasi (oʻzbek)" },
  ];
}

export function seedIntegrationsSettings(): IntegrationsSettings {
  return { public_base_url: null, recording_link_ttl_s: 7 * 24 * 3600, updated_at: '2026-10-27T05:00:00Z' };
}

export function seedRecordingSettings(): RecordingSettings {
  return { retention_days: 90, external_only: false, updated_at: '2026-10-27T05:00:00Z' };
}

// ─────────────────────── M4a — qarang ../../replica/m4a-contract.md ───────────────────────
// `extensions` dagi webrtc=true (101/102) ga ip_phone biriktirib bo'lmaydi (422 `extension_webrtc`) —
// shu sabab demo apparatlar 103/105/106/108 ga bog'langan.

export function seedDevices(extensions: Extension[]): Device[] {
  const ref = (number: string): Device['extension'] => {
    const e = extensions.find((x) => x.number === number);
    return e ? { id: e.id, number: e.number, name: e.name } : null;
  };
  return [
    {
      id: 'dv-103', mac: '805ec0aa0001', vendor: 'yealink', model: 'T46U', label: 'Aziz — stol telefoni',
      extension: ref('103'), enabled: true, status: 'registered', provisioned_at: callAt(48), last_seen_at: callAt(1),
      last_ip: '10.0.0.41', firmware: '108.86.0.20', registered: true, keys_count: 2, updated_at: callAt(48),
    },
    {
      id: 'dv-106', mac: '00156501aa02', vendor: 'grandstream', model: 'GXP2170', label: 'Zarina — qabulxona',
      extension: ref('106'), enabled: true, status: 'registered', provisioned_at: callAt(500), last_seen_at: callAt(0.2),
      last_ip: '10.0.0.21', firmware: '1.0.11.16', registered: true, keys_count: 1, updated_at: callAt(500),
    },
    {
      id: 'dv-108', mac: '0c383e55aa03', vendor: 'fanvil', model: 'X4U', label: 'Qabulxona — kirish eshigi',
      extension: ref('108'), enabled: true, status: 'stale_config', provisioned_at: callAt(900), last_seen_at: callAt(30),
      last_ip: '10.0.0.9', firmware: '2.12.3', registered: true, keys_count: 0, updated_at: callAt(1),
    },
    {
      id: 'dv-105', mac: '805ec0aa0004', vendor: 'yealink', model: 'T43U', label: null,
      extension: ref('105'), enabled: true, status: 'never', provisioned_at: null, last_seen_at: null,
      last_ip: null, firmware: null, registered: false, keys_count: 0, updated_at: callAt(2),
    },
  ];
}

/** `dv-103` uchun — BLF 102 (sheriklar), speed dial bo'lim raqami. */
export function seedDeviceKeys(deviceId: string): DeviceKey[] {
  if (deviceId !== 'dv-103') return [];
  return [
    { idx: 1, type: 'blf', value: '102', label: 'Sherzod' },
    { idx: 2, type: 'speed_dial', value: '0712001122', label: 'Qabul' },
  ];
}

export function seedDiscoveredDevices(): DiscoveredDevice[] {
  return [
    {
      mac: '805ec0aabbcc', vendor: 'yealink', model: 'T46U', ip: '10.0.0.50',
      user_agent: 'Yealink SIP-T46U 108.86.0.20 805ec0aabbcc', firmware: '108.86.0.20',
      first_seen_at: callAt(3), last_seen_at: callAt(0.1), requests: 4,
    },
  ];
}

export function seedProvisionRequests(): ProvisionRequest[] {
  return [
    { at: callAt(0.1), ip: '10.0.0.50', mac: '805ec0aabbcc', vendor: 'yealink', path: '/prov/***/805ec0aabbcc.cfg', status_code: 404, reason: 'unknown_mac' },
    { at: callAt(1), ip: '10.0.0.41', mac: '805ec0aa0001', vendor: 'yealink', path: '/prov/***/805ec0aa0001.cfg', status_code: 200, reason: 'ok' },
    { at: callAt(5), ip: '203.0.113.9', mac: null, vendor: null, path: '/prov/xxxxx/y000000000000.cfg', status_code: 404, reason: 'bad_token' },
    { at: callAt(6), ip: '198.51.100.4', mac: null, vendor: null, path: '/prov/***/y000000000000.cfg', status_code: 403, reason: 'network_denied' },
    { at: callAt(20), ip: '10.0.0.21', vendor: 'grandstream', mac: '00156501aa02', path: '/prov/***/cfg00156501aa02', status_code: 404, reason: 'legacy_binary' },
  ];
}

export function seedProvisioningSettings(): ProvisioningSettings {
  return {
    url: 'http://pbx.innova.local/prov/8f2c91a4b3d7e6f5a1c0b9d8e7f6a5b4/',
    has_admin_password: false,
    allowed_networks: ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'],
    language: 'uz',
    timezone: 'Asia/Tashkent',
    ntp_server: 'pool.ntp.org',
    sip_transport: 'udp',
    sip_server_host: null,
    extra: { yealink: '', grandstream: '', fanvil: '' },
    updated_at: '2026-10-27T05:00:00Z',
  };
}

// ─────────────────────── M4b — qarang ../../replica/m4b-contract.md ───────────────────────

export function seedBackups(): Backup[] {
  return [
    {
      id: 'bk-3', kind: 'manual', status: 'ok',
      components: ['config', 'history', 'sounds', 'voicemail', 'certs'],
      step: null, progress: 100, file_name: 'innova-pbx1-20261028-030000-a1b2c3d4.ibk',
      sha256: '9f3a7c2e1d4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6d7c8b9a0f',
      manifest: {
        format: 'INNOVABK1', product_version: '1.4.0', alembic_revision: 'f3a9c1', created_at: callAt(28),
        source_host: 'pbx1.innova.local', components: ['config', 'history', 'sounds', 'voicemail', 'certs'],
        parts: [
          { name: 'db.dump', size: 18_874_368, sha256: 'aa11' }, { name: 'sounds.tar', size: 4_194_304, sha256: 'bb22' },
          { name: 'voicemail.tar', size: 2_097_152, sha256: 'cc33' },
        ],
        db_key_fp: 'e1f2a3b4c5d6e7f8',
      },
      size_bytes: 26_738_688,
      copies: [
        { target: 'local', status: 'ok', remote_path: '/var/lib/innova/backups/innova-pbx1-20261028-030000-a1b2c3d4.ibk', size_bytes: 26_738_688, error: null, uploaded_at: callAt(28) },
        { target: 's3', status: 'ok', remote_path: 'pbx1/innova-pbx1-20261028-030000-a1b2c3d4.ibk', size_bytes: 26_738_688, error: null, uploaded_at: callAt(28) },
        { target: 'sftp', status: 'ok', remote_path: '/backups/innova-pbx1-20261028-030000-a1b2c3d4.ibk', size_bytes: 26_738_688, error: null, uploaded_at: callAt(28) },
      ],
      created_by: null, created_at: callAt(28),
    },
    {
      id: 'bk-2', kind: 'scheduled', status: 'partial',
      components: ['config', 'history', 'sounds', 'voicemail', 'certs'],
      step: null, progress: 100, file_name: 'innova-pbx1-20261027-030000-e5f6a7b8.ibk',
      sha256: '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b',
      manifest: {
        format: 'INNOVABK1', product_version: '1.4.0', alembic_revision: 'f3a9c1', created_at: callAt(52),
        source_host: 'pbx1.innova.local', components: ['config', 'history', 'sounds', 'voicemail', 'certs'],
        parts: [{ name: 'db.dump', size: 18_350_080, sha256: 'dd44' }],
        db_key_fp: 'e1f2a3b4c5d6e7f8',
      },
      size_bytes: 24_117_248,
      copies: [
        { target: 'local', status: 'ok', remote_path: '/var/lib/innova/backups/innova-pbx1-20261027-030000-e5f6a7b8.ibk', size_bytes: 24_117_248, error: null, uploaded_at: callAt(52) },
        { target: 's3', status: 'ok', remote_path: 'pbx1/innova-pbx1-20261027-030000-e5f6a7b8.ibk', size_bytes: 24_117_248, error: null, uploaded_at: callAt(52) },
        { target: 'sftp', status: 'failed', remote_path: null, size_bytes: null, error: 'Ulanish vaqti tugadi (timeout, 30s)', uploaded_at: null },
      ],
      created_by: null, created_at: callAt(52),
    },
    {
      id: 'bk-1', kind: 'pre_restore', status: 'ok',
      components: ['config', 'history', 'sounds', 'voicemail', 'certs'],
      step: null, progress: 100, file_name: 'innova-pbx1-20260915-091500-c9d8e7f6.ibk',
      sha256: '5f6e7d8c9b0a1f2e3d4c5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e',
      manifest: {
        format: 'INNOVABK1', product_version: '1.3.2', alembic_revision: 'b7c2d1', created_at: '2026-09-15T09:15:00Z',
        source_host: 'pbx1.innova.local', components: ['config', 'history', 'sounds', 'voicemail', 'certs'],
        parts: [{ name: 'db.dump', size: 15_728_640, sha256: 'ee55' }],
        db_key_fp: 'e1f2a3b4c5d6e7f8',
      },
      size_bytes: 19_922_944,
      copies: [
        { target: 'local', status: 'ok', remote_path: '/var/lib/innova/backups/innova-pbx1-20260915-091500-c9d8e7f6.ibk', size_bytes: 19_922_944, error: null, uploaded_at: '2026-09-15T09:15:00Z' },
      ],
      created_by: { id: SEED_ADMIN.id, login: SEED_ADMIN.login }, created_at: '2026-09-15T09:15:00Z',
    },
  ];
}

export function seedBackupSettings(): BackupSettings {
  return {
    has_passphrase: true,
    schedule: { enabled: true, frequency: 'daily', weekday: 1, time: '03:00', components: ['config', 'history', 'sounds', 'voicemail', 'certs'] },
    targets: {
      local: { keep_last: 7 },
      s3: {
        enabled: true, endpoint: 'https://s3.eu-central-1.wasabisys.com', region: 'eu-central-1', bucket: 'innova-backups',
        prefix: 'pbx1/', access_key: 'AKIADEMO1234567890', has_secret_key: true, path_style: false, keep_last: 14,
      },
      sftp: { enabled: false, host: '', port: 22, user: '', has_password: false, has_key: false, folder: '/backups', host_key_fp: null, keep_last: 7 },
    },
    updated_at: callAt(28),
  };
}

export function seedRestoreJobs(): RestoreJob[] {
  return [
    {
      id: 'rj-1', backup_id: 'bk-2', source: 'local', status: 'ok', step: null, progress: 100, error: null,
      force: false, pre_restore_backup_id: 'bk-1', started_by: { id: SEED_ADMIN.id, login: SEED_ADMIN.login },
      started_at: '2026-09-15T09:10:00Z', finished_at: '2026-09-15T09:15:00Z',
    },
  ];
}

// ─────────────────────── M5a — qarang ../../replica/m5a-contract.md ───────────────────────

export function seedMigrationJobs(): MigrationJob[] {
  return [
    {
      id: 'mjob-1', source: 'upload', status: 'ok', step: null, progress: 100,
      source_meta: {
        file_name: 'fpbx-export-pbx-old.innova.local-20260914-021500.tar.gz', size_bytes: 19_914_752,
        host: 'pbx-old.innova.local', freepbx_version: '17.0.33.2', asterisk_version: '20.9.0', created_at: '2026-09-14T02:15:00Z',
      },
      summary: { by_kind: { extension: { create: 5, skip: 0, conflict: 1, unsupported: 0 }, trunk: { create: 2, skip: 0, conflict: 0, unsupported: 0 } }, warnings: 2, ignored: 2, weak_secrets: 1 },
      options: { rotate_weak_secrets: false },
      result: { created: { extension: 5, trunk: 2 }, skipped: 1, warnings: 2, revision_id: '141' },
      error: null, pre_import_backup_id: 'bk-pre-import-1', backup_ready: true,
      created_by: { id: SEED_ADMIN.id, login: SEED_ADMIN.login },
      created_at: '2026-09-14T02:14:00Z', finished_at: '2026-09-14T02:16:40Z',
    },
  ];
}

export function seedDeviceModels(): DeviceModel[] {
  return [
    { vendor: 'yealink', model: 'T31P', keys: 0, family: 'T3x' },
    { vendor: 'yealink', model: 'T33G', keys: 21, family: 'T3x' },
    { vendor: 'yealink', model: 'T43U', keys: 27, family: 'T4x' },
    { vendor: 'yealink', model: 'T46U', keys: 27, family: 'T4x' },
    { vendor: 'yealink', model: 'T54W', keys: 29, family: 'T5x' },
    { vendor: 'grandstream', model: 'GXP1628', keys: 4, family: 'GXP16xx' },
    { vendor: 'grandstream', model: 'GXP1760', keys: 6, family: 'GXP17xx' },
    { vendor: 'grandstream', model: 'GXP2170', keys: 24, family: 'GXP21xx' },
    { vendor: 'grandstream', model: 'GRP2614', keys: 4, family: 'GRP26xx' },
    { vendor: 'fanvil', model: 'X3U', keys: 10, family: 'X3' },
    { vendor: 'fanvil', model: 'X4U', keys: 20, family: 'X4' },
    { vendor: 'fanvil', model: 'X5U', keys: 20, family: 'X5' },
    { vendor: 'fanvil', model: 'X6U', keys: 40, family: 'X6' },
    { vendor: 'fanvil', model: 'X7', keys: 60, family: 'X7' },
  ];
}

// ─────────────────────────── M9 seed — qarang ../../replica/m9-freepbx-gaps-contract.md ───────────────────────────

export function seedAnnouncements(): Announcement[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'an-tanaffus', name: 'Tushlik tanaffusi', audio_file_id: 'au-notice', audio_name: 'Ish vaqtidan tashqari eʼlon',
      next_target: { id: 'tc-ish-vaqti', kind: 'time_condition', label: 'Ish vaqti', number: null, broken: false },
      allow_skip: true, repeat_key: '*', answer: true, target_id: 'tgt-an-tanaffus', updated_at: now,
    },
  ];
}

export function seedMiscDestinations(): MiscDestination[] {
  const now = '2026-10-27T05:00:00Z';
  return [{ id: 'md-faks', name: 'Faks liniyasi', dial: '0022', target_id: 'tgt-md-faks', updated_at: now }];
}

export function seedMiscApplications(): MiscApplication[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'ma-sardor', name: 'Direktorga toʻgʻridan-toʻgʻri', code: '*501',
      target: { id: 'e-101', kind: 'extension', label: '101 · Dilnoza Karimova', number: '101', broken: false },
      enabled: true, updated_at: now,
    },
  ];
}

export function seedParkingSettings(): ParkingSettings {
  return {
    lot_number: '700', first_slot: 701, slot_count: 20, timeout_s: 60, on_timeout: 'origin',
    timeout_target: null, moh_class_id: null, updated_at: '2026-10-27T05:00:00Z',
  };
}

export function seedPageGroups(): PageGroup[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    {
      id: 'pg-ofis', name: 'Butun ofis', number: '800', duplex: false, skip_busy: true, beep: true,
      members: [{ id: 'e-101', number: '101', name: 'Dilnoza Karimova' }, { id: 'e-102', number: '102', name: 'Sherzod Yusupov' }],
      updated_at: now,
    },
  ];
}

export function seedPinSets(): PinSet[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'ps-xalqaro', name: 'Xalqaro qoʻngʻiroqlar', record_in_cdr: true, pin_count: 2, used_by: [], updated_at: now },
  ];
}

export function seedContacts(): Contact[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'ct-1', name: 'Oqiljon Rustamov', company: '«Tezkor Yetkazib Berish» MChJ', note: 'Yetkazib beruvchi', numbers: [{ number: '998901112233', label: 'Mobil' }], updated_at: now },
    { id: 'ct-2', name: 'Dildora Ergasheva', company: null, note: null, numbers: [{ number: '998712223344', label: 'Ofis' }, { number: '998933334455', label: 'Mobil' }], updated_at: now },
  ];
}

export function seedCidSources(): CidSource[] {
  const now = '2026-10-27T05:00:00Z';
  return [
    { id: 'cs-telefon-kitobi', name: 'Telefon kitobi', kind: 'phonebook', http_url: null, http_json_path: null, timeout_ms: 1500, cache_ttl_s: 3600, enabled: true, used_by: [], updated_at: now },
  ];
}
