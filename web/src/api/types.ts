// M0 shartnomasi turlari — manba: ../../replica/m0-contract.md. Ekranlar shu tiplarga amal qiladi.

export type Lang = 'uz' | 'ru' | 'en';

/** M7 — endi istalgan rol NOMI (tizim rollari `admin`/`operator` yoki maxsus rol nomi). */
export type Role = string;

export type User = {
  id: string;
  login: string;
  full_name: string;
  role: Role;
  permissions: string[];
  language: Lang;
  /** M2b §3 — true bo'lsa, foydalanuvchi parolni almashtirmaguncha boshqa ekranga o'tolmaydi. */
  must_change_password?: boolean;
  /** M2b — foydalanuvchining o'z ichki raqami (yuqori paneldagi telefon belgisida); yo'q bo'lsa null. */
  extension?: { id: string; number: string; name: string } | null;
  /** M10 B2 — 2FA (TOTP) yoqilgan/majburiy ro'yxatdan o'tish kerakligi. */
  totp_enabled?: boolean;
  must_enroll_2fa?: boolean;
};

/** M10 B2 — login natijasi: tokenlar bilan tayyor ('ok') yoki 2FA kodi so'raladi ('totp_required'). */
export type AuthResult =
  | { status: 'ok'; access: string; refresh: string; user: User }
  | { status: 'totp_required'; challenge: string };

export type SetupPayload = {
  admin: { login: string; password: string; full_name: string };
  language: Lang;
  timezone: string;
  external_ip: string | null;
  local_nets: string[];
  /** 1.0.4 — o'rnatish kodi (install.sh konsolga chiqargan); eski serverlarda tekshiruv o'chiq. */
  code?: string | null;
};

export type ApplyStatus = 'applied' | 'unchanged' | 'rolled_back' | 'realtime';
export type ApplyResult = { status: ApplyStatus; revision: number | null; message: string | null };

export type ExtensionStatus = 'online' | 'offline' | 'unknown';

export type Extension = {
  id: string;
  number: string;
  name: string;
  enabled: boolean;
  status: ExtensionStatus;
  contact: string | null;
  user_agent: string | null;
  // M2a — qarang ../../replica/m2a-contract.md §1. Realtime: apply/reload talab qilmaydi.
  dnd: boolean;
  forward_always: string | null;
  forward_busy: string | null;
  pickup_group: string | null;
  // Tashqi qo'ng'iroq ruxsati va chiquvchi CallerID — ichki raqam darajasida (route darajasidagidan mustaqil).
  outbound_allowed: boolean;
  outbound_callerid: string | null;
  updated_at: string;
  // M2c §3 — qarang ../../replica/m2c-contract.md §3 (toll-fraud).
  toll_blocked_at: string | null;
  toll_block_reason: TollBlockReason | null;
  // M3a §2 — qarang ../../replica/m3a-contract.md §2 (brauzer softfoni). `true` — raqamning YAGONA qurilmasi brauzer.
  webrtc: boolean;
  /** Faqat `webrtc=true` bo'lsa maʼnoli; aks holda boʻsh. Ruxsat etilgan toʻplam: opus, g722, ulaw, alaw. */
  codecs: string[];
  // M3b §1 — qarang ../../replica/m3b-contract.md §1 (qo'ngiroq yozib olish).
  /** @deprecated — `recording_in` bilan bir xil (orqaga moslik). */
  recording: RecordingPolicy;
  // M3c §1 — yo'nalish bo'yicha MUSTAQIL siyosat: shu raqamga KELGAN / shu raqamdan CHIQQAN qo'ng'iroq.
  recording_in: RecordingPolicy;
  recording_out: RecordingPolicy;
  // M9 A5 — qarang ../../replica/m9-freepbx-gaps-contract.md §A5. Sukut — yoqilgan.
  call_waiting: boolean;
};

/** M3b §1 — `always`: har doim yoziladi; `never`: hech qachon; `on_demand`: `*1` bilan yoqiladi/oʻchiriladi. */
export type RecordingPolicy = 'always' | 'never' | 'on_demand';

/** M3a §4 — WebRTC softfon uchun ruxsat etilgan kodeklar va sukut toʻplami. */
export const WEBRTC_CODECS = ['opus', 'g722', 'ulaw', 'alaw'] as const;
export type WebrtcCodec = (typeof WEBRTC_CODECS)[number];

export type SipCredentials = { username: string; password: string; domain: string; port: number };
/** `PUT /extensions/{id}/secret` javobi — qo'lda kiritilgan yoki generatsiya qilingan parolni qo'llash. */
export type RotateSecretResult = { sip: SipCredentials; apply: ApplyResult };

export type TrunkHealthState = 'ok' | 'unreachable' | 'unknown' | 'disabled';
export type TrunkHealth = { state: TrunkHealthState; rtt_ms: number | null; checked_at: string | null };

export type TrunkAuthMode = 'ip' | 'register';
export type TrunkRegistration = 'registered' | 'rejected' | 'unregistered' | null;

export type Trunk = {
  id: string;
  name: string;
  host: string;
  port: number;
  match: string[];
  codecs: string[];
  max_channels: number | null;
  enabled: boolean;
  auth_mode: TrunkAuthMode;
  username: string | null;
  has_password: boolean;
  from_domain: string | null;
  outbound_callerid: string | null;
  health: TrunkHealth & { registration: TrunkRegistration; reason: string | null };
  updated_at: string;
};

export type TrunkTestResult = { ok: boolean; rtt_ms: number | null; detail: string };

export const TARGET_KINDS = [
  'extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy',
  // M9 A1/A2 — qarang ../../replica/m9-freepbx-gaps-contract.md §A1/§A2.
  'announcement', 'misc',
] as const;
export type TargetKind = (typeof TARGET_KINDS)[number];
export type Target = { id: string; kind: TargetKind; label: string; number: string | null; broken: boolean };
/** @deprecated — `Target` ga koʻchirildi (M1a: faqat ichki raqamdan koʻp turlar). */
export type RouteTarget = Target;

export type InboundRoute = {
  id: string;
  name: string;
  did: string | null;
  cid: string | null;
  target: Target;
  enabled: boolean;
  updated_at: string;
  // M9 B3 — qarang ../../replica/m9-freepbx-gaps-contract.md §B3.
  cid_name_prefix: string | null;
  alert_info: string | null;
  cid_lookup_source: { id: string; name: string } | null;
};

export type CallDirection = 'in' | 'out' | 'internal';
export type CallDisposition = 'answered' | 'no_answer' | 'busy' | 'failed';

export type Call = {
  uniqueid: string;
  started_at: string;
  src: string;
  dst: string;
  did: string | null;
  direction: CallDirection;
  disposition: CallDisposition;
  duration: number;
  billsec: number;
  trunk: string | null;
  // M3b §1 — qo'ngiroq bilan bog'langan yozuvlar (bo'lmasa — bo'sh massiv).
  recordings: CallRecordingRef[];
  // CDR kengaytirilgan qidiruv — qo'ng'iroq qiluvchining CallerID ismi (bo'lmasa — null).
  src_name: string | null;
  // CDR kengaytirilgan qidiruv — PIN-to'plam yorlig'i / accountcode (bo'lmasa — null).
  pin_label: string | null;
  // M10 B1 — sifat bahosi (bo'lmasa — null); alohida so'rovsiz jadvalda ko'rsatish uchun.
  // Backend `CallQaBadge` — `checklist_name` ham bor (eng oxirgi baholash belgisi).
  qa: { evaluation_id: string; checklist_name: string; score_pct: number } | null;
};

/** M3b §1 — qo'ngiroqlar roʻyxatida koʻrsatiladigan yozuv havolasi (toʻliq audio — alohida soʻrov bilan). */
export type CallRecordingRef = { id: string; duration_s: number };

export type SystemHealth = {
  asterisk: { up: boolean; version: string | null; uptime_s: number | null };
  db: { up: boolean };
  revision: number | null;
};

export type ConfigRevision = {
  id: string;
  sha256: string;
  status: string;
  created_at: string;
  message: string | null;
  user: { id: string; login: string } | null;
  summary: string | null;
};
export type RevisionDetail = ConfigRevision & { dialplan: string };
export type RevisionDiffAgainst = 'prev' | 'current';
export type RevisionDiff = { unified: string };
export type RestoreRevisionResult = { item: ConfigRevision; apply: ApplyResult; drift: true };

export type Paged<T> = { items: T[]; total: number };

export type ListExtensionsParams = { q?: string; page?: number; size?: number };

/** CDR kengaytirilgan qidiruv — matn maydoni uchun solishtirish usuli (sukut — `contains`). */
export type CallTextMatchMode = 'contains' | 'begins' | 'ends' | 'exact';
/** CDR kengaytirilgan qidiruv — yozuv bo'yicha filtr (sukut — `any`, ya'ni cheklovsiz). */
export type CallRecordingFilter = 'any' | 'with' | 'without';

/** FreePBX «CDR Reports» uslubidagi kengaytirilgan qidiruv — barchasi ixtiyoriy (M9 CDR). */
export type ListCallsParams = {
  from?: string; to?: string; q?: string; direction?: CallDirection; page?: number; size?: number;
  src?: string; src_mode?: CallTextMatchMode; src_not?: boolean;
  dst?: string; dst_mode?: CallTextMatchMode; dst_not?: boolean;
  did?: string; did_mode?: CallTextMatchMode; did_not?: boolean;
  /** Qo'ng'iroq qiluvchi ismi (CallerID name), har doim `contains`. */
  name?: string;
  /** Ichki raqam — `src` YOKI `dst` ga aniq teng. */
  ext?: string;
  /** Trunk nomi, aniq teng. */
  trunk?: string;
  /** PIN-to'plam yorlig'i / accountcode, `contains`. */
  account?: string;
  /** Vergul bilan ajratilgan `CallDisposition` ro'yxati (masalan `"answered,busy"`). */
  disposition?: string;
  min_duration?: number;
  max_duration?: number;
  recording?: CallRecordingFilter;
};
/** `kind` — vergul bilan ajratilgan roʻyxat (`"extension,queue"`), boʻsh — hammasi. */
export type ListTargetsParams = { kind?: string; q?: string };

export type CreateExtensionPayload = {
  number?: string;
  name: string;
  /** Berilmasa — server generatsiya qiladi (siyosat: 8-64 belgi, kamida 1 harf+1 raqam, raqamni oʻz ichiga olmasin). */
  password?: string;
  enabled?: boolean;
  dnd?: boolean;
  forward_always?: string | null;
  forward_busy?: string | null;
  pickup_group?: string | null;
  outbound_allowed?: boolean;
  outbound_callerid?: string | null;
  webrtc?: boolean;
  codecs?: string[];
  /** @deprecated — berilsa IKKALASINI (`recording_in`/`recording_out`) o'rnatadi; aniq maydonlar ustun turadi. */
  recording?: RecordingPolicy;
  recording_in?: RecordingPolicy;
  recording_out?: RecordingPolicy;
  call_waiting?: boolean;
};
export type UpdateExtensionPayload = {
  name?: string;
  enabled?: boolean;
  /** Aniq `null` — tozalash; umuman berilmagan (`undefined`) — oʻzgarmaydi (M2a §1). */
  dnd?: boolean;
  forward_always?: string | null;
  forward_busy?: string | null;
  pickup_group?: string | null;
  outbound_allowed?: boolean;
  outbound_callerid?: string | null;
  // M3a §2 — webrtc va codecs birgalikda tekshiriladi (422 `webrtc_codec`, field `codecs`).
  webrtc?: boolean;
  codecs?: string[];
  // M3b §1 / M3c §1 — qo'ngiroq yozib olish siyosati (eski maydon — ikkalasini birga o'rnatadi).
  recording?: RecordingPolicy;
  recording_in?: RecordingPolicy;
  recording_out?: RecordingPolicy;
  call_waiting?: boolean;
  updated_at: string;
};

// ─────────────────────────── M9 — qarang ../../replica/m9-freepbx-gaps-contract.md ───────────────────────────

/** B4 §4 — `/extensions/export.csv` ustunlari aynan shu tartibda. */
export const EXTENSIONS_CSV_COLUMNS = [
  'number', 'name', 'email', 'outbound_cid', 'language', 'voicemail', 'record_in', 'record_out',
  'max_contacts', 'call_waiting', 'enabled',
] as const;
export type ExtensionImportRowAction = 'create' | 'update' | 'skip' | 'error';
export type ExtensionImportRow = { row: number; number: string; action: ExtensionImportRowAction; message: string | null };
export type ImportExtensionsResult = {
  rows: ExtensionImportRow[];
  created: number;
  updated: number;
  errors: number;
  /** Faqat `dry_run=false` va yangi yaratilganlar bo'lsa — BIR MARTA qaytadi (number,sip_password). */
  secrets_csv: string | null;
};
export type ImportExtensionsParams = { file: File; dry_run: boolean };

export type CreateTrunkPayload = {
  name: string;
  host: string;
  port: number;
  match: string[];
  codecs: string[];
  max_channels: number | null;
  enabled: boolean;
  auth_mode: TrunkAuthMode;
  username?: string | null;
  /** Faqat yozish uchun; PATCH da berilmasa — oʻzgarmaydi. */
  password?: string | null;
  from_domain?: string | null;
  outbound_callerid?: string | null;
};
export type UpdateTrunkPayload = Partial<CreateTrunkPayload> & { updated_at: string };

export type CreateInboundRoutePayload = {
  name: string; did: string | null; cid: string | null; target_id: string; enabled: boolean;
  cid_name_prefix?: string | null; alert_info?: string | null; cid_lookup_source_id?: string | null;
};
export type UpdateInboundRoutePayload = Partial<CreateInboundRoutePayload> & { updated_at: string };

// ─────────────────────────── M1a — qarang ../../replica/m1a-contract.md ───────────────────────────

export type Usage = { kind: string; id: string; label: string; field: string };

export type Weekday = 1 | 2 | 3 | 4 | 5 | 6 | 7; // 1 = Dushanba

export type TimeRange = { weekdays: Weekday[]; start: string; end: string };
export type TimeGroup = { id: string; name: string; ranges: TimeRange[]; updated_at: string };
export type CreateTimeGroupPayload = { name: string; ranges: TimeRange[] };
export type UpdateTimeGroupPayload = Partial<CreateTimeGroupPayload> & { updated_at: string };

export type Holiday = { id: string; name: string; day: string; recurring_yearly: boolean };
export type CreateHolidayPayload = { name: string; day: string; recurring_yearly: boolean };
export type UpdateHolidayPayload = Partial<CreateHolidayPayload>;
export type ImportUzHolidaysPayload = { year: number };
export type ImportUzHolidaysResult = { items: Holiday[]; created: number; skipped: string[] };

export type TimeConditionOverride = 'auto' | 'force_open' | 'force_closed';
export type TimeCondition = {
  id: string;
  name: string;
  number: string | null;
  time_group: { id: string; name: string };
  honor_holidays: boolean;
  open_target: Target;
  closed_target: Target;
  override: TimeConditionOverride;
  toggle_code: string | null;
  state_now: 'open' | 'closed';
  updated_at: string;
};
export type CreateTimeConditionPayload = {
  name: string; number?: string | null; time_group_id: string; honor_holidays: boolean;
  open_target_id: string; closed_target_id: string; toggle_code?: string | null;
};
export type UpdateTimeConditionPayload = Partial<CreateTimeConditionPayload> & { updated_at: string };
export type OverrideTimeConditionPayload = { override: TimeConditionOverride };

export type AudioFormat = 'wav' | 'mp3' | 'ogg' | 'webm';
// Backend `AudioOut` — faqat shu 5 maydon (TTS orqali yaratilgan audio ham xususiyatsiz AudioOut qaytaradi).
export type Audio = {
  id: string; name: string; duration_ms: number; format: AudioFormat; created_at: string;
};

export type IvrOption = { digit: string; target: Target };
export type IvrOptionInput = { digit: string; target_id: string };
export type Ivr = {
  id: string;
  name: string;
  number: string | null;
  greeting: Audio;
  invalid_audio: Audio | null;
  timeout_seconds: number;
  repeats: number;
  direct_dial: boolean;
  options: IvrOption[];
  timeout_target: Target;
  invalid_target: Target;
  updated_at: string;
};
export type CreateIvrPayload = {
  name: string; number?: string | null; greeting_audio_id: string; invalid_audio_id?: string | null;
  timeout_seconds: number; repeats: number; direct_dial: boolean;
  options: IvrOptionInput[]; timeout_target_id: string; invalid_target_id: string;
};
export type UpdateIvrPayload = Partial<CreateIvrPayload> & { updated_at: string };

export type RingGroupStrategy = 'ringall' | 'hunt' | 'memoryhunt';
export type RingGroupMember = {
  position: number;
  extension: { id: string; number: string; name: string } | null;
  external_number: string | null;
};
export type RingGroup = {
  id: string;
  name: string;
  number: string | null;
  strategy: RingGroupStrategy;
  ring_seconds: number;
  members: RingGroupMember[];
  no_answer_target: Target;
  callerid_prefix: string | null;
  updated_at: string;
};
/** Bitta a'zo kiritish shakli — ichki raqam id'si YOKI tashqi raqam, ikkisi birga emas. */
export type RingGroupMemberInput = { extension_id: string; external_number?: never } | { external_number: string; extension_id?: never };
export type CreateRingGroupPayload = {
  name: string; number?: string | null; strategy: RingGroupStrategy; ring_seconds: number;
  members: RingGroupMemberInput[]; no_answer_target_id: string; callerid_prefix?: string | null;
};
export type UpdateRingGroupPayload = Partial<CreateRingGroupPayload> & { updated_at: string };

export type QueueStrategy = 'ringall' | 'leastrecent' | 'fewestcalls' | 'random' | 'rrmemory' | 'linear' | 'wrandom';
/** `dynamic`/`logged_in`/`paused`/`pause_reason`/`state_at` — M2b §1 (navbat a'zosi real holati). */
export type QueueMember = {
  extension: { id: string; number: string; name: string };
  penalty: number;
  dynamic: boolean;
  logged_in: boolean;
  paused: boolean;
  pause_reason: string | null;
  state_at: string;
};
export type QueueLive = { waiting: number; members_online: number };
export type Queue = {
  id: string;
  name: string;
  number: string | null;
  strategy: QueueStrategy;
  agent_ring_seconds: number;
  retry_seconds: number;
  wrapup_seconds: number;
  max_wait_seconds: number;
  max_callers: number | null;
  announce_position: boolean;
  announce_frequency_seconds: number;
  sla_seconds: number;
  join_empty: boolean;
  record: boolean;
  members: QueueMember[];
  timeout_target: Target;
  live: QueueLive | null;
  moh_class: { id: string; name: string } | null;
  updated_at: string;
};
export type CreateQueuePayload = {
  name: string; number?: string | null; strategy: QueueStrategy; agent_ring_seconds: number; retry_seconds: number;
  wrapup_seconds: number; max_wait_seconds: number; max_callers: number | null; announce_position: boolean;
  announce_frequency_seconds: number; sla_seconds: number; join_empty: boolean; record: boolean;
  members: { extension_id: string; penalty: number }[]; timeout_target_id: string; moh_class_id?: string | null;
};
export type UpdateQueuePayload = Partial<CreateQueuePayload> & { updated_at: string };

export type FlowEdgeLabel = 'target' | 'open' | 'closed' | 'timeout' | 'invalid' | 'no_answer' | string;
export type FlowNodeApi = { target: Target; edge: FlowEdgeLabel | null; children: FlowNodeApi[]; loop: boolean; broken: boolean };
export type FlowResult = { root: FlowNodeApi };

export type NumbersFreeParams = { from?: number; to?: number; limit?: number };

// ─────────────────────────── M1b — qarang ../../replica/m1b-contract.md ───────────────────────────

// Backend shartnomasi (schemas.OutboundPatternIn, ustun NOT NULL DEFAULT ''): bo'sh = '' — null 422 beradi.
export type OutboundPattern = { strip_prefix: string; pattern: string; add_prefix: string; callerid_match: string };
export type OutboundTrunkRef = { position: number; trunk: { id: string; name: string; health_state: TrunkHealthState } };
export type OutboundExtensionRef = { id: string; number: string; name: string };

export type OutboundRoute = {
  id: string;
  name: string;
  priority: number;
  enabled: boolean;
  patterns: OutboundPattern[];
  trunks: OutboundTrunkRef[];
  callerid: string | null;
  override_extension_callerid: boolean;
  has_pin: boolean;
  international: boolean;
  extensions: 'all' | OutboundExtensionRef[];
  updated_at: string;
  // M9 B1 — qarang ../../replica/m9-freepbx-gaps-contract.md §B1. Yakka PIN bilan birga ishlaydi — istalgani yetadi.
  pin_set: { id: string; name: string } | null;
};

export type CreateOutboundRoutePayload = {
  name: string;
  enabled: boolean;
  patterns: OutboundPattern[];
  trunk_ids: string[];
  callerid?: string | null;
  override_extension_callerid: boolean;
  /** 4–8 raqam; null — olib tashlash; berilmasa — oʻzgarmaydi (update'da). */
  pin?: string | null;
  international: boolean;
  extensions: 'all' | string[];
  pin_set_id?: string | null;
};
export type UpdateOutboundRoutePayload = Partial<CreateOutboundRoutePayload> & { updated_at: string };
export type OutboundOrderPayload = { ids: string[] };

export type OutboundSimulateParams = { extension: string; number: string };
export type OutboundStepResult = 'match' | 'no_pattern' | 'ext_not_allowed' | 'international_blocked' | 'disabled';
export type OutboundStep = { route: string; result: OutboundStepResult; detail: string };
export type OutboundSimulateResult = {
  allowed: boolean;
  route: { id: string; name: string } | null;
  dialed: string | null;
  callerid: string | null;
  trunks: { id: string; name: string; health_state: TrunkHealthState }[];
  steps: OutboundStep[];
  reason: string | null;
};

export type SipSettings = {
  external_ip: string | null;
  external_host: string | null;
  local_nets: string[];
  sip_udp_port: number;
  sip_tls_port: number | null;
  rtp_start: number;
  rtp_end: number;
  codecs: string[];
  detected: { public_ip: string | null; local_ips: string[] };
  restart_required: boolean;
  updated_at: string;
};
export type UpdateSipSettingsPayload = {
  external_ip?: string | null;
  external_host?: string | null;
  local_nets?: string[];
  sip_udp_port?: number;
  sip_tls_port?: number | null;
  rtp_start?: number;
  rtp_end?: number;
  codecs?: string[];
  updated_at: string;
};
export type RestartAsteriskResult = { ok: boolean };

export type DashboardTrunkHealth = { id: string; name: string; state: TrunkHealthState; registration: TrunkRegistration; reason: string | null };
export type DashboardLiveCall = { channel: string; from: string; to: string; state: string; duration_s: number; direction: CallDirection };
export type DashboardQueueLive = { id: string; name: string; waiting: number; members_online: number; longest_wait_s: number };
export type DashboardHourBucket = { hour: number; in: number; out: number; missed: number };
export type DashboardMissedCall = { uniqueid: string; started_at: string; src: string; did: string | null; called_back: boolean };
export type DashboardAlertLevel = 'warn' | 'danger';
export type DashboardAlertCode = 'trunk_down' | 'disk_low' | 'asterisk_down' | 'no_outbound_route' | 'revision_rolled_back';
export type DashboardAlert = { level: DashboardAlertLevel; code: DashboardAlertCode; text: string; link: string };

export type DashboardResult = {
  health: {
    asterisk: SystemHealth['asterisk'];
    db: SystemHealth['db'];
    disk: { used_pct: number; free_gb: number };
    trunks: DashboardTrunkHealth[];
  };
  live: { active_calls: number; calls: DashboardLiveCall[] };
  queues: DashboardQueueLive[];
  today: { total: number; answered: number; missed: number; out: number; avg_wait_s: number | null; by_hour: DashboardHourBucket[] };
  missed: DashboardMissedCall[];
  alerts: DashboardAlert[];
};

// ─────────────────────── Tizim holati (status) — pbx-klon vazifa (2026-11-02) ───────────────────────

export type DiskCategoryKey = 'recordings' | 'backups' | 'migrations' | 'voicemail' | 'logs';
export type DiskCategory = { key: DiskCategoryKey; bytes: number; files: number; cleanable: boolean };
export type SystemDisk = {
  total_gb: number;
  used_gb: number;
  free_gb: number;
  used_pct: number;
  categories: DiskCategory[];
};
export type SystemInternet = { up: boolean; dns_ok: boolean; latency_ms: number | null; target: string; error: string | null };
export type SipTransportInfo = { name: string; protocol: string; bind: string };
export type SystemSip = {
  asterisk_up: boolean;
  transports: SipTransportInfo[];
  endpoints_total: number;
  endpoints_online: number;
};
export type SystemStatus = {
  disk: SystemDisk;
  trunks: DashboardTrunkHealth[];
  internet: SystemInternet;
  sip: SystemSip;
};

export type CleanupIn = {
  recordings_older_than_days: number | null;
  backups_keep_last: number | null;
  migrations: boolean;
};
export type CleanupCategoryResult = { files: number; bytes: number };
export type CleanupResult = {
  recordings: CleanupCategoryResult;
  backups: CleanupCategoryResult;
  migrations: CleanupCategoryResult;
  total_bytes: number;
  errors: string[];
};

// ─────────────────────── Tarmoq sozlamalari (network) — M8 (../../replica/m8-network-contract.md) ───────────────────────

export type NetworkBackend = 'ifupdown' | 'netplan' | 'networkmanager' | 'unknown';
export type NetworkInterfaceKind = 'ethernet' | 'vlan' | 'bond' | 'bridge' | 'wireless' | 'other';
export type NetworkInterfaceMode = 'dhcp' | 'static' | 'manual' | 'unconfigured';

export type NetworkInterfaceConfig = { mode: NetworkInterfaceMode; address: string | null; gateway: string | null; mtu: number | null };
export type NetworkInterface = {
  name: string;
  mac: string | null;
  kind: NetworkInterfaceKind;
  oper_state: 'up' | 'down' | 'unknown';
  carrier: boolean;
  speed_mbps: number | null;
  mtu: number;
  live_ipv4: string[];
  live_ipv6: string[];
  editable: boolean;
  config: NetworkInterfaceConfig;
};

export type NetworkStaticRoute = { destination: string; gateway: string | null; interface: string | null; metric: number | null };
export type NetworkLiveRoute = NetworkStaticRoute & { protocol: string | null };

export type NetworkPending = { id: string; applied_at: string; expires_at: string; summary: string[] };
export type NetworkLastResult = { kind: 'confirmed' | 'rolled_back' | 'apply_failed'; at: string; message: string | null };

export type NetworkStateOut = {
  helper: { available: boolean; version: string | null; error: string | null };
  backend: NetworkBackend;
  editable: boolean;
  readonly_reason: string | null;
  hostname: string;
  dns: { servers: string[]; search: string[]; editable: boolean };
  default_gateway: { address: string | null; interface: string | null };
  interfaces: NetworkInterface[];
  routes: { static: NetworkStaticRoute[]; live: NetworkLiveRoute[] };
  pending: NetworkPending | null;
  last_result: NetworkLastResult | null;
};

export type NetworkInterfaceIn = { name: string; mode: 'dhcp' | 'static'; address: string | null; gateway: string | null; mtu: number | null };
export type NetworkRouteIn = { destination: string; gateway: string | null; interface: string | null; metric: number | null };
export type NetworkConfigIn = {
  hostname: string;
  dns: { servers: string[]; search: string[] };
  interfaces: NetworkInterfaceIn[];
  routes: NetworkRouteIn[];
  timeout_s: number;
};

export type NetworkFieldError = { field: string; message: string };
export type NetworkValidateResult = { ok: boolean; errors: NetworkFieldError[]; warnings: string[]; diff: string[] };

export type AuditAction = 'create' | 'update' | 'delete' | 'login' | 'login_failed' | 'restore' | 'restart' | 'override' | 'spy';
export type AuditDiff = Record<string, [unknown, unknown]>;
export type AuditEntry = {
  id: string;
  at: string;
  user: { id: string; login: string } | null;
  action: AuditAction;
  entity: string;
  entity_id: string | null;
  label: string | null;
  diff: AuditDiff;
  ip: string | null;
};
export type ListAuditParams = { entity?: string; user_id?: string; action?: AuditAction; from?: string; to?: string; q?: string; page?: number; size?: number };

export type MohClass = { id: string; name: string; shuffle: boolean; files: Audio[]; updated_at: string };
export type CreateMohClassPayload = { name: string; shuffle: boolean; file_ids: string[] };
export type UpdateMohClassPayload = Partial<CreateMohClassPayload> & { updated_at: string };

// ─────────────────────────── M1c — qarang ../../replica/m1c-contract.md ───────────────────────────

export type UpdateMePayload = { language: Lang };

export type VoicemailExtensionRef = { id: string; number: string; name: string };
export type VoicemailGreetingRef = { id: string; name: string };
export type VoicemailCounts = { new: number; old: number };

export type VoicemailBox = {
  id: string;
  mailbox: string;
  extension: VoicemailExtensionRef | null;
  email: string | null;
  email_notify: boolean;
  telegram_notify: boolean;
  telegram_chat_id: string | null;
  attach_audio: boolean;
  greeting: VoicemailGreetingRef | null;
  has_pin: boolean;
  counts: VoicemailCounts;
  updated_at: string;
};

/** `extension_id` YOKI `mailbox` — aynan bittasi (umumiy quti uchun ikkinchisi). */
export type CreateVoicemailBoxPayload = {
  extension_id?: string | null;
  mailbox?: string | null;
  pin: string;
  email?: string | null;
  email_notify?: boolean;
  telegram_notify?: boolean;
  telegram_chat_id?: string | null;
  attach_audio?: boolean;
  greeting_audio_id?: string | null;
};
export type UpdateVoicemailBoxPayload = {
  pin?: string | null;
  email?: string | null;
  email_notify?: boolean;
  telegram_notify?: boolean;
  telegram_chat_id?: string | null;
  attach_audio?: boolean;
  greeting_audio_id?: string | null;
  updated_at: string;
};
export type ListVoicemailBoxesParams = { extension_id?: string };

export type VoicemailMessageFolder = 'inbox' | 'old';
export type VoicemailMessage = {
  id: string;
  folder: VoicemailMessageFolder;
  callerid: string;
  duration_s: number;
  received_at: string;
  heard: boolean;
};

export type SmtpTls = 'none' | 'starttls' | 'tls';
export type NotifyChannel = 'email' | 'telegram';

export type NotifySettings = {
  smtp_host: string | null;
  smtp_port: number;
  smtp_tls: SmtpTls;
  smtp_user: string | null;
  has_smtp_password: boolean;
  from_email: string | null;
  has_telegram_token: boolean;
  telegram_api_base: string;
  updated_at: string | null;
};
/** Parol/token: berilmasa o'zgarmaydi, `""` — o'chiriladi. */
export type UpdateNotifySettingsPayload = {
  smtp_host?: string | null;
  smtp_port?: number;
  smtp_tls?: SmtpTls;
  smtp_user?: string | null;
  smtp_password?: string | null;
  from_email?: string | null;
  telegram_token?: string | null;
  telegram_api_base?: string | null;
  updated_at?: string | null;
};
export type NotifyTestPayload = { channel: NotifyChannel; to: string };
export type NotifyTestResult = { ok: boolean };

export type BadCertificateReason = 'key_mismatch' | 'expired' | 'not_pem' | 'encrypted_key';
export type SipTlsCertificate = { subject: string; issuer: string; not_after: string; self_signed: boolean; fingerprint_sha256: string };
export type SipTls = { enabled: boolean; port: number | null; certificate: SipTlsCertificate | null; restart_required: boolean };
export type SelfSignedTlsPayload = { common_name: string };

// ─────────────────────── M2a — qarang ../../replica/m2a-contract.md ───────────────────────

/** Tartib — shartnoma §2 roʻyxati (UI ham shu tartibda chiqaradi). */
export type FeatureName =
  | 'voicemail' | 'voicemail_other' | 'dnd_toggle' | 'cf_always_on' | 'cf_always_off' | 'cf_busy_on' | 'cf_busy_off'
  | 'pickup_group' | 'pickup_direct' | 'park' | 'echo_test' | 'speaking_clock'
  // M5b — qarang ../../replica/m5b-contract.md §1
  | 'followme_toggle';
export type FeatureCode = { feature: FeatureName; code: string; default_code: string; enabled: boolean };
export type UpdateFeatureCodePayload = { code?: string; enabled?: boolean };

export type Conference = {
  id: string;
  name: string;
  number: string;
  has_pin: boolean;
  has_admin_pin: boolean;
  record: boolean;
  max_members: number | null;
  /** `call_targets` dagi id — DestinationPicker/Target sifatida shu orqali bogʻlanadi. */
  target_id: string;
  updated_at: string;
  live: { members: number };
};
export type CreateConferencePayload = {
  name: string;
  number?: string;
  pin?: string | null;
  admin_pin?: string | null;
  record: boolean;
  max_members: number | null;
};
/** PIN/admin_pin: berilmasa — oʻzgarmaydi, aniq `null` — olib tashlanadi. */
export type UpdateConferencePayload = {
  name?: string;
  number?: string;
  pin?: string | null;
  admin_pin?: string | null;
  record?: boolean;
  max_members?: number | null;
  updated_at: string;
};

export type BlacklistEntry = { number: string; reason: string | null; created_at: string };
export type CreateBlacklistPayload = { number: string; reason?: string | null };
export type ListBlacklistParams = { q?: string };

export type ParkedCall = { slot: string; callerid: string; parked_by: string; since: string };
export type Parking = { lot: string; slots: string; timeout_s: number; parked: ParkedCall[] };

// ─────────────────────── M2b — qarang ../../replica/m2b-contract.md ───────────────────────

// §1 — navbat a'zosi amallari

export type QueueMemberAction = 'login' | 'logout' | 'pause' | 'unpause';
export type QueueMemberActionPayload = { reason?: string | null };
export type UpdateQueueMemberPayload = { penalty?: number; dynamic?: boolean };

// §2 — jonli monitoring (S29)

export type LiveCallDirection = 'inbound' | 'outbound' | 'internal';
export type LiveCallState = 'ringing' | 'up' | 'queued' | 'held' | 'parked';
export type LiveCall = {
  id: string;
  direction: LiveCallDirection;
  from: string;
  to: string;
  state: LiveCallState;
  started_at: string;
  answered_at: string | null;
  queue_id: string | null;
  extension: string | null;
  /** Asterisk kanal nomlari (masalan `PJSIP/t1-101-0000002a`) — kontraktda oddiy satrlar roʻyxati. */
  channels: string[];
};
export type LiveQueueWaiting = { from: string; since: string; position: number };
export type LiveAgentState = 'idle' | 'ringing' | 'busy' | 'paused' | 'offline' | 'unavailable';
export type LiveQueueAgent = {
  extension: string;
  name: string;
  dynamic: boolean;
  logged_in: boolean;
  paused: boolean;
  pause_reason: string | null;
  state: LiveAgentState;
  answered_today: number;
};
export type LiveQueue = { id: string; name: string; number: string | null; waiting: LiveQueueWaiting[]; agents: LiveQueueAgent[] };
export type LiveExtensionState = 'idle' | 'ringing' | 'busy' | 'unavailable' | 'dnd';
export type LiveExtension = { number: string; name: string; state: LiveExtensionState; dnd: boolean };
export type LiveSnapshot = {
  at: string;
  calls: LiveCall[];
  queues: LiveQueue[];
  extensions: LiveExtension[];
  asterisk?: 'down';
};
export type LiveSpyMode = 'listen' | 'whisper' | 'barge';
export type LiveSpyPayload = { call_id?: string; channel?: string; mode: LiveSpyMode };
export type LiveSpyResult = { status: 'calling' };

// §3 — foydalanuvchilar (S31)

export type ManagedUser = {
  id: string;
  username: string;
  full_name: string;
  email: string | null;
  role: Role;
  extension: { id: string; number: string; name: string } | null;
  is_active: boolean;
  language: Lang;
  must_change_password: boolean;
  last_login_at: string | null;
  /** M10 B2 — 2FA (TOTP) yoqilganligi; admin shu yerdan reset qila oladi. */
  totp_enabled: boolean;
  updated_at: string;
};
export type CreateUserPayload = {
  username: string;
  full_name: string;
  email?: string | null;
  role: Role;
  extension_id?: string | null;
  password: string;
  language?: Lang;
};
export type UpdateUserPayload = {
  username?: string;
  full_name?: string;
  email?: string | null;
  role?: Role;
  extension_id?: string | null;
  language?: Lang;
  is_active?: boolean;
  password?: string;
  updated_at: string;
};
export type ChangePasswordPayload = { current: string; new: string };

// M7 — rollar muharriri (qarang ../../replica/m7-roles-contract.md §2)

export type RoleOut = {
  id: string;
  name: string;
  permissions: string[];
  is_system: boolean;
  user_count: number;
  updated_at: string;
};
export type CreateRolePayload = { name: string; permissions: string[] };
export type UpdateRolePayload = { name?: string; permissions?: string[]; updated_at: string };

// §4 — mening kabinetim (S30)

export type MeExtensionOverview = {
  id: string;
  number: string;
  name: string;
  dnd: boolean;
  forward_always: string | null;
  forward_busy: string | null;
  outbound_allowed: boolean;
  voicemail_box_id: string | null;
  updated_at: string;
};
export type MeQueueOverview = { id: string; name: string; number: string | null; dynamic: boolean; logged_in: boolean; paused: boolean; pause_reason: string | null };
export type MeOverview = {
  user: ManagedUser;
  extension: MeExtensionOverview | null;
  queues: MeQueueOverview[];
  today: { answered: number; missed: number; talk_seconds: number };
};
export type PatchMeExtensionPayload = { dnd?: boolean; forward_always?: string | null; forward_busy?: string | null; updated_at: string };

// M3a §2 — GET /api/v1/me/softphone (qarang ../../replica/m3a-contract.md §2)

export type SoftphoneIceServer = { urls: string | string[]; username?: string; credential?: string };
export type SoftphoneInfo = {
  number: string;
  display_name: string;
  ws_path: string;
  ticket: string;
  ticket_expires_at: string;
  sip: { uri: string; auth_user: string; password: string; realm: string };
  ice_servers: SoftphoneIceServer[];
};

// §5 — analitika (S13)

export type ReportRangeParams = { from: string; to: string; queue_id?: string };
export type ReportsSummary = {
  from: string; to: string; timezone: string;
  total: number; inbound: number; outbound: number; internal: number;
  answered: number; missed: number; blocked: number;
  avg_wait_seconds: number | null; avg_talk_seconds: number | null; sla_percent: number | null; busiest_hour: number | null;
};
export type ReportsQueueRow = {
  queue_id: string; name: string; entered: number; answered: number; abandoned: number; timeout: number;
  avg_wait_seconds: number | null; max_wait_seconds: number | null; sla_percent: number | null;
};
export type ReportsAgentRow = {
  extension: string; name: string;
  answered: number; missed_ring: number; talk_seconds: number; avg_talk_seconds: number | null;
  login_seconds: number; pause_seconds: number;
};
export type ReportsHourlyRow = { hour: number; inbound: number; answered: number; missed: number };
export type ReportsDailyRow = { date: string; total: number; answered: number; missed: number };

// ─────────────────────── M2c — qarang ../../replica/m2c-contract.md ───────────────────────

// §1 — xavfsizlik sozlamalari (S33 «Sozlamalar»)

export type SipGuardConfig = { enabled: boolean; max_failures: number; window_s: number; ban_s: number; trusted_nets: string[]; trust_lan: boolean };
export type TollFraudConfig = { enabled: boolean; max_concurrent_outbound: number; ext_max_per_hour: number; ext_international_per_day: number };
/** M10 B2 — 2FA majburiyat siyosati: hech kim/adminlar/hamma. */
export type Require2faPolicy = 'off' | 'admins' | 'all';
export type SecuritySettings = { sip_guard: SipGuardConfig; toll_fraud: TollFraudConfig; require_2fa: Require2faPolicy; updated_at: string };
export type UpdateSecuritySettingsPayload = { sip_guard?: Partial<SipGuardConfig>; toll_fraud?: Partial<TollFraudConfig>; require_2fa?: Require2faPolicy; updated_at: string };

// §2 — SIP hujum himoyasi

export type BanReason = 'auto' | 'manual';
export type IpBan = {
  id: string;
  ip: string;
  reason: BanReason;
  failures: number;
  note: string | null;
  created_at: string;
  expires_at: string | null;
  created_by: string | null;
};
/** `ban_s` berilmasa — sozlamadagi qiymat ishlatiladi; `0` — muddatsiz. */
export type CreateBanPayload = { ip: string; note?: string | null; ban_s?: number };

export type SecurityStatsHour = { hour: string; failures: number; blocked: number };
export type SecurityStatsTopIp = { ip: string; failures: number; last_at: string; banned: boolean };
export type SecurityStatsTotals = { failures: number; blocked: number; bans_active: number; bans_period: number };
export type SecurityStats = { hours: SecurityStatsHour[]; top_ips: SecurityStatsTopIp[]; totals: SecurityStatsTotals };
export type SecurityStatsParams = { hours?: number };

export type SecurityEventKind = 'ip_banned' | 'ip_unbanned' | 'ban_expired' | 'toll_blocked' | 'toll_unblocked' | 'concurrent_limit';
export type SecurityEvent = { id: string; at: string; kind: SecurityEventKind; ip: string | null; extension: string | null; details: Record<string, unknown> | null };
export type ListSecurityEventsParams = { limit?: number; kind?: SecurityEventKind };

// §3 — toll-fraud

export type TollBlockReason = 'per_hour' | 'international_per_day';
export type TollBlock = { extension_id: string; number: string; name: string; blocked_at: string; reason: TollBlockReason };

// §4 — ogohlantirishlar (Telegram)

export type AlertEventFlags = { ip_banned: boolean; toll_blocked: boolean; concurrent_limit: boolean; trunk_down: boolean; trunk_up: boolean };
export type AlertSettings = { chat_ids: string[]; dedup_s: number; events: AlertEventFlags; has_telegram_token: boolean; updated_at: string };
export type UpdateAlertSettingsPayload = { chat_ids?: string[]; dedup_s?: number; events?: Partial<AlertEventFlags>; updated_at: string };
export type TestAlertResult = { sent: number };

export type AlertStatus = 'pending' | 'sent' | 'failed' | 'suppressed' | 'disabled';
export type AlertLogKind = SecurityEventKind | 'trunk_down' | 'trunk_up' | 'test';
export type AlertLogEntry = { id: string; at: string; kind: AlertLogKind; key: string | null; text: string; status: AlertStatus; error: string | null; sent_at: string | null };
export type ListAlertLogParams = { limit?: number; kind?: AlertLogKind };

// ─────────────────────── M3b — qarang ../../replica/m3b-contract.md ───────────────────────

// §1 — qo'ngiroq yozib olish (recording policy/types yuqorida, Extension/Call yonida)

export type RecordingAudio = { blob: Blob };

// §4 — API kalitlari va ochiq (public) API

export const API_KEY_SCOPES = ['calls:read', 'recordings:read', 'calls:originate', 'extensions:read', 'events:read'] as const;
export type ApiKeyScope = (typeof API_KEY_SCOPES)[number];

export type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  scopes: ApiKeyScope[];
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
};
export type CreateApiKeyPayload = { name: string; scopes: ApiKeyScope[]; expires_at?: string | null };
export type CreatedApiKey = { item: ApiKey; key: string };

// §3 — vebhuklar (webhooks)

export const WEBHOOK_EVENTS = ['call.ringing', 'call.answered', 'call.ended'] as const;
export type WebhookEvent = (typeof WEBHOOK_EVENTS)[number];

export type Webhook = {
  id: string;
  name: string;
  url: string;
  events: WebhookEvent[];
  include_internal: boolean;
  enabled: boolean;
  has_secret: boolean;
  disabled_reason: string | null;
  created_at: string;
  updated_at: string;
};
export type CreateWebhookPayload = { name: string; url: string; events: WebhookEvent[]; include_internal?: boolean; enabled?: boolean };
export type UpdateWebhookPayload = { name?: string; url?: string; events?: WebhookEvent[]; include_internal?: boolean; enabled?: boolean; updated_at: string };
export type CreatedWebhook = { item: Webhook; secret: string };
export type RotatedWebhookSecret = { secret: string };
export type TestWebhookResult = { queued: boolean };

export type DeliveryStatus = 'pending' | 'success' | 'failed' | 'dead';
export type WebhookDelivery = {
  id: string;
  event_type: WebhookEvent | 'test.ping';
  status: DeliveryStatus;
  http_status: number | null;
  attempts: number;
  next_retry_at: string | null;
  last_error: string | null;
  created_at: string;
};
export type ListDeliveriesParams = { status?: DeliveryStatus; limit?: number };

// §5 — CRM (Bitrix24 / amoCRM)

export const CRM_PROVIDERS = ['bitrix24', 'amocrm'] as const;
export type CrmProvider = (typeof CRM_PROVIDERS)[number];

export type CrmStatusState = 'ok' | 'error' | 'disabled';
export type CrmStatus = { state: CrmStatusState; last_ok_at: string | null; last_error: string | null; unmapped_extensions: string[] };
export type CrmUserMapSource = 'auto' | 'manual';
export type CrmUserMapEntry = { extension: string; crm_user_id: string | null; crm_user_name: string | null; source: CrmUserMapSource };

export type BitrixConfig = {
  has_webhook_url: boolean;
  create_lead: boolean;
  popup_max_delay_s: number;
  default_user_id: string | null;
  application_token_set: boolean;
  hook_token: string;
};
export type UpdateBitrixPayload = {
  enabled: boolean;
  /** Berilmasa — mavjud qiymat saqlanadi (secret-like, faqat qayta kiritilganda almashadi). */
  webhook_url?: string;
  create_lead: boolean;
  popup_max_delay_s: number;
  default_user_id: string | null;
  application_token?: string;
  updated_at: string;
};

export type AmoConfig = { base_url: string; token_set: boolean; unsorted_for_unknown: boolean; default_user_id: string | null };
export type UpdateAmoPayload = {
  enabled: boolean;
  base_url: string;
  token?: string;
  unsorted_for_unknown: boolean;
  default_user_id: string | null;
  updated_at: string;
};

export type CrmConfigResult<TConfig> = { enabled: boolean; config: TConfig; status: CrmStatus; user_map: CrmUserMapEntry[]; updated_at: string };
export type BitrixConfigResult = CrmConfigResult<BitrixConfig>;
export type AmoConfigResult = CrmConfigResult<AmoConfig>;
export type CrmTestResult = { ok: boolean; message: string; users_loaded: number | null };
export type UpdateCrmUserMapPayload = { entries: { extension: string; crm_user_id: string | null }[] };

// 1C — tayyor hujjat/namuna to'plami (alohida deliverer yo'q)

export type OneCSample = { name: string; title: string };

// §6 — sozlamalar (Integratsiyalar / Yozib olish)

export type IntegrationsSettings = { public_base_url: string | null; recording_link_ttl_s: number; updated_at: string };
export type UpdateIntegrationsSettingsPayload = { public_base_url?: string | null; recording_link_ttl_s?: number; updated_at: string };

export type RecordingSettings = { retention_days: number; external_only: boolean; updated_at: string };
export type UpdateRecordingSettingsPayload = { retention_days?: number; external_only?: boolean; updated_at: string };

// ─────────────────────── M4a — qarang ../../replica/m4a-contract.md ───────────────────────
// Apparatlarni avtoprovizioning (S35). Backend parallel yozilmoqda — maydon shakllari shartnomadan olingan.

export const DEVICE_VENDORS = ['yealink', 'grandstream', 'fanvil'] as const;
export type DeviceVendor = (typeof DEVICE_VENDORS)[number];

/** `never` — hech so'ramagan, `provisioned` — config oldi, `registered` — PJSIP contact shu IP'dan,
 * `stale_config` — config_hash joriy render'dan farq qiladi (masalan parol o'zgargan). */
export const DEVICE_STATUSES = ['never', 'provisioned', 'registered', 'stale_config'] as const;
export type DeviceStatus = (typeof DEVICE_STATUSES)[number];

export const DEVICE_KEY_TYPES = ['blf', 'speed_dial', 'line', 'park', 'dnd', 'none'] as const;
export type DeviceKeyType = (typeof DEVICE_KEY_TYPES)[number];

export type DeviceExtensionRef = { id: string; number: string; name: string };

export type DeviceKey = { idx: number; type: DeviceKeyType; value: string | null; label: string | null };

export type Device = {
  id: string;
  mac: string;
  vendor: DeviceVendor;
  model: string;
  label: string | null;
  extension: DeviceExtensionRef | null;
  enabled: boolean;
  status: DeviceStatus;
  provisioned_at: string | null;
  last_seen_at: string | null;
  last_ip: string | null;
  firmware: string | null;
  registered: boolean;
  keys_count: number;
  updated_at: string;
};
export type ListDevicesParams = { extension_id?: string; vendor?: DeviceVendor | ''; q?: string };
export type CreateDevicePayload = { mac: string; vendor: DeviceVendor; model: string; extension_id: string; label?: string; keys?: DeviceKey[] };
export type UpdateDevicePayload = { label?: string; extension_id?: string; enabled?: boolean; notes?: string; updated_at: string };
export type UpdateDeviceKeysPayload = { keys: DeviceKey[] };
/** `POST /devices/{id}/resync` — faqat NOTIFY yuboradi, apparat holati keyingi so'rovda yangilanadi. */
export type ResyncDeviceResult = { ok: true };
export type DeviceConfigResult = { filename: string; content: string };

export type DiscoveredDevice = {
  mac: string;
  vendor: DeviceVendor | null;
  model: string | null;
  ip: string;
  user_agent: string;
  firmware: string | null;
  first_seen_at: string;
  last_seen_at: string;
  requests: number;
};
export type AssignDiscoveredDevicePayload = { extension_id: string; model?: string; label?: string };

export type DeviceModel = { vendor: DeviceVendor; model: string; keys: number; family: string };

export type ProvisionRequestReason = 'unknown_mac' | 'bad_token' | 'network_denied' | 'rate_limited' | 'ok' | 'legacy_binary';
export type ProvisionRequest = {
  at: string; ip: string; mac: string | null; vendor: DeviceVendor | null; path: string; status_code: number; reason: ProvisionRequestReason;
};
export type ListProvisionRequestsParams = { mac?: string; ip?: string; limit?: number };

export type SipTransport = 'udp' | 'tcp' | 'tls';
export type ProvisioningExtra = { yealink: string; grandstream: string; fanvil: string };
export type ProvisioningSettings = {
  url: string;
  has_admin_password: boolean;
  allowed_networks: string[];
  language: 'uz' | 'ru' | 'en';
  timezone: string;
  ntp_server: string;
  sip_transport: SipTransport;
  sip_server_host: string | null;
  extra: ProvisioningExtra;
  updated_at: string;
};
export type UpdateProvisioningSettingsPayload = {
  allowed_networks?: string[];
  language?: 'uz' | 'ru' | 'en';
  timezone?: string;
  ntp_server?: string;
  sip_transport?: SipTransport;
  sip_server_host?: string | null;
  extra?: Partial<ProvisioningExtra>;
  /** Faqat yoziladi — javobda hech qachon qaytmaydi. */
  admin_password?: string;
  updated_at: string;
};
export type RotateProvisioningTokenResult = { url: string; updated_at: string };

// ─────────────────────── M4b — qarang ../../replica/m4b-contract.md ───────────────────────
// Zaxira nusxa va tiklash (S34 «Zaxira»). Backend parallel yozilmoqda — maydon shakllari shartnomadan olingan.

export const BACKUP_KINDS = ['scheduled', 'manual', 'pre_restore', 'uploaded', 'pre_import'] as const;
export type BackupKind = (typeof BACKUP_KINDS)[number];

export const BACKUP_STATUSES = ['running', 'ok', 'partial', 'failed'] as const;
export type BackupStatus = (typeof BACKUP_STATUSES)[number];

/** Sukut: hammasi; `recordings` ixtiyoriy (katta hajm). */
export const BACKUP_COMPONENTS = ['config', 'history', 'sounds', 'voicemail', 'recordings', 'certs'] as const;
export type BackupComponent = (typeof BACKUP_COMPONENTS)[number];

export const BACKUP_TARGET_KINDS = ['local', 's3', 'sftp'] as const;
export type BackupTargetKind = (typeof BACKUP_TARGET_KINDS)[number];

export const BACKUP_COPY_STATUSES = ['pending', 'ok', 'failed', 'deleted'] as const;
export type BackupCopyStatus = (typeof BACKUP_COPY_STATUSES)[number];

export type BackupCopy = {
  target: BackupTargetKind;
  status: BackupCopyStatus;
  remote_path: string | null;
  size_bytes: number | null;
  error: string | null;
  uploaded_at: string | null;
};

export type BackupManifestPart = { name: string; size: number; sha256: string };
export type BackupManifest = {
  format: string;
  product_version: string;
  alembic_revision: string;
  created_at: string;
  source_host: string;
  components: BackupComponent[];
  parts: BackupManifestPart[];
  db_key_fp: string;
};

export type Backup = {
  id: string;
  kind: BackupKind;
  status: BackupStatus;
  components: BackupComponent[];
  step: string | null;
  progress: number | null;
  file_name: string | null;
  sha256: string | null;
  manifest: BackupManifest | null;
  size_bytes: number | null;
  copies: BackupCopy[];
  created_by: { id: string; login: string } | null;
  created_at: string;
};

export type CreateBackupPayload = { components: BackupComponent[] };

export type BackupJobKind = 'backup' | 'restore';
export type BackupJobStatus = 'running' | 'ok' | 'failed';
/** `POST /backups` va `POST /backups/{id}/restore` 202 javobi — faqat navigatsiya uchun, holat `GET /backups/jobs/{id}`dan. */
export type BackupJob = { kind: BackupJobKind; id: string };
/** `GET /backups/jobs/{id}` — maintenance paytida ham, tiklashdan keyin sessiya bekor bo'lsa ham ochiq (sirsiz, faqat holat). */
export type BackupJobState = { kind: BackupJobKind; status: BackupJobStatus; step: string | null; progress: number | null; error: string | null };

export type RestoreJobSource = 'local' | 'upload';
export type RestoreJobStatus = 'running' | 'ok' | 'failed';
export type RestoreJob = {
  id: string;
  backup_id: string | null;
  source: RestoreJobSource;
  status: RestoreJobStatus;
  step: string | null;
  progress: number | null;
  error: string | null;
  force: boolean;
  pre_restore_backup_id: string | null;
  started_by: { id: string; login: string } | null;
  started_at: string;
  finished_at: string | null;
};

export type InspectBackupPayload = { passphrase?: string };
export type InspectBackupResult = { manifest: BackupManifest; checks: { sha256: 'ok' }; compatible: boolean; warnings: string[] };

export type RestoreBackupPayload = { passphrase?: string; confirm: 'TIKLASH'; force?: boolean };

export type BackupScheduleFrequency = 'daily' | 'weekly';
export type BackupSchedule = { enabled: boolean; frequency: BackupScheduleFrequency; weekday: Weekday; time: string; components: BackupComponent[] };

export type BackupLocalTarget = { keep_last: number };
export type BackupS3Target = {
  enabled: boolean; endpoint: string; region: string; bucket: string; prefix: string; access_key: string;
  has_secret_key: boolean; path_style: boolean; keep_last: number;
};
export type BackupSftpTarget = {
  enabled: boolean; host: string; port: number; user: string; has_password: boolean; has_key: boolean;
  folder: string; host_key_fp: string | null; keep_last: number;
};
export type BackupSettings = {
  has_passphrase: boolean;
  schedule: BackupSchedule;
  targets: { local: BackupLocalTarget; s3: BackupS3Target; sftp: BackupSftpTarget };
  updated_at: string;
};

export type UpdateBackupSettingsPayload = {
  schedule?: BackupSchedule;
  targets?: {
    local?: BackupLocalTarget;
    s3?: Omit<BackupS3Target, 'has_secret_key'> & { secret_key?: string };
    sftp?: Omit<BackupSftpTarget, 'has_password' | 'has_key' | 'host_key_fp'> & { password?: string; key?: string };
  };
  updated_at: string;
};

export type UpdateBackupPassphrasePayload = { passphrase: string; current?: string };

export type TestBackupTargetPayload = { target: 's3' | 'sftp' };
export type TestBackupTargetResult = { ok: boolean; error?: string; host_key_fp?: string };
export type TrustSftpHostKeyPayload = { host_key_fp: string };

// ─────────────────────── M5a — qarang ../../replica/m5a-contract.md ───────────────────────
// FreePBX'dan ko'chirish (S36 «Ko'chirish»). Backend parallel yozilmoqda — maydon shakllari shartnomadan olingan.

export const MIGRATION_KINDS = [
  'audio', 'moh', 'time_group', 'holiday', 'extension', 'voicemail', 'trunk', 'ring_group',
  'queue', 'conference', 'announcement', 'ivr', 'time_condition', 'inbound_route',
  'outbound_route', 'blacklist', 'feature_code',
] as const;
export type MigrationKind = (typeof MIGRATION_KINDS)[number];

export const MIGRATION_SOURCES = ['upload', 'ssh'] as const;
export type MigrationSource = (typeof MIGRATION_SOURCES)[number];

export const MIGRATION_JOB_STATUSES = ['uploaded', 'analyzing', 'analyzed', 'applying', 'ok', 'failed'] as const;
export type MigrationJobStatus = (typeof MIGRATION_JOB_STATUSES)[number];

export const MIGRATION_ACTIONS = ['create', 'skip', 'conflict', 'unsupported'] as const;
export type MigrationAction = (typeof MIGRATION_ACTIONS)[number];

export const MIGRATION_PATCH_ACTIONS = ['skip', 'replace', 'create'] as const;
export type MigrationPatchAction = (typeof MIGRATION_PATCH_ACTIONS)[number];

export type MigrationSourceMeta = {
  file_name: string | null;
  size_bytes: number | null;
  host: string | null;
  freepbx_version: string | null;
  asterisk_version: string | null;
  created_at: string | null;
};

export type MigrationKindSummary = { create: number; skip: number; conflict: number; unsupported: number };
export type MigrationSummary = {
  by_kind: Partial<Record<MigrationKind, MigrationKindSummary>>;
  warnings: number;
  ignored: number;
  weak_secrets: number;
};

export type MigrationJobOptions = { rotate_weak_secrets: boolean };

export type MigrationResult = {
  created: Partial<Record<MigrationKind, number>>;
  skipped: number;
  warnings: number;
  revision_id: string | null;
};

export type MigrationJob = {
  id: string;
  source: MigrationSource;
  status: MigrationJobStatus;
  step: string | null;
  progress: number;
  source_meta: MigrationSourceMeta | null;
  summary: MigrationSummary | null;
  options: MigrationJobOptions;
  result: MigrationResult | null;
  error: { code: string; message: string } | null;
  pre_import_backup_id: string | null;
  /** CTO qo'shimchasi: zaxira paroli o'rnatilganmi — `false` bo'lsa Qo'llash bosqichi bloklanadi. */
  backup_ready: boolean;
  created_by: { id: string; login: string } | null;
  created_at: string;
  finished_at: string | null;
};

export type MigrationPlanWarning = { code: string; message: string };
export type MigrationPlanItem = {
  kind: MigrationKind;
  source_ref: string;
  name: string;
  number: string | null;
  action: MigrationAction;
  reason: string | null;
  warnings: MigrationPlanWarning[];
  depends_on: string[];
  replaceable: boolean;
  has_secret: boolean;
  weak_secret: boolean;
};

export type MigrationIgnoredItem = { table: string; key: string; reason: string };
export type MigrationWarning = { code: string; message: string; source_ref: string | null };

export type ListMigrationPlanParams = {
  kind?: MigrationKind;
  action?: MigrationAction;
  q?: string;
  page?: number;
  page_size?: number;
};

export type SshTestPayload = {
  host: string;
  port: number;
  username: string;
  password?: string;
  private_key?: string;
};
export type SshTestResult = { ok: boolean; host_key_fp: string | null; error?: string };
export type SshFetchPayload = SshTestPayload & { host_key_fp: string };

export type PatchMigrationPlanItem = { kind: MigrationKind; source_ref: string; action: 'skip' | 'replace' | 'create' };
export type PatchMigrationPlanPayload = { items: PatchMigrationPlanItem[] };

export type ApplyMigrationPayload = { confirm: 'KOCHIRISH'; options: MigrationJobOptions };

// ─────────────────────── M5b — qarang ../../replica/m5b-contract.md ───────────────────────

/** `ring_all` — hammasi birga; `sequential` — ro'yxat tartibida, har biriga `ring_seconds`. */
export type FollowMeStrategy = 'ring_all' | 'sequential';
export type FollowMe = {
  enabled: boolean;
  /** 1..6 ta: ichki raqam (o'zi emas) yoki tashqi raqam; takror yo'q. */
  numbers: string[];
  strategy: FollowMeStrategy;
  /** Faqat `ring_all`da ma'noli — ichki raqam ham ro'yxat bilan birga jiringlaydi. */
  include_extension: boolean;
  ring_seconds: number;
  /** Tashqi raqam javob bersa «1 ni bosing» — mobil ovozli pochtasi qo'ng'iroqni «yeb» qo'ymasin. */
  confirm: boolean;
};
export const FOLLOW_ME_MAX_NUMBERS = 6;
export const FOLLOW_ME_RING_MIN = 5;
export const FOLLOW_ME_RING_MAX = 120;
export type FollowMeInfo = { extension_id: string; number: string; follow_me: FollowMe; updated_at: string };
/** PUT — to'liq obyekt; `updated_at` — optimistik qulf. */
export type UpdateFollowMePayload = FollowMe & { updated_at?: string };
/** Bir martalik Linphone havolasi (TTL 15 daq; telefon olgach 60 s). Parol QR ichida emas. */
export type QrProvisioning = { url: string; expires_at: string; transport: SipTransport };
/** Follow Me / QR egasi: ichki raqam `id`si (admin) yoki `null` — operatorning o'z raqami (`/me/...`). */
export type FollowMeTarget = string | null;

// ─────────────────────── M6 — qarang ../../replica/m6-contract.md (S18 «Kampaniyalar») ───────────────────────

/** `message` — audio (ixtiyoriy «1» ulash / «9» rad etish); `connect` — javob bergan mijozni darhol ulash. */
export type CampaignMode = 'message' | 'connect';
export type CampaignStatus = 'draft' | 'running' | 'paused' | 'completed' | 'stopped';
export type CampaignAction = 'start' | 'pause' | 'stop';
export type CampaignContactStatus = 'pending' | 'dialing' | 'retry' | 'done' | 'failed' | 'skipped';
export const CAMPAIGN_CONTACT_STATUSES: CampaignContactStatus[] = ['pending', 'dialing', 'retry', 'done', 'failed', 'skipped'];

export type CampaignFields = {
  name: string;
  mode: CampaignMode;
  audio_id: string | null;
  /** Ichki raqam / navbat / guruh raqami (2–15 raqam). */
  target_number: string | null;
  dtmf_connect: boolean;
  dtmf_optout: boolean;
  /** Mijozga ko'rinadigan raqam; bo'sh — trunk sukuti. */
  callerid: string | null;
  max_concurrent: number;
  max_attempts: number;
  retry_delay_s: number;
  ring_seconds: number;
  /** `HH:MM` yoki `HH:MM:SS` (tenant mahalliy vaqti); `start > end` — tun oshadi. */
  window_start: string;
  window_end: string;
  /** ISO hafta kuni: 1 — dushanba … 7 — yakshanba. */
  days: number[];
};

export type CampaignStats = {
  total: number; pending: number; dialing: number; retry: number; done: number; failed: number; skipped: number;
  /** «1» bosib ulanganlar. */
  connected: number;
  /** «9» bosib rad etganlar. */
  optout: number;
};

export type Campaign = CampaignFields & {
  id: string;
  status: CampaignStatus;
  audio_name: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  stats: CampaignStats;
};

export type CreateCampaignPayload = CampaignFields;
export type UpdateCampaignPayload = Partial<CampaignFields> & { updated_at: string };

export type CampaignContact = {
  id: number;
  number: string;
  name: string | null;
  status: CampaignContactStatus;
  /** ANSWER | BUSY | NOANSWER | CHANUNAVAIL | CONGESTION | NOROUTE | BLACKLIST | OPTOUT | LOST | STOPPED */
  result: string | null;
  attempts: number;
  billsec: number | null;
  key: string | null;
  next_attempt_at: string | null;
  last_attempt_at: string | null;
};

export type ListCampaignContactsParams = { status?: CampaignContactStatus; q?: string; page?: number; page_size?: number };

/** CSV: 1-ustun raqam, 2-ustun ism (`,` yoki `;`); `replace` — eski kontaktlar o'chadi. */
export type ImportCampaignContactsPayload = { csv: string; replace: boolean };
export type ImportCampaignContactsResult = {
  added: number;
  duplicates: number;
  /** Qora ro'yxat / rad etganlar — `skipped` bo'lib qo'shiladi. */
  skipped: number;
  invalid_count: number;
  invalid: { line: number; value: string }[];
  item: Campaign;
};

// ─────────────────────────── M9 A1 — E'lon (Announcements) ───────────────────────────

export type RepeatKey = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | '*' | '#';
export type Announcement = {
  id: string;
  name: string;
  audio_file_id: string;
  audio_name: string;
  next_target: Target;
  allow_skip: boolean;
  repeat_key: RepeatKey | null;
  answer: boolean;
  /** `call_targets`dagi o'z yozuvi — boshqa manzillardan shu e'longa ishora qilish uchun. */
  target_id: string;
  updated_at: string;
};
export type CreateAnnouncementPayload = {
  name: string;
  audio_file_id: string;
  next_target_id: string;
  allow_skip?: boolean;
  repeat_key?: RepeatKey | null;
  answer?: boolean;
};
export type UpdateAnnouncementPayload = Partial<CreateAnnouncementPayload> & { updated_at: string };

// ─────────────────────────── M9 A2 — Boshqa manzillar / Maxsus kodlar ───────────────────────────

export type MiscDestination = { id: string; name: string; dial: string; target_id: string; updated_at: string };
export type CreateMiscDestinationPayload = { name: string; dial: string };
export type UpdateMiscDestinationPayload = Partial<CreateMiscDestinationPayload> & { updated_at: string };

export type MiscApplication = { id: string; name: string; code: string; target: Target; enabled: boolean; updated_at: string };
export type CreateMiscApplicationPayload = { name: string; code: string; target_id: string; enabled?: boolean };
export type UpdateMiscApplicationPayload = Partial<CreateMiscApplicationPayload> & { updated_at: string };

// ─────────────────────────── M9 A3 — Parkovka sozlamalari ───────────────────────────

export type ParkingOnTimeout = 'origin' | 'target';
export type ParkingSettings = {
  lot_number: string;
  first_slot: number;
  slot_count: number;
  timeout_s: number;
  on_timeout: ParkingOnTimeout;
  timeout_target: Target | null;
  moh_class_id: string | null;
  updated_at: string;
};
export type UpdateParkingSettingsPayload = {
  lot_number: string;
  first_slot: number;
  slot_count: number;
  timeout_s: number;
  on_timeout: ParkingOnTimeout;
  timeout_target_id: string | null;
  moh_class_id: string | null;
  updated_at: string;
};
/** @note Mavjud `ParkedCall`/`Parking` (dashboard vidjeti) dan ataylab farqlanadi — M9 A3 shartnomasi aniq shakl beradi. */
export type ParkingCall = { slot: number; caller_num: string; caller_name: string | null; parked_by: string; parked_seconds: number; timeout_s: number };

// ─────────────────────────── M9 A4 — Paging / Intercom ───────────────────────────

export type PageGroupMember = { id: string; number: string; name: string };
export type PageGroup = {
  id: string;
  name: string;
  number: string;
  duplex: boolean;
  skip_busy: boolean;
  beep: boolean;
  members: PageGroupMember[];
  updated_at: string;
};
export type CreatePageGroupPayload = {
  name: string; number: string; duplex: boolean; skip_busy: boolean; beep: boolean; member_ids: string[];
};
export type UpdatePageGroupPayload = Partial<CreatePageGroupPayload> & { updated_at: string };

// ─────────────────────────── M9 B1 — PIN to'plamlari ───────────────────────────

export type PinSet = {
  id: string;
  name: string;
  record_in_cdr: boolean;
  pin_count: number;
  used_by: { id: string; name: string }[];
  updated_at: string;
};
export type CreatePinSetPayload = { name: string; record_in_cdr?: boolean };
export type UpdatePinSetPayload = Partial<CreatePinSetPayload> & { updated_at: string };
export type PinSetPin = { id: string; label: string };
/** PIN — 4–12 raqam; takror → 409 `pin_taken`. Ochiq PIN hech qachon serverdan qaytmaydi. */
export type AddPinsPayload = { pins: { pin: string; label: string }[] };

// ─────────────────────────── M9 B2 — Telefon kitobi + CID Lookup ───────────────────────────

export type PhonebookNumber = { number: string; label: string };
export type Contact = { id: string; name: string; company: string | null; note: string | null; numbers: PhonebookNumber[]; updated_at: string };
export type CreateContactPayload = { name: string; company?: string | null; note?: string | null; numbers: PhonebookNumber[] };
export type UpdateContactPayload = Partial<CreateContactPayload> & { updated_at: string };
export type ListPhonebookParams = { q?: string; page?: number; page_size?: number };
export type ImportPhonebookResult = { created: number; updated: number; skipped: number; errors: { row: number; message: string }[] };
export type ImportPhonebookParams = { file: File; dry_run: boolean };

export type CidSourceKind = 'phonebook' | 'crm' | 'http';
export type CidSource = {
  id: string;
  name: string;
  kind: CidSourceKind;
  http_url: string | null;
  http_json_path: string | null;
  timeout_ms: number;
  cache_ttl_s: number;
  enabled: boolean;
  used_by: { id: string; name: string }[];
  updated_at: string;
};
export type CreateCidSourcePayload = {
  name: string; kind: CidSourceKind; http_url?: string | null; http_json_path?: string | null;
  timeout_ms?: number; cache_ttl_s?: number; enabled?: boolean;
};
export type UpdateCidSourcePayload = Partial<CreateCidSourcePayload> & { updated_at: string };
export type CidSourceTestResult = { name: string | null; ms: number; error: string | null };

// ─────────────────────────── M10 C — Callback vidjet (A1) ───────────────────────────

export type CallbackOffhoursMode = 'reject' | 'schedule';
export type WidgetAppearanceText = { uz: string; ru: string; en: string };
export type WidgetAppearance = {
  color: string;
  position: 'right' | 'left';
  title: WidgetAppearanceText;
  button: WidgetAppearanceText;
  success: WidgetAppearanceText;
};
export type CallbackWidget = {
  id: string;
  name: string;
  public_key: string;
  target: Target;
  allowed_origins: string[];
  time_group_id: string | null;
  time_group_name: string | null;
  offhours_mode: CallbackOffhoursMode;
  max_attempts: number;
  retry_interval_s: number;
  callerid_prefix: string | null;
  allow_international: boolean;
  appearance: WidgetAppearance;
  enabled: boolean;
  /** `public_base_url` sozlanmagan bo'lsa — null (409 EMAS, UI ogohlantiradi). */
  embed_snippet: string | null;
  updated_at: string;
};
export type CreateCallbackWidgetPayload = {
  name: string;
  // Backend `resolve_target()` — yagona `call_targets` jadvali, kind kerak emas (qarang `api/callback_widgets.py`).
  target_id: string;
  allowed_origins?: string[];
  time_group_id?: string | null;
  offhours_mode?: CallbackOffhoursMode;
  max_attempts?: number;
  retry_interval_s?: number;
  callerid_prefix?: string | null;
  allow_international?: boolean;
  appearance?: Partial<WidgetAppearance>;
  enabled?: boolean;
};
export type UpdateCallbackWidgetPayload = Partial<CreateCallbackWidgetPayload> & { updated_at: string };
export type CallbackRequestStatus = 'pending' | 'dialing' | 'connected' | 'failed' | 'rejected' | 'cancelled';
export type CallbackRequest = {
  id: string;
  widget_id: string;
  widget_name: string;
  phone: string;
  name: string | null;
  page_url: string | null;
  status: CallbackRequestStatus;
  attempts: number;
  next_attempt_at: string | null;
  linkedid: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};
// Backend `list_callback_requests` — `widget_id`/`status`/`page`/`page_size` qabul qiladi (sana oralig'i YO'Q).
export type ListCallbackRequestsParams = {
  widget_id?: string; status?: CallbackRequestStatus; page?: number; page_size?: number;
};

// ─────────────────────────── M10 C — Javobsiz qoʻngʻiroq xabari (A2) ───────────────────────────

export type MissedCallScopeKind = 'any' | 'did' | 'queue' | 'ring_group' | 'extension';
export type MissedCallRule = {
  id: string;
  name: string;
  scope_kind: MissedCallScopeKind;
  scope_value: string | null;
  telegram_chat_ids: string[];
  emails: string[];
  include_internal: boolean;
  enabled: boolean;
  updated_at: string;
};
export type CreateMissedCallRulePayload = {
  name: string;
  scope_kind: MissedCallScopeKind;
  scope_value?: string | null;
  telegram_chat_ids?: string[];
  emails?: string[];
  include_internal?: boolean;
  enabled?: boolean;
};
export type UpdateMissedCallRulePayload = Partial<CreateMissedCallRulePayload> & { updated_at: string };
// Backend `MissedCallRuleMutated = {item}` (apply YO'Q — bu qoida dialplanga ta'sir qilmaydi, `apply_config` chaqirilmaydi).
export type MissedCallRuleMutated = { item: MissedCallRule };
// Backend `MissedCallRuleTestResult = {ok, message}` (error EMAS; muvaffaqiyatsiz bo'lsa ham xabar `message`da).
export type TestMissedCallRuleResult = { ok: boolean; message: string };
export type MissedCallNoticeStatus = 'pending' | 'sent' | 'failed';
export type MissedCallNotice = {
  id: string;
  rule_id: string;
  rule_name: string;
  call_id: string;
  status: MissedCallNoticeStatus;
  attempts: number;
  last_error: string | null;
  created_at: string;
  sent_at: string | null;
};
// Backend `list_missed_call_notices` — `rule_id`/`page`/`page_size` qabul qiladi (`status` filtri YO'Q).
export type ListMissedCallNoticesParams = { rule_id?: string; page?: number; page_size?: number };

// ─────────────────────────── M10 C — TTS (A3) ───────────────────────────

export type TtsProvider = 'none' | 'yandex';
export type TtsVoices = { uz: string; ru: string; en: string };
// Backend `TtsSettingsOut.has_api_key` (has_key EMAS); `PATCH` javobi `{item}` (Mutated/apply YO'Q — dialplanga ta'sir qilmaydi).
export type TtsSettings = { provider: TtsProvider; has_api_key: boolean; folder_id: string | null; voices: TtsVoices; updated_at: string | null };
export type TtsSettingsMutated = { item: TtsSettings };
export type UpdateTtsSettingsPayload = {
  provider?: TtsProvider;
  /** '' yuborilsa — mavjud kalit o'chiriladi. */
  api_key?: string;
  folder_id?: string | null;
  voices?: Partial<TtsVoices>;
  /** Yangi o'rnatishda (sozlama hali saqlanmagan) — `null`. */
  updated_at: string | null;
};
// Backend `TtsTestResult = {ok, message}` (error EMAS).
export type TtsTestResult = { ok: boolean; message: string };
// Backend `TtsSynthesizePayload = {text, name}` — til/ovoz/tezlik YO'Q (tenant tili va
// `TtsSettings.voices`dan avtomatik olinadi, so'rov darajasida tanlanmaydi).
export type CreateTtsAudioPayload = { name: string; text: string };
export type TtsPreviewPayload = { text: string };

// ─────────────────────────── M10 C — Sifat baholash (B1) ───────────────────────────
// Qattiq backend qolipi (`api/app/schemas_qa.py` + `api/app/api/v1/qa.py`): varaqa
// (checklist) CRUD flat qaytaradi (Mutated/apply YO'Q — dialplanga ta'sir qilmaydi),
// ro'yxat `{items}` (pagination/filtr YO'Q), baholash (evaluation) CRUD HAM flat,
// `answers` — object-map (`criterion_id -> qiymat`), massiv EMAS.

export type QaCriterionKind = 'yesno' | 'scale5';
export type QaCriterion = {
  id: string;
  label: string;
  kind: QaCriterionKind;
  weight: number;
  critical: boolean;
  position: number;
};
export type QaCriterionInput = { label: string; kind: QaCriterionKind; weight?: number; critical?: boolean };
export type QaChecklist = {
  id: string;
  name: string;
  is_active: boolean;
  criteria: QaCriterion[];
  updated_at: string;
};
export type CreateQaChecklistPayload = { name: string; criteria: QaCriterionInput[] };
export type UpdateQaChecklistPayload = { name?: string; is_active?: boolean; criteria?: QaCriterionInput[]; updated_at: string };
// Backend `answers: dict[str, bool | int]` — criterion_id -> ha/yo'q YOKI 1..5.
export type QaAnswers = Record<string, boolean | number>;
export type QaEvaluation = {
  id: string;
  checklist_id: string;
  checklist_name: string;
  call_id: string;
  extension_id: string | null;
  evaluator_id: string | null;
  // Backend operator o'zi ko'radigan ro'yxatlarda (`/me/evaluations`, `/calls/{id}/evaluations`)
  // ataylab `null` qaytaradi — kim baholaganini ko'rsatmaydi.
  evaluator_name: string | null;
  answers: QaAnswers;
  comment: string | null;
  score_pct: number;
  created_at: string;
  updated_at: string;
};
export type CreateQaEvaluationPayload = { checklist_id: string; call_id: string; extension_id?: string | null; answers: QaAnswers; comment?: string | null };
export type UpdateQaEvaluationPayload = { answers?: QaAnswers; comment?: string | null; updated_at: string };
// Backend `list_evaluations` — faqat `call_id` bo'yicha filtr, ko'proq yo'q.
export type ListQaEvaluationsParams = { call_id?: string; page?: number; size?: number };
export type QaSummaryByExtension = { extension_id: string | null; extension_number: string | null; count: number; avg_score_pct: number };
// Backend `/qa/summary` parametrsiz, tenant-keng bir martalik xulosa (sana oynasi/guruhlash YO'Q).
export type QaSummary = { count: number; avg_score_pct: number; by_extension: QaSummaryByExtension[] };

// ─────────────────────────── M10 C — 2FA (TOTP, B2) ───────────────────────────

export type TotpSetup = { secret: string; otpauth_uri: string };
export type TotpEnablePayload = { code: string };
export type TotpEnableResult = { recovery_codes: string[] };
// Backend `TotpDisablePayload` — faqat `code` (parol SO'RALMAYDI, qarang schemas_2fa.py).
export type TotpDisablePayload = { code: string };
export type TotpRecoveryCodesPayload = { code: string };
export type TotpRecoveryCodesResult = { recovery_codes: string[] };
export type LoginTotpPayload = { challenge: string; code: string };
