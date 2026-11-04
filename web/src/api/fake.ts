// Fake klient: xotirada ishlaydi, kechikishni simulyatsiya qiladi, shartnomadagi 409/423/403/422 holatlarini chiqaradi.
// `createFakeClient()` — har chaqiriqda yangi, mustaqil holat (testlar uchun); `fakeClient` — ilova bo'ylab yagona nusxa.
import type { ApiClient, Created, Mutated } from './client';
import type { FollowMe, FollowMeInfo, FollowMeTarget, QrProvisioning, UpdateFollowMePayload } from './types';
import type {
  CreateDayNightPayload, CreateDisaPayload, DayNight, Disa, UpdateDayNightPayload, UpdateDisaPayload,
} from './types';
import { defaultFollowMe, sameFollowMe } from '@/domain/followMe';
import { generateSipPassword, validateSipPassword, type SipPasswordIssue } from '@/domain/sipPassword';
import { normalizeFollowMe } from './fakeFollowMe';
import { createCampaignStore, csvCell } from './fakeCampaigns';
import { callsToCsv, matchesCallFilters } from './fakeCalls';
import { splitCsvRow } from '../domain/campaigns';
import { seedCampaigns } from './fakeCampaignSeed';
import { ApiError } from './errors';
import { toneWav } from '../lib/wav';
import { HUDUD_LIST } from '@/shell/screens';
import {
  SEED_ADMIN, SEED_ADMIN_PASSWORD, SEED_CONFERENCE_ADMIN_PIN, SEED_CONFERENCE_PIN,
  SEED_CUSTOM_USER, SEED_CUSTOM_USER_PASSWORD, SEED_OPERATOR,
  SEED_OPERATOR_PASSWORD, SEED_VOICEMAIL_PIN, SIM_ROLLBACK_MARK,
  type FakeRoleSeed, seedRoles,
  SYS_BUSY_TARGET, SYS_HANGUP_TARGET, seedAlertLog, seedAlertSettings, seedAudio, seedAuditLog, seedBlacklist,
  seedCalls, seedConferences,
  seedExtensions, seedFeatureCodes, seedHolidays,
  seedInboundRoutes, seedIpBans, seedIvrs, seedMohClasses, seedNotifySettings, seedOutboundRoutes, seedParking,
  seedQueues, seedRevisions,
  seedRingGroups, seedSecurityEvents, seedSecuritySettings, seedSecurityStatsHours, seedSecurityTopIps,
  seedSipSettings, seedSipTls, seedTimeConditions, seedTimeGroups, seedTrunks, seedUsers,
  seedVoicemailBoxes, seedVoicemailMessages,
  // M3b — qarang ../../replica/m3b-contract.md
  seedAmoConfig, seedApiKeys, seedBitrixConfig, seedIntegrationsSettings, seedOneCSamples, seedRecordingSettings,
  seedWebhookDeliveries, seedWebhooks,
  // M4a — qarang ../../replica/m4a-contract.md
  seedDeviceKeys, seedDeviceModels, seedDevices, seedDiscoveredDevices, seedProvisionRequests,
  seedProvisioningSettings,
  // M4b — qarang ../../replica/m4b-contract.md
  seedBackups, seedBackupSettings, seedRestoreJobs,
  // M5a — qarang ../../replica/m5a-contract.md
  seedMigrationJobs,
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  seedAnnouncements, seedCidSources, seedContacts, seedMiscApplications, seedMiscDestinations,
  seedPageGroups, seedParkingSettings, seedPinSets,
  // M12 A1/A2 — qarang ../../replica/m12-contract.md §A1/§A2
  seedDayNight, seedDisa, SEED_DISA_PIN,
} from './fakeSeed';
import { findDuplicateDigit, findIvrLoop, type IvrEdgeLookup, type IvrEdges } from '../domain/ivr';
import { buildFlowGraph, type FlowGraphNode, type FlowLookup, type FlowLookupResult, type FlowRef } from '../domain/flow';
import { isValidCidr, isValidHost, isValidIPv4 } from '../lib/validators';
import { isTrustedIp } from '../domain/security';
import { parsePattern } from '../domain/pattern';
import { simulateOutbound, type SimRoute } from '../domain/outbound';
import { unifiedDiff } from '../domain/diff';
import { buildNetworkDiff, buildNetworkWarnings, validateNetworkConfig } from '../domain/network';
import { defaultNtpServers, validateTimeConfig } from '../domain/systemTime';
import { buildFirewallDiff, checkFirewallSelfLockout, validateFirewallConfig } from '../domain/firewall';
import { computeScorePct, type QaCriterionLike } from '../domain/qaScore';
import { generateRecoveryCodes, generateTotpSecret, otpauthUri, verifyTotp } from '../domain/totp';
import { jobStep, validatedLocalTarget, validatedS3Target, validatedSftpTarget } from './fakeBackup';
import {
  FREEPBX_FIXTURE_IGNORED, FREEPBX_FIXTURE_WARNINGS, SSH_HOST_KEY_FINGERPRINT, cloneFixturePlan,
  jobStep as migrationJobStep, migrationPatchAllowed, summarizePlan,
} from './fakeMigration';
import type {
  AlertLogEntry, AlertSettings, ApplyResult, AuditEntry, Audio, AuthResult, BlacklistEntry, Call,
  ChangePasswordPayload, Conference,
  ConfigRevision,
  CreateBanPayload, CreateBlacklistPayload, CreateConferencePayload, CreateExtensionPayload, CreateHolidayPayload,
  CreateInboundRoutePayload, CreateIvrPayload, CreateMohClassPayload, CreateOutboundRoutePayload, CreateQueuePayload,
  CreateRingGroupPayload, CreateTimeConditionPayload, CreateTimeGroupPayload, CreateTrunkPayload,
  CreateUserPayload,
  CreateVoicemailBoxPayload, DashboardResult, FeatureCode,
  Extension, FlowNodeApi, FlowResult, Holiday, ImportUzHolidaysPayload, ImportUzHolidaysResult, InboundRoute,
  IpBan, Ivr,
  ListAlertLogParams, ListAuditParams, ListBlacklistParams, ListCallsParams, ListExtensionsParams,
  ListSecurityEventsParams, ListTargetsParams,
  ListVoicemailBoxesParams, LiveAgentState, LiveCall, LiveExtensionState, LiveSnapshot, LiveSpyPayload,
  LiveSpyResult, ManagedUser, MeOverview, MohClass,
  NotifySettings, NotifyTestPayload, NotifyTestResult, NumbersFreeParams,
  OutboundExtensionRef, OutboundOrderPayload, OutboundPattern, OutboundRoute, OutboundSimulateParams,
  OutboundSimulateResult, OutboundTrunkRef, OverrideTimeConditionPayload,
  Paged, Parking, PatchMeExtensionPayload, Queue, QueueMember, QueueMemberAction, QueueMemberActionPayload,
  RecordingPolicy,
  ReportRangeParams, ReportsAgentRow, ReportsDailyRow, ReportsHourlyRow, ReportsQueueRow, ReportsSummary,
  RestartAsteriskResult, RestoreRevisionResult, RevisionDetail, RevisionDiff,
  RevisionDiffAgainst, Role, RoleOut, CreateRolePayload, UpdateRolePayload,
  RingGroup, SecurityEvent, SecuritySettings, SecurityStats, SecurityStatsParams, SecurityStatsTopIp,
  SelfSignedTlsPayload, SetupPayload,
  SipCredentials, SipSettings, SipTls, SoftphoneInfo, SystemHealth, Target,
  TargetKind, TestAlertResult, TimeCondition, TimeGroup,
  TimeRange, TollBlock, Trunk, TrunkTestResult, UpdateAlertSettingsPayload, UpdateConferencePayload,
  UpdateExtensionPayload, UpdateFeatureCodePayload,
  UpdateHolidayPayload, UpdateInboundRoutePayload,
  UpdateIvrPayload, UpdateMePayload, UpdateMohClassPayload, UpdateNotifySettingsPayload,
  UpdateOutboundRoutePayload, UpdateQueueMemberPayload, UpdateQueuePayload, UpdateRingGroupPayload,
  UpdateSecuritySettingsPayload, UpdateSipSettingsPayload, UpdateTimeConditionPayload, UpdateTimeGroupPayload,
  UpdateTrunkPayload,
  UpdateUserPayload,
  UpdateVoicemailBoxPayload, Usage, User, VoicemailBox, VoicemailMessage,
  WebrtcCodec, Weekday,
  // M3b — qarang ../../replica/m3b-contract.md
  AmoConfigResult, ApiKey, BitrixConfigResult, CreateApiKeyPayload, CreateWebhookPayload, CreatedApiKey,
  CreatedWebhook, CrmProvider, CrmTestResult, CrmUserMapEntry, IntegrationsSettings, ListDeliveriesParams,
  OneCSample, RecordingSettings, RotatedWebhookSecret, TestWebhookResult, UpdateAmoPayload, UpdateBitrixPayload,
  UpdateCrmUserMapPayload, UpdateIntegrationsSettingsPayload, UpdateRecordingSettingsPayload, UpdateWebhookPayload,
  Webhook, WebhookDelivery,
  // M4a — qarang ../../replica/m4a-contract.md
  AssignDiscoveredDevicePayload, CreateDevicePayload, Device, DeviceConfigResult, DeviceKey, DeviceModel,
  DiscoveredDevice, ListDevicesParams, ListProvisionRequestsParams, ProvisionRequest, ProvisioningSettings,
  ResyncDeviceResult, RotateProvisioningTokenResult, UpdateDeviceKeysPayload, UpdateDevicePayload,
  UpdateProvisioningSettingsPayload,
  // M4b — qarang ../../replica/m4b-contract.md
  Backup, BackupCopy, BackupJob, BackupJobKind, BackupJobState, BackupManifest,
  BackupSettings, CreateBackupPayload, InspectBackupPayload, InspectBackupResult,
  RestoreBackupPayload, RestoreJob, TestBackupTargetPayload, TestBackupTargetResult, TrustSftpHostKeyPayload,
  UpdateBackupPassphrasePayload, UpdateBackupSettingsPayload,
  // M5a — qarang ../../replica/m5a-contract.md
  ApplyMigrationPayload, ListMigrationPlanParams, MigrationAction, MigrationIgnoredItem, MigrationJob,
  MigrationPlanItem, MigrationWarning, PatchMigrationPlanPayload, SshFetchPayload, SshTestPayload, SshTestResult,
  // Tizim holati (status) — pbx-klon vazifa (2026-11-02)
  CleanupIn, CleanupResult, DiskCategory, SystemDisk, SystemStatus,
  // M8 — qarang ../../replica/m8-network-contract.md
  NetworkConfigIn, NetworkInterface, NetworkLastResult, NetworkPending, NetworkStateOut, NetworkStaticRoute,
  NetworkValidateResult,
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  AddPinsPayload, Announcement, CidSource, CidSourceTestResult, Contact, CreateAnnouncementPayload,
  CreateCidSourcePayload, CreateContactPayload, CreateMiscApplicationPayload, CreateMiscDestinationPayload,
  CreatePageGroupPayload, CreatePinSetPayload, ExtensionImportRowAction, ImportExtensionsParams, ImportExtensionsResult,
  ImportPhonebookParams, ImportPhonebookResult, ListPhonebookParams,
  MiscApplication, MiscDestination, PageGroup, ParkingCall, ParkingSettings, PhonebookNumber, PinSet, PinSetPin,
  UpdateAnnouncementPayload, UpdateCidSourcePayload, UpdateContactPayload, UpdateMiscApplicationPayload,
  UpdateMiscDestinationPayload, UpdatePageGroupPayload, UpdateParkingSettingsPayload, UpdatePinSetPayload,
  // M10 C — qarang ../../replica/m10-onlinepbx-contract.md (Bo'lak C)
  CallbackWidget, CreateCallbackWidgetPayload, UpdateCallbackWidgetPayload, WidgetAppearance,
  CallbackRequest, ListCallbackRequestsParams,
  MissedCallRule, CreateMissedCallRulePayload, UpdateMissedCallRulePayload, TestMissedCallRuleResult, MissedCallRuleMutated,
  MissedCallNotice, ListMissedCallNoticesParams,
  TtsSettings, UpdateTtsSettingsPayload, TtsTestResult, CreateTtsAudioPayload, TtsPreviewPayload, TtsSettingsMutated,
  QaChecklist, QaCriterion, CreateQaChecklistPayload, UpdateQaChecklistPayload,
  QaEvaluation, CreateQaEvaluationPayload, UpdateQaEvaluationPayload, ListQaEvaluationsParams,
  QaSummary,
  TotpSetup, TotpEnablePayload, TotpEnableResult, TotpDisablePayload, TotpRecoveryCodesPayload,
  TotpRecoveryCodesResult, LoginTotpPayload,
  // M11 — qarang ../../replica/m11-update-contract.md
  StartSystemUpdatePayload, SystemUpdateLog, SystemUpdateOut, UpdateChangelogEntry, UpdateErrorCode, UpdatePendingAction,
  UpdatePhase, UpdateState,
  // M12 B1/B2/B3 — qarang ../../replica/m12-contract.md
  TimeConfigIn, TimeStateOut, PowerActionIn, PowerActionOut, PowerStatusOut,
  FirewallConfigIn, FirewallLastResult, FirewallPending, FirewallServiceOut, FirewallStateOut, FirewallValidateOut,
} from './types';
import { API_KEY_SCOPES, DEVICE_VENDORS, EXTENSIONS_CSV_COLUMNS, WEBHOOK_EVENTS, WEBRTC_CODECS } from './types';

const LOCK_MS = 15 * 60 * 1000;
const LOCK_AFTER = 5;
const TZ = 'Asia/Tashkent';

function err(status: number, code: string, message: string, extra?: { field?: string; details?: Record<string, unknown> }): never {
  throw new ApiError(status, { code, message, ...extra });
}

/** Ombor metodlariga tarmoq kechikishini qo'shadi (M6 — alohida modul omborlari uchun). */
function delayed<T extends object>(api: T): T {
  return Object.fromEntries(Object.entries(api).map(([name, fn]) => [
    name, async (...args: unknown[]) => { await delay(); return (fn as (...a: unknown[]) => unknown)(...args); },
  ])) as T;
}

function randomId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function randomSecret() {
  return Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 6).toUpperCase();
}

/** M10 C — `fakeSeed.ts`dagi xususiy `callAt`ning nusxasi (demo vaqt belgilari uchun, shu fayl ichida qoʻshilgan seedlarga). */
function callAt(hoursAgo: number): string {
  const d = new Date('2026-10-27T09:00:00Z');
  d.setHours(d.getHours() - hoursAgo);
  return d.toISOString();
}

/**
 * M3b §3 — vebhuk manzili tekshiruvi (422 `url_forbidden`): faqat http/https, loopback/link-local/0.0.0.0/
 * metadata va PBX konteynerlarining o'ziga yuborish taqiqlanadi. LAN (10/8, 172.16/12, 192.168/16) RUXSAT etilgan
 * (on-prem CRM/1C serverlari).
 */
function isForbiddenWebhookUrl(raw: string): boolean {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return true;
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return true;
  const host = url.hostname.toLowerCase();
  const FORBIDDEN_HOSTS = ['localhost', 'api', 'postgres', 'asterisk', 'web', 'metadata.google.internal'];
  if (FORBIDDEN_HOSTS.includes(host)) return true;
  if (host === '0.0.0.0' || host === '169.254.169.254' || host === '::1' || host === '127.0.0.1') return true;
  if (/^127\./.test(host)) return true;
  if (/^169\.254\./.test(host)) return true;
  if (host.startsWith('fe80:')) return true;
  return false;
}

/** Delay — testlarda VITE_FAKE_DELAY=0 bilan o'chiriladi (vitest.setup / vite.config env orqali). */
const DELAY_MS = import.meta.env.VITE_FAKE_DELAY === '0' ? 0 : 260;
const delay = (ms = DELAY_MS) => (ms > 0 ? new Promise((r) => setTimeout(r, ms)) : Promise.resolve());

const UZ_FIXED_HOLIDAYS = [
  { month: 1, day: 1, name: 'Yangi yil' },
  { month: 3, day: 8, name: 'Xalqaro xotin-qizlar kuni' },
  { month: 3, day: 21, name: 'Navruz bayrami' },
  { month: 5, day: 9, name: 'Xotira va qadrlash kuni' },
  { month: 9, day: 1, name: 'Mustaqillik kuni' },
  { month: 10, day: 1, name: "Oʻqituvchi va murabbiylar kuni" },
  { month: 12, day: 8, name: 'Konstitutsiya kuni' },
  { month: 12, day: 31, name: 'Yangi yil arafasi' },
] as const;
const pad2 = (n: number) => String(n).padStart(2, '0');

/** Jonli qoʻnqiroqlar demo holati (M2b §2) — qarang ../../replica/m2b-contract.md */
function seedLiveCalls(): LiveCall[] {
  const now = Date.now();
  return [
    {
      id: 'lc-1', direction: 'inbound', from: '998901112233', to: '101', state: 'up',
      started_at: new Date(now - 125_000).toISOString(), answered_at: new Date(now - 120_000).toISOString(),
      queue_id: null, extension: '101',
      channels: ['PJSIP/t1-101-0000002a'],
    },
    {
      id: 'lc-2', direction: 'inbound', from: '998933221199', to: '600', state: 'queued',
      started_at: new Date(now - 35_000).toISOString(), answered_at: null,
      queue_id: 'q-sotuv', extension: null, channels: [],
    },
  ];
}

/**
 * M4b zaxira/tiklash ishlarini simulyatsiya qilish — vaqtga asoslangan (poll chaqirilganda hisoblanadi, `setTimeout`
 * zanjiri yoʻq: shu bilan `VITE_FAKE_DELAY=0` testlarda ham determinstik, soat/timer mock qilish shart emas).
 */
type FakeBackupJob = {
  kind: BackupJobKind;
  startedAt: number;
  totalMs: number;
  steps: string[];
  outcome: 'ok' | 'failed';
  errorMessage?: string;
  finalized: boolean;
  finalize: () => void;
};

function jobProgress(job: FakeBackupJob): number {
  const elapsed = Date.now() - job.startedAt;
  return Math.min(100, Math.round((elapsed / job.totalMs) * 100));
}

function readBackupJobState(job: FakeBackupJob): BackupJobState {
  const progress = jobProgress(job);
  if (progress < 100) return { kind: job.kind, status: 'running', step: jobStep(job.steps, progress), progress, error: null };
  if (!job.finalized) {
    job.finalized = true;
    job.finalize();
  }
  return { kind: job.kind, status: job.outcome, step: null, progress: 100, error: job.outcome === 'failed' ? (job.errorMessage ?? 'Xatolik yuz berdi.') : null };
}

/** Demo SFTP host barmoq izi — `testBackupTarget`/`trustSftpHostKey` shu bittasini "haqiqiy" deb hisoblaydi. */
const DEMO_SFTP_FINGERPRINT = 'SHA256:9f26b9c2b3f1e4d5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9';

function backupFileName(prefix: string, iso: string, id: string): string {
  const stamp = iso.replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
  return `${prefix}-${stamp}-${id.slice(-8)}.ibk`;
}

/**
 * M5a FreePBX importi ishini simulyatsiya qilish — `FakeBackupJob` bilan bir xil vaqtga asoslangan naqsh:
 * ikki bosqich (`analyze`, `apply`) alohida progress/step bilan, poll chaqirilganda hisoblanadi.
 */
type FakeMigrationRecord = {
  job: MigrationJob;
  phase: 'analyze' | 'apply' | null;
  phaseStartedAt: number;
  phaseTotalMs: number;
  phaseSteps: string[];
  plan: MigrationPlanItem[];
  ignored: MigrationIgnoredItem[];
  warnings: MigrationWarning[];
  /** Keyingi `apply`da bir martalik 409 `plan_stale` chiqarish — qayta `analyze`da tozalanadi. */
  forceStale: boolean;
  /** `DELETE /jobs/{id}` — to'plam fayli o'chadi, lekin tarix (natija) qoladi. */
  bundleDeleted: boolean;
  /** Sinov uchun: fayl nomida `fail` bo'lsa, `apply` muvaffaqiyatsiz tugaydi (atomarlik demosi). */
  forceFail: boolean;
};

const ANALYZE_STEPS = ["To'plam ochilmoqda", "Jadvallar o'qilmoqda", 'Reja tuzilmoqda', "Bog'liqliklar tekshirilmoqda"];
const APPLY_STEPS = ['pre_import zaxira olinmoqda', "Ma'lumotlar yozilmoqda (bitta tranzaksiya)", "Audio fayllar ko'chirilmoqda", 'Dialplan qo\'llanmoqda'];

function migrationPhaseProgress(rec: FakeMigrationRecord): number {
  if (!rec.phase) return rec.job.progress;
  const elapsed = Date.now() - rec.phaseStartedAt;
  return Math.min(100, Math.round((elapsed / rec.phaseTotalMs) * 100));
}

/** Joriy bosqich (analyze/apply) tugaganini aniqlab, `rec.job`ni keyingi holatga o'tkazadi — snapshotdan oldin chaqiriladi. */
function advanceMigrationJob(
  rec: FakeMigrationRecord,
  finalizeAnalyze: (rec: FakeMigrationRecord) => void,
  finalizeApply: (rec: FakeMigrationRecord) => void,
) {
  if (!rec.phase) return;
  const progress = migrationPhaseProgress(rec);
  if (progress < 100) {
    rec.job = { ...rec.job, status: rec.phase === 'analyze' ? 'analyzing' : 'applying', progress, step: migrationJobStep(rec.phaseSteps, progress) };
    return;
  }
  if (rec.phase === 'analyze') finalizeAnalyze(rec);
  else finalizeApply(rec);
  rec.phase = null;
}

/** `listCalls`/`exportCallsCsv` ikkisi ham shu yerdan: sana/yoʻnalish/erkin qidiruv + CDR kengaytirilgan filtr. */
function filterCallsFor(calls: Call[], params: ListCallsParams): Call[] {
  const { from, to, q = '', direction } = params;
  const needle = q.trim().toLowerCase();
  const fromTs = from ? Date.parse(from) : -Infinity;
  const toTs = to ? Date.parse(to) : Infinity;
  return calls.filter((c) => {
    const ts = Date.parse(c.started_at);
    if (ts < fromTs || ts > toTs) return false;
    if (direction && c.direction !== direction) return false;
    if (needle && !`${c.src} ${c.dst} ${c.did ?? ''}`.toLowerCase().includes(needle)) return false;
    return matchesCallFilters(c, params);
  });
}

/** `restart_502` — M11 testlari uchun: yangilash jarayonida bitta so'rov 502 bilan qaytadi ("qayta ishga tushmoqda"),
 * boshqa qiymatlar — `failed` holatini shu xato kodi bilan yakunlaydi. Berilmasa — muvaffaqiyatli yakunlanadi. */
export function createFakeClient(
  opts: { updateScenario?: UpdateErrorCode | 'restart_502'; updateAgent?: boolean; updateAvailable?: boolean } = {},
): ApiClient {
  const { updateScenario } = opts;
  let needed = true;
  let extensions = seedExtensions();
  let trunks = seedTrunks();
  let routes = seedInboundRoutes();
  const calls = seedCalls();
  let revisions = seedRevisions();
  let revisionNumber = Number(revisions[0]?.id ?? 140);

  let timeGroups = seedTimeGroups();
  let holidays = seedHolidays();
  let audioList = seedAudio();
  let ivrs = seedIvrs(audioList[0]!);
  let ringGroups = seedRingGroups();
  let queues = seedQueues();
  let timeConditions = seedTimeConditions(ivrs[0]!);
  let outboundRoutes = seedOutboundRoutes(trunks);
  const outboundPins = new Map<string, string>(); // route id -> PIN (fake saqlash, hech qachon qaytarilmaydi)
  let sipSettings = seedSipSettings();
  let auditLog = seedAuditLog();
  let mohClasses = seedMohClasses(audioList);
  let voicemailBoxes = seedVoicemailBoxes(extensions);
  const voicemailPins = new Map<string, string>(voicemailBoxes.map((b) => [b.id, SEED_VOICEMAIL_PIN]));
  const voicemailMessages = new Map<string, VoicemailMessage[]>(voicemailBoxes.map((b) => [b.id, seedVoicemailMessages()]));
  let notifySettings = seedNotifySettings();
  const notifySecrets = { smtp_password: 'seed-smtp-parol', telegram_token: null as string | null };
  let sipTls = seedSipTls();

  // ─────────────────────── M2a — qarang ../../replica/m2a-contract.md ───────────────────────
  let featureCodes = seedFeatureCodes();
  let conferences = seedConferences();
  const conferencePins = new Map<string, string>([[conferences[0]!.id, SEED_CONFERENCE_PIN]]);
  const conferenceAdminPins = new Map<string, string>([[conferences[0]!.id, SEED_CONFERENCE_ADMIN_PIN]]);
  let blacklist = seedBlacklist();
  const parkingState = seedParking();

  // ─────────────────────── M2b — qarang ../../replica/m2b-contract.md ───────────────────────
  let users = seedUsers(extensions);
  const userPasswords = new Map<string, string>([
    [SEED_ADMIN.id, SEED_ADMIN_PASSWORD], [SEED_OPERATOR.id, SEED_OPERATOR_PASSWORD],
    [SEED_CUSTOM_USER.id, SEED_CUSTOM_USER_PASSWORD],
  ]);
  const liveCalls = seedLiveCalls();
  // ─────────────────────── M7 — rollar (qarang ../../replica/m7-roles-contract.md §2) ───────────────────────
  let roles: FakeRoleSeed[] = seedRoles();

  // ─────────────────────── M2c — qarang ../../replica/m2c-contract.md ───────────────────────
  let securitySettings = seedSecuritySettings();
  let ipBans = seedIpBans();
  let securityEvents = seedSecurityEvents();
  /** Joriy faol banlardan tashqari, davr ichida allaqachon muddati tugagan banlar ham bor deb hisoblanadi (demo). */
  let bansPeriodCount = ipBans.length + 3;
  let alertSettingsCore = seedAlertSettings();
  let alertLog = seedAlertLog();

  // ─────────────────────── M3b — qarang ../../replica/m3b-contract.md ───────────────────────
  let apiKeys = seedApiKeys();
  let webhooks = seedWebhooks();
  const webhookDeliveries = new Map<string, WebhookDelivery[]>(webhooks.map((w) => [w.id, seedWebhookDeliveries(w.id)]));
  let bitrixConfig = seedBitrixConfig();
  let amoConfig = seedAmoConfig();
  const oneCSamples = seedOneCSamples();
  let integrationsSettingsCore = seedIntegrationsSettings();
  /** M5b — ichki raqam id → Follow Me (yo'q bo'lsa — sukut). */
  const followMeByExt = new Map<string, FollowMe>();
  /** M6 — kampaniyalar ombori (`fakeCampaigns.ts`); dialer har o'qishda bir qadam yuradi. */
  const campaigns = createCampaignStore({
    requireManage: () => requireManage('pbx.manage'),
    audioName: (id) => audioList.find((a) => a.id === id)?.name,
    dialNumbers: () => new Set([...extensions, ...queues, ...ringGroups].map((x) => x.number).filter((n): n is string => !!n)),
    blacklist: () => new Set(blacklist.map((b) => b.number)),
    audit: (action, id, label, diff) => auditAdd(action, 'campaign', id, label,
      Object.fromEntries(Object.entries(diff).map(([k, v]) => [k, [null, v]]))),
  });
  seedCampaigns(campaigns.seed);
  let recordingSettingsCore = seedRecordingSettings();

  // ─────────────────────── M4a — qarang ../../replica/m4a-contract.md ───────────────────────
  let devices = seedDevices(extensions);
  const deviceKeysByDevice = new Map<string, DeviceKey[]>(devices.map((d) => [d.id, seedDeviceKeys(d.id)]));
  let discoveredDevices = seedDiscoveredDevices();
  let provisionRequests = seedProvisionRequests();
  let provisioningSettingsCore = seedProvisioningSettings();
  const deviceModels = seedDeviceModels();
  /** Shartnomada aniq son yoʻq — demo qiymat; backend bilan solishtirish kerak (shartnoma §5 "max_contacts"). */
  const MAX_CONTACTS_PER_EXTENSION = 2;

  // ─────────────────────── M4b — qarang ../../replica/m4b-contract.md ───────────────────────
  let backups = seedBackups();
  let backupSettingsCore = seedBackupSettings();
  let restoreJobs = seedRestoreJobs();
  /** Demo zaxira paroli — seed `has_passphrase: true` bilan mos (parolning o'zi hech qachon javobda ko'rinmaydi). */
  let backupPassphraseValue: string | null = 'DemoZaxiraParoli12345!';
  /** SFTP maqsadini oxirgi marta qaysi host uchun tasdiqlangani — host o'zgarsa qayta pin so'raladi. */
  let sftpTrustedHost: string | null = backupSettingsCore.targets.sftp.host_key_fp ? backupSettingsCore.targets.sftp.host : null;
  /** `uploadBackup`da fayl nomidan aniqlanadigan demo holat — `inspectBackup`/`restoreBackup` shu bo'yicha xato qaytaradi. */
  const uploadedFixtures = new Map<string, 'ok' | 'corrupt' | 'newer'>();

  // ─────────────────────── Tizim holati (status/cleanup) — pbx-klon vazifa (2026-11-02) ───────────────────────
  /** Qo'ng'iroq yozuvlari diskda — `zaxiralar`dan farqli, hajmi demo CDR ro'yxatiga bog'liq emas (haqiqiy yig'ilgan hajm). */
  let diskRecordings = { bytes: 51_539_607_552, files: 2140 };
  /** Yuklangan FreePBX migratsiya bog'lamalari (shartnoma: `migrations: boolean` — hammasi birdan tozalanadi). */
  let diskMigrations = { bytes: 644_245_094, files: 4 };
  /** Ovozli pochta va jurnal fayllari — cleanup shartnomasida tozalash parametri yo'q, faqat ko'rsatish uchun. */
  const diskVoicemail = { bytes: 1_288_490_189, files: 96 };
  const diskLogs = { bytes: 322_122_547, files: 140 };
  const backupJobs = new Map<string, FakeBackupJob>();

  // ─────────────────────── Tarmoq sozlamalari (network) — M8 (../../replica/m8-network-contract.md) ───────────────────────
  // Seed shartnoma §5'da berilgan: ifupdown, ens18 statik 192.168.10.20/24 (gw 192.168.10.1), ens19 dhcp,
  // 1 statik marshrut 10.20.0.0/16 192.168.10.254 orqali.
  let netHostname = 'innova-pbx1';
  let netDns: { servers: string[]; search: string[] } = { servers: ['8.8.8.8', '1.1.1.1'], search: [] };
  let netIfaces: NetworkInterface[] = [
    {
      name: 'ens18', mac: '52:54:00:11:22:33', kind: 'ethernet', oper_state: 'up', carrier: true, speed_mbps: 1000,
      mtu: 1500, live_ipv4: ['192.168.10.20/24'], live_ipv6: [], editable: true,
      config: { mode: 'static', address: '192.168.10.20/24', gateway: '192.168.10.1', mtu: 1500 },
    },
    {
      name: 'ens19', mac: '52:54:00:11:22:34', kind: 'ethernet', oper_state: 'up', carrier: true, speed_mbps: 1000,
      mtu: 1500, live_ipv4: ['192.168.10.55/24'], live_ipv6: [], editable: true,
      config: { mode: 'dhcp', address: null, gateway: null, mtu: 1500 },
    },
  ];
  let netRoutesStatic: NetworkStaticRoute[] = [{ destination: '10.20.0.0/16', gateway: '192.168.10.254', interface: null, metric: null }];
  let netPending: NetworkPending | null = null;
  let netPendingSnapshot: { hostname: string; dns: typeof netDns; interfaces: NetworkInterface[]; routes: NetworkStaticRoute[] } | null = null;
  let netLastResult: NetworkLastResult | null = null;

  // ─────────────────────── Sana/vaqt (M12 B1) — ../../replica/m12-contract.md §B1 — pending/confirm yo'q, to'g'ridan-to'g'ri qo'llanadi ───────────────────────
  let timeTimezone = 'Asia/Tashkent';
  let timeNtpServers: string[] = ['0.uz.pool.ntp.org', '1.uz.pool.ntp.org'];
  let timeNtpEnabled = true;

  // ─────────────────────── Firewall GUI (M12 B3) — ../../replica/m12-contract.md §B3 ───────────────────────
  let fwServices: FirewallServiceOut[] = [
    { name: 'ssh', mode: 'all', allow: [] },
    { name: 'web', mode: 'all', allow: [] },
    { name: 'sip', mode: 'all', allow: [] },
    { name: 'rtp', mode: 'all', allow: [] },
  ];
  let fwBlockedCidrs: string[] = [];
  let fwPending: FirewallPending | null = null;
  let fwPendingSnapshot: { services: FirewallServiceOut[]; blockedCidrs: string[] } | null = null;
  let fwLastResult: FirewallLastResult | null = null;

  // ─────────────────────── Paneldan yangilash (update) — M11 (../../replica/m11-update-contract.md) ───────────────────────
  // Vaqtga asoslangan simulyatsiya — `FakeBackupJob` bilan bir xil naqsh (setTimeout zanjiri yo'q, `Date.now()` farqidan hisoblanadi).
  const UPD_CHECK_MS = 180;
  const UPD_PHASE_MS = 300; // har bosqich (zaxira/kod/o'rnatish) — jami 900ms
  const UPD_TOTAL_MS = UPD_PHASE_MS * 3;
  const UPD_LOG_LINES = [
    'Zaxira olinmoqda (ma\'lumotlar bazasi)…',
    "Zaxira tayyor: pre-update paketi yozildi",
    'Yangi kod olinmoqda (git fetch)…',
    "git merge --ff-only bajarildi",
    "Bog'liqliklar o'rnatilmoqda (pip/npm)…",
    'Migratsiyalar qo\'llanmoqda…',
    'Servislar qayta ishga tushirilmoqda…',
    'Yangilanish yakunlandi.',
  ];
  let updAgent = opts.updateAgent ?? true;
  let updCurrent = '1.0.12';
  const updAvailable0 = opts.updateAvailable ?? true;
  let updLatest = updAvailable0 ? '1.0.13' : updCurrent;
  let updAvailable = updAvailable0;
  let updState: UpdateState = 'idle';
  let updPhase: UpdatePhase | null = null;
  let updPending: UpdatePendingAction | null = null;
  let updCheckedAt: string | null = null;
  let updStartedAt: string | null = null;
  let updFinishedAt: string | null = null;
  let updError: UpdateErrorCode | null = null;
  let updBackup: string | null = null;
  let updChangelog: UpdateChangelogEntry[] = [
    { version: '1.0.13', date: '2026-11-04', body: "## 1.0.13 — 2026-11-04\n\n- Paneldan yangilash qo'shildi\n- **Tuzatish**: `status` fayli endi atomik yoziladi\n- Kichik `<xato>` matni endi to'g'ri chiqadi" },
  ];
  let updJobStartedAt = 0;
  let updCheckStartedAt = 0;
  let updRestartFired = false;

  /** `GET/POST /system/update*` chaqiruvi — poll vaqtida joriy ish (tekshirish/yangilash) elapsed vaqtiga qarab yakunlanadi. */
  function advanceUpdateJob(): void {
    if (updState === 'checking') {
      if (Date.now() - updCheckStartedAt < UPD_CHECK_MS) return;
      updState = 'idle';
      updPending = null;
      updCheckedAt = new Date().toISOString();
      return;
    }
    if (updState !== 'updating') return;
    const elapsed = Date.now() - updJobStartedAt;
    if (elapsed < UPD_TOTAL_MS) {
      updPhase = elapsed < UPD_PHASE_MS ? 'backup' : elapsed < UPD_PHASE_MS * 2 ? 'code' : 'install';
      return;
    }
    updPhase = null;
    updPending = null;
    updFinishedAt = new Date().toISOString();
    if (updateScenario && updateScenario !== 'restart_502') {
      updState = 'failed';
      updError = updateScenario;
      updBackup = updateScenario === 'backup_failed' ? null : 'pre-update-1.0.12-20261104-100000.sql.gz';
    } else {
      updState = 'done';
      updBackup = 'pre-update-1.0.12-20261104-100000.sql.gz';
      updCurrent = updLatest;
      updAvailable = false;
      updError = null;
    }
  }

  /** Jarayon logi — bosqich elapsed foiziga qarab `UPD_LOG_LINES`dan nechtasi "yozilgan" boʻlishini hisoblaydi. */
  function currentUpdateLogText(): string {
    if (updState === 'idle' && !updStartedAt) return '';
    const elapsed = updState === 'updating' ? Date.now() - updJobStartedAt : UPD_TOTAL_MS;
    const revealed = Math.min(UPD_LOG_LINES.length, Math.max(1, Math.ceil((Math.min(elapsed, UPD_TOTAL_MS) / UPD_TOTAL_MS) * UPD_LOG_LINES.length)));
    return UPD_LOG_LINES.slice(0, revealed).join('\n') + '\n';
  }

  function buildSystemUpdateOut(): SystemUpdateOut {
    if (!updAgent) {
      return {
        agent: false, current: null, latest: null, available: false, state: 'idle', phase: null, pending: null,
        checked_at: null, started_at: null, finished_at: null, error: null, backup: null, changelog: [],
      };
    }
    return {
      agent: true, current: updCurrent, latest: updLatest, available: updAvailable, state: updState, phase: updPhase,
      pending: updPending, checked_at: updCheckedAt, started_at: updStartedAt, finished_at: updFinishedAt,
      error: updError, backup: updBackup, changelog: updAvailable ? updChangelog : [],
    };
  }

  // ─────────────────────── M9 — qarang ../../replica/m9-freepbx-gaps-contract.md ───────────────────────
  let announcements = seedAnnouncements();
  let miscDestinations = seedMiscDestinations();
  let miscApplications = seedMiscApplications();
  let parkingSettingsCore = seedParkingSettings();
  /** Jonli park ro'yxati (A3 §GET /parking/calls) — mavjud dashboard `Parking`/`ParkedCall`dan ataylab mustaqil. */
  let parkingCalls: ParkingCall[] = [{ slot: 701, caller_num: '998901112233', caller_name: null, parked_by: '101', parked_seconds: 42, timeout_s: 60 }];
  let pageGroups = seedPageGroups();
  let pinSets = seedPinSets();
  /** PIN-to'plam id → PIN yozuvlari; ochiq PIN faqat shu xaritada (hech qachon javobda qaytmaydi). */
  const pinSetPins = new Map<string, { id: string; pin: string; label: string }[]>(
    pinSets.map((p) => [p.id, [{ id: randomId('pin'), pin: '2024', label: 'Buxgalteriya' }, { id: randomId('pin'), pin: '1357', label: 'Savdo' }]]),
  );
  let contacts = seedContacts();
  let cidSources = seedCidSources();

  // ─────────────────────── M10 C — qarang ../../replica/m10-onlinepbx-contract.md (Bo'lak C) ───────────────────────
  let callbackWidgets: CallbackWidget[] = [{
    id: 'cbw-1', name: 'Sayt — qayta chaqirish', public_key: 'pk-demo-24chars-url-safe01',
    target: toExtensionTarget(extensions[1] ?? extensions[0]!),
    allowed_origins: ['https://example.uz'], time_group_id: null, time_group_name: null,
    offhours_mode: 'schedule', max_attempts: 2, retry_interval_s: 120, callerid_prefix: null, allow_international: false,
    appearance: {
      color: '#2563eb', position: 'right',
      title: { uz: 'Sizga qayta qoʻngʻiroq qilaylik', ru: 'Мы вам перезвоним', en: 'We will call you back' },
      button: { uz: 'Qayta chaqirish', ru: 'Обратный звонок', en: 'Request a callback' },
      success: { uz: 'Soʻrovingiz qabul qilindi', ru: 'Заявка принята', en: 'Request received' },
    },
    enabled: true, embed_snippet: '<script async src="https://pbx.example.uz/widget/pk-demo-24chars-url-safe01.js"></script>',
    updated_at: '2026-10-27T05:00:00Z',
  }];
  let callbackRequests: CallbackRequest[] = [
    { id: 'cbr-1', widget_id: 'cbw-1', widget_name: callbackWidgets[0]!.name, phone: '998901112233', name: 'Nodira', page_url: 'https://example.uz/contacts', status: 'connected', attempts: 1, next_attempt_at: null, linkedid: null, last_error: null, created_at: callAt(3), updated_at: callAt(3) },
    { id: 'cbr-2', widget_id: 'cbw-1', widget_name: callbackWidgets[0]!.name, phone: '998909998877', name: null, page_url: 'https://example.uz/', status: 'failed', attempts: 2, next_attempt_at: null, linkedid: null, last_error: 'no_answer', created_at: callAt(10), updated_at: callAt(10) },
  ];

  let missedCallRules: MissedCallRule[] = [{
    id: 'mcr-1', name: 'Barcha javobsizlar — telegram', scope_kind: 'any', scope_value: null,
    telegram_chat_ids: ['-100123456789'], emails: [], include_internal: false, enabled: true, updated_at: '2026-10-27T05:00:00Z',
  }];
  let missedCallNotices: MissedCallNotice[] = [
    { id: 'mcn-1', rule_id: 'mcr-1', rule_name: missedCallRules[0]!.name, call_id: calls[1]?.uniqueid ?? 'x', status: 'sent', attempts: 1, last_error: null, created_at: callAt(5), sent_at: callAt(5) },
  ];

  let ttsSettingsCore: TtsSettings = { provider: 'none', has_api_key: false, folder_id: null, voices: { uz: 'nigora', ru: 'alena', en: 'john' }, updated_at: null };
  let ttsApiKey: string | null = null;

  let qaChecklists: QaChecklist[] = [{
    id: 'qac-1', name: 'Standart savdo chek-listi', is_active: true,
    criteria: [
      { id: 'qc-1', position: 0, label: 'Operator o‘zini tanishtirdi', weight: 2, kind: 'yesno', critical: true },
      { id: 'qc-2', position: 1, label: 'Mijoz muammosini to‘g‘ri tushundi', weight: 3, kind: 'scale5', critical: false },
      { id: 'qc-3', position: 2, label: 'Suhbat ohangi xushmuomalalik bilan', weight: 2, kind: 'scale5', critical: false },
    ],
    updated_at: '2026-10-27T05:00:00Z',
  }];
  let qaEvaluations: QaEvaluation[] = [];

  // Backend `CallQaBadge` — eng oxirgi (created_at bo'yicha) baholash belgisi.
  function qaOf(uniqueid: string): Call['qa'] {
    const ev = [...qaEvaluations].filter((e) => e.call_id === uniqueid).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
    return ev ? { evaluation_id: ev.id, checklist_name: ev.checklist_name, score_pct: ev.score_pct } : null;
  }

  // Backend (`api/callback_widgets.py` `_validate_target`) `resolve_target()`ni kind cheklovisiz chaqiradi —
  // real stekka moslab, kind tekshiruvini olib tashladik (frontend qolgan 4 turga sodda ixtiyoriy tavsiya beradi, majburlamaydi).
  function requireCallbackTarget(targetId: string): Target {
    return requireTarget(targetId, 'target_id');
  }

  function timeGroupNameOrNull(id: string | null | undefined): string | null {
    if (!id) return null;
    const tg = timeGroups.find((t) => t.id === id);
    if (!tg) err(404, 'not_found', 'Ish vaqti guruhi topilmadi.', { field: 'time_group_id' });
    return tg.name;
  }

  function widgetEmbedSnippet(publicKey: string): string | null {
    const base = (integrationsSettingsCore.public_base_url ?? '').replace(/\/+$/, '');
    return base ? `<script async src="${base}/widget/${publicKey}.js"></script>` : null;
  }

  const DEFAULT_WIDGET_APPEARANCE: WidgetAppearance = {
    color: '#2563eb', position: 'right',
    title: { uz: 'Sizga qayta qoʻngʻiroq qilaylik', ru: 'Мы вам перезвоним', en: 'We will call you back' },
    button: { uz: 'Qayta chaqirish', ru: 'Обратный звонок', en: 'Request a callback' },
    success: { uz: 'Soʻrovingiz qabul qilindi', ru: 'Заявка принята', en: 'Request received' },
  };

  function mergeAppearance(base: WidgetAppearance, patch?: Partial<WidgetAppearance>): WidgetAppearance {
    if (!patch) return base;
    return {
      color: patch.color ?? base.color,
      position: patch.position ?? base.position,
      title: { ...base.title, ...patch.title },
      button: { ...base.button, ...patch.button },
      success: { ...base.success, ...patch.success },
    };
  }

  function requireCallbackWidget(id: string): CallbackWidget {
    const w = callbackWidgets.find((x) => x.id === id);
    if (!w) err(404, 'not_found', 'Vidjet topilmadi.');
    return w;
  }

  function requireMissedCallRule(id: string): MissedCallRule {
    const r = missedCallRules.find((x) => x.id === id);
    if (!r) err(404, 'not_found', 'Qoida topilmadi.');
    return r;
  }

  /** `extension_id` sukut — chaqiruvning javob bergan tomoni (dst agar ichki raqam boʻlsa, aks holda src). */
  function defaultExtensionIdForCall(call: Call | undefined): string | null {
    if (!call) return null;
    return extensions.find((e) => e.number === call.dst)?.id ?? extensions.find((e) => e.number === call.src)?.id ?? null;
  }

  function requireQaChecklist(id: string): QaChecklist {
    const c = qaChecklists.find((x) => x.id === id);
    if (!c) err(404, 'not_found', 'Chek-list topilmadi.', { field: 'checklist_id' });
    return c;
  }

  // Backend `UpdateQaChecklistPayload.criteria` berilsa TO'LIQ almashtiradi — eskilari
  // o'chiriladi, YANGI id/position bilan qayta yaratiladi (qisman qo'shish/o'chirish yo'q).
  function normalizeQaCriteria(raw: CreateQaChecklistPayload['criteria']): QaCriterion[] {
    if (raw.length === 0) err(422, 'bad_criteria', 'Kamida bitta mezon kerak.', { field: 'criteria' });
    return raw.map((c, position) => ({
      id: randomId('qc'),
      position,
      label: c.label.trim(),
      weight: c.weight ?? 1,
      kind: c.kind,
      critical: c.critical ?? false,
    }));
  }

  function requireQaEvaluation(id: string): QaEvaluation {
    const e = qaEvaluations.find((x) => x.id === id);
    if (!e) err(404, 'not_found', 'Baho topilmadi.');
    return e;
  }

  // ─────────────────────── M5a — qarang ../../replica/m5a-contract.md ───────────────────────
  const migrationJobs = new Map<string, FakeMigrationRecord>();
  seedMigrationJobs().forEach((job) => migrationJobs.set(job.id, {
    job, phase: null, phaseStartedAt: 0, phaseTotalMs: 0, phaseSteps: [],
    plan: cloneFixturePlan(), ignored: [...FREEPBX_FIXTURE_IGNORED], warnings: [...FREEPBX_FIXTURE_WARNINGS],
    forceStale: false, bundleDeleted: false, forceFail: false,
  }));

  /** Fake rejimda doim shu qadar "faol qoʻngʻiroq" bor deb hisoblanadi — restart 409 yoʻlini sinash uchun. */
  const fakeActiveCallCount = 2;
  const revisionDialplans = new Map<string, string>(); // revision id -> matn (restore uchun)
  revisions.forEach((r) => revisionDialplans.set(r.id, `; Innova PBX dialplan — reviziya r${r.id}\n; ${r.message ?? ''}\n`));

  const refreshTokens = new Map<string, string>(); // refresh token -> user id
  let currentUser: User | null = null;
  const attempts = new Map<string, { count: number; until: number }>();
  /** Sehrgarda yaratilgan haqiqiy admin — `setup()`dan keyin shu login/parol bilan kirish ishlashi kerak. */
  let createdAdmin: { login: string; password: string; user: User } | null = null;

  // ─────────────────────── M10 C B2 — 2FA (TOTP) holati ───────────────────────
  type TotpState = { secret: string; enabled: boolean; recoveryHashes: string[]; lastStep: number | null };
  const totpByUser = new Map<string, TotpState>(); // faqat `enabled` bo'lgach shu yerda
  const totpPendingSecret = new Map<string, string>(); // setup() chaqirilgan, hali enable() qilinmagan
  const totpChallenges = new Map<string, { userId: string; attempts: number }>();

  function require2fa(user: { role: Role }): boolean {
    if (securitySettings.require_2fa === 'all') return true;
    if (securitySettings.require_2fa === 'admins') return user.role === 'admin';
    return false;
  }

  /** TOTP kodi yoki bir martalik tiklash kodi — muvaffaqiyatli bo'lsa `lastStep`/tiklash ro'yxatini yangilaydi. */
  async function verifyAnyTotpCode(state: { secret: string; recoveryHashes: string[]; lastStep: number | null }, code: string): Promise<boolean> {
    const step = await verifyTotp(state.secret, code, Date.now(), state.lastStep);
    if (step !== null) { state.lastStep = step; return true; }
    const idx = state.recoveryHashes.indexOf(code);
    if (idx >= 0) { state.recoveryHashes.splice(idx, 1); return true; }
    return false;
  }

  function issueTokens(user: User): { access: string; refresh: string } {
    const access = `fake-access-${user.id}-${randomSecret()}`;
    const refresh = `fake-refresh-${user.id}-${randomSecret()}`;
    refreshTokens.set(refresh, user.id);
    currentUser = user;
    return { access, refresh };
  }

  function revisionUser(): ConfigRevision['user'] {
    return currentUser ? { id: currentUser.id, login: currentUser.login } : null;
  }

  function apply(message: string | null, marker?: string): ApplyResult {
    if (marker?.includes(SIM_ROLLBACK_MARK)) {
      revisions = [{ id: String(revisionNumber), sha256: 'rolledback', status: 'rolled_back', created_at: new Date().toISOString(), message: 'Dialplan tekshiruvdan oʻtmadi', user: revisionUser(), summary: message }, ...revisions];
      return { status: 'rolled_back', revision: revisionNumber, message: 'Maʼlumot saqlandi, lekin PBXʼga qoʻllanmadi — oldingi holatga qaytarildi.' };
    }
    revisionNumber += 1;
    const id = String(revisionNumber);
    revisionDialplans.set(id, `; Innova PBX dialplan — reviziya r${id}\n; ${message ?? ''}\n`);
    revisions = [{ id, sha256: randomSecret(), status: 'applied', created_at: new Date().toISOString(), message, user: revisionUser(), summary: message }, ...revisions];
    return { status: 'applied', revision: revisionNumber, message };
  }

  /** `*` — toʻliq admin ruxsati, qolgan barcha legacy `requireManage*` tekshiruvlarini aylanib oʻtadi (M7 §1). */
  function requireManage(perm: string) {
    if (currentUser && !currentUser.permissions.includes('*') && !currentUser.permissions.includes(perm)) {
      err(403, 'forbidden', 'Bu amal uchun ruxsatingiz yoʻq.');
    }
  }

  function requireManageAny(perms: string[]) {
    if (currentUser && !currentUser.permissions.includes('*') && !perms.some((p) => currentUser!.permissions.includes(p))) {
      err(403, 'forbidden', 'Bu amal uchun ruxsatingiz yoʻq.');
    }
  }

  // ─────────────────────── M2b — qarang ../../replica/m2b-contract.md ───────────────────────

  /** Rol boʻyicha ruxsatlar — endi dinamik `roles` jadvalidan olinadi (M7 §1/§2). */
  function permissionsForRole(role: Role): string[] {
    return roles.find((r) => r.name === role)?.permissions ?? [];
  }

  // ─────────────────────── M7 — rollar (qarang ../../replica/m7-roles-contract.md §1/§2) ───────────────────────
  const RESERVED_ROLE_NAMES = ['admin', 'operator'];
  const LITERAL_PERMISSIONS = new Set(['*', 'calls:read:own', 'me:*']);

  function isValidPermissionKey(p: string): boolean {
    if (LITERAL_PERMISSIONS.has(p)) return true;
    const m = /^([a-z]+):(view|edit)$/.exec(p);
    return !!m && (HUDUD_LIST as string[]).includes(m[1]!);
  }

  /** Takrorlarni olib tashlaydi, `X:edit` bor boʻlsa `X:view`ni ham qoldirmaydi (faqat eng yuqori daraja) — §2. */
  function normalizeRolePermissions(raw: string[]): string[] {
    const set = new Set<string>();
    for (const p of raw) {
      if (!isValidPermissionKey(p)) err(422, 'validation_error', `Notoʻgʻri ruxsat: «${p}».`, { field: 'permissions' });
      set.add(p);
    }
    if (set.has('*')) return ['*'];
    for (const hudud of HUDUD_LIST) if (set.has(`${hudud}:edit`)) set.delete(`${hudud}:view`);
    return [...set];
  }

  function roleToOut(r: FakeRoleSeed): RoleOut {
    return { id: r.id, name: r.name, permissions: r.permissions, is_system: r.is_system, user_count: users.filter((u) => u.role === r.name).length, updated_at: r.updated_at };
  }

  /** Tartib: tizim rollari avval (admin, operator), keyin maxsus rollar nom boʻyicha — §2. */
  function sortedRoles(): FakeRoleSeed[] {
    const systemOrder = ['admin', 'operator'];
    const system = roles.filter((r) => r.is_system).sort((a, b) => systemOrder.indexOf(a.name) - systemOrder.indexOf(b.name));
    const custom = roles.filter((r) => !r.is_system).sort((a, b) => a.name.localeCompare(b.name, 'uz'));
    return [...system, ...custom];
  }

  function validateRoleName(name: string, excludeId?: string): string {
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 40) err(422, 'validation_error', 'Rol nomi 1–40 belgidan iborat boʻlishi kerak.', { field: 'name' });
    const taken = RESERVED_ROLE_NAMES.includes(trimmed.toLowerCase())
      || roles.some((r) => r.id !== excludeId && r.name.toLowerCase() === trimmed.toLowerCase());
    if (taken) err(409, 'role_name_taken', `«${trimmed}» nomli rol allaqachon bor.`, { field: 'name' });
    return trimmed;
  }

  function toSessionUser(mu: ManagedUser): User {
    const totp = totpByUser.get(mu.id);
    return {
      id: mu.id, login: mu.username, full_name: mu.full_name, role: mu.role,
      permissions: permissionsForRole(mu.role), language: mu.language, must_change_password: mu.must_change_password,
      extension: mu.extension,
      totp_enabled: !!totp?.enabled,
      must_enroll_2fa: require2fa(mu) && !totp?.enabled,
    };
  }

  function requireManagedUser(id: string): ManagedUser {
    const mu = users.find((u) => u.id === id);
    if (!mu) err(404, 'not_found', 'Foydalanuvchi topilmadi.');
    return mu;
  }

  /** O'zini bloklab qo'yish (S31) — faol yagona admin bo'lsa yoki o'zini deaktivlashtirsa/rolidan tushirsa. */
  function checkSelfLockout(targetId: string, nextIsActive: boolean, nextRole: Role) {
    if (currentUser?.id !== targetId) return;
    if (!nextIsActive) err(409, 'self_lockout', 'Oʻzingizni faolsizlantira olmaysiz.');
    if (nextRole !== 'admin' && currentUser.role === 'admin') err(409, 'self_lockout', 'Oʻzingizni admin rolidan pastga tushira olmaysiz.');
  }

  /** Oxirgi faol adminni yo'qotib qo'ymaslik — deaktivlash/rol pastga/o'chirishda tekshiriladi. */
  function checkLastAdmin(targetId: string, nextIsActive: boolean, nextRole: Role) {
    const mu = requireManagedUser(targetId);
    if (mu.role !== 'admin') return;
    if (nextIsActive && nextRole === 'admin') return;
    const otherActiveAdmins = users.filter((u) => u.id !== targetId && u.role === 'admin' && u.is_active);
    if (otherActiveAdmins.length === 0) err(409, 'last_admin', 'Tizimda kamida bitta faol admin qolishi kerak.');
  }

  /** Navbat a'zosiga login/logout/pauza qo'llash — admin konsoli va `/me` kabineti bir xil mantiqdan foydalanadi. */
  function applyQueueMemberAction(q: Queue, extensionId: string, action: QueueMemberAction, reason?: string | null): QueueMember[] {
    const idx = q.members.findIndex((m) => m.extension.id === extensionId);
    if (idx < 0) err(404, 'not_found', 'Bu ichki raqam navbat aʼzosi emas.');
    const m = q.members[idx]!;
    if (!m.dynamic && (action === 'login' || action === 'logout')) err(409, 'not_dynamic', 'Statik aʼzo tizimga kirish/chiqishni oʻzgartira olmaydi.');
    const next: QueueMember = { ...m, state_at: new Date().toISOString() };
    if (action === 'login') { next.logged_in = true; next.paused = false; next.pause_reason = null; }
    if (action === 'logout') { next.logged_in = false; next.paused = false; next.pause_reason = null; }
    if (action === 'pause') { next.paused = true; next.pause_reason = reason ?? null; }
    if (action === 'unpause') { next.paused = false; next.pause_reason = null; }
    const members = [...q.members];
    members[idx] = next;
    return members;
  }

  /** Qoʻngʻiroq raqamiga mos jonli kanal bormi — ichki raqamning joriy holatini aniqlashda ishlatiladi (M2b §2). */
  function activeCallForExtension(number: string): LiveCall | undefined {
    return liveCalls.find((c) => c.extension === number && (c.state === 'up' || c.state === 'ringing'));
  }

  function agentStateFor(m: QueueMember, ext: Extension | undefined): LiveAgentState {
    if (!m.logged_in) return 'offline';
    if (ext?.dnd) return 'unavailable';
    if (m.paused) return 'paused';
    const call = activeCallForExtension(m.extension.number);
    if (call?.state === 'ringing') return 'ringing';
    if (call?.state === 'up') return 'busy';
    return 'idle';
  }

  function extensionStateFor(e: Extension): LiveExtensionState {
    if (e.dnd) return 'dnd';
    const call = activeCallForExtension(e.number);
    if (call) return call.state === 'ringing' ? 'ringing' : 'busy';
    return e.status === 'offline' ? 'unavailable' : 'idle';
  }

  /** Joriy foydalanuvchiga bogʻlangan ichki raqam yoʻq bo'lsa — kabinetdagi barcha amallar 409 `no_extension` qaytaradi. */
  /** M3a §2 — `/me/softphone` va `/me/softphone/status` uchun bir xil shartlar (serverdagi `softphone_extension`). */
  function requireSoftphoneExtension() {
    if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
    const mu = requireManagedUser(currentUser.id);
    const ext = mu.extension ? extensions.find((e) => e.id === mu.extension!.id) : undefined;
    if (!ext) err(404, 'no_extension', 'Profilingizga ichki raqam bogʻlanmagan.');
    if (!ext.webrtc) err(409, 'webrtc_disabled', 'Bu ichki raqam brauzer softfoni uchun yoqilmagan.');
    if (!ext.enabled) err(409, 'extension_disabled', 'Ichki raqam oʻchirilgan.');
    return ext;
  }

  function requireOwnExtension(): Extension {
    if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
    const mu = requireManagedUser(currentUser!.id);
    if (!mu.extension) err(409, 'no_extension', 'Profilingizga ichki raqam bogʻlanmagan.');
    const ext = extensions.find((e) => e.id === mu.extension!.id);
    if (!ext) err(409, 'no_extension', 'Profilingizga ichki raqam bogʻlanmagan.');
    return ext;
  }

  function requireOwnVoicemailBox(): VoicemailBox {
    const ext = requireOwnExtension();
    const box = voicemailBoxes.find((b) => b.extension?.id === ext.id);
    if (!box) err(409, 'no_extension', 'Profilingizga ovozli pochta qutisi bogʻlanmagan.');
    return box;
  }

  /** Bu ichki raqamga chiquvchi marshrutlardan birortasi ruxsat berganmi (kabinet kartasidagi "chiquvchi ruxsat" belgisi). */
  // ─────────────────────── M5b — Follow Me / QR egasi ───────────────────────
  function followMeOwner(target: FollowMeTarget): Extension {
    if (target === null) return requireOwnExtension();
    requireManage('pbx.manage');
    const ext = extensions.find((e) => e.id === target);
    if (!ext) err(404, 'not_found', 'Ichki raqam topilmadi.');
    return ext;
  }

  function followMeInfo(ext: Extension): FollowMeInfo {
    return { extension_id: ext.id, number: ext.number, follow_me: followMeByExt.get(ext.id) ?? defaultFollowMe(), updated_at: ext.updated_at };
  }

  function extensionOutboundAllowed(extId: string): boolean {
    return outboundRoutes.some((r) => r.enabled && (r.extensions === 'all' || r.extensions.some((e) => e.id === extId)));
  }

  /** Davr parametrlari toʻgʻri va 92 kundan oshmasin (M2b §5). */
  function validateReportRange(params: ReportRangeParams) {
    const fromTs = Date.parse(params.from);
    const toTs = Date.parse(params.to);
    if (Number.isNaN(fromTs) || Number.isNaN(toTs) || toTs < fromTs) {
      err(422, 'bad_range', 'Davr notoʻgʻri — tugash sanasi boshlanishidan oldin boʻlmasin.', { field: 'to' });
    }
    if ((toTs - fromTs) / 86_400_000 > 92) err(422, 'bad_range', 'Davr 92 kundan oshmasligi kerak.', { field: 'to' });
  }

  function callsInRange(params: ReportRangeParams): Call[] {
    const fromTs = Date.parse(params.from);
    const toTs = Date.parse(params.to);
    return calls.filter((c) => { const ts = Date.parse(c.started_at); return ts >= fromTs && ts <= toTs; });
  }

  /** Chaqiruvni navbatga bog'lash — CDR'da navbat maydoni yo'q, shuning uchun taxminiy, lekin barqaror taqsimlash (M2b §5, fake-maʼlumot soddalashtirishi). */
  function assignedQueueId(c: Call): string | null {
    if (c.direction !== 'in' || queues.length === 0) return null;
    const idx = calls.findIndex((x) => x.uniqueid === c.uniqueid);
    return queues[idx % queues.length]?.id ?? null;
  }

  /** Chaqiruvga aloqador ichki raqam — kiruvchi/ichki uchun `dst`, chiquvchi uchun `src` (seed maʼlumoti shunday tuzilgan). */
  function callAgentNumber(c: Call): string | null {
    return c.direction === 'out' ? c.src : c.dst;
  }

  const PIN_RE = /^\d{4,8}$/;
  const MAILBOX_RE = /^[0-9]{2,10}$/;
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  const CHAT_ID_RE = /^(-?[0-9]{1,20}|@[A-Za-z0-9_]{5,32})$/;
  /** M2c §4 — Telegram ogohlantirish chat ID'lari faqat raqamli (kanal nomi emas), qarang m2c-contract.md §4. */
  const ALERT_CHAT_ID_RE = /^-?\d{1,20}$/;
  const TELEGRAM_API_RE = /^https?:\/\/\S+$/;
  // M2a — qarang ../../replica/m2a-contract.md
  const FORWARD_NUMBER_RE = /^\+?[0-9]{2,15}$/;
  const PICKUP_GROUP_RE = /^[a-z0-9_-]{1,32}$/;
  const FEATURE_CODE_RE = /^\*[0-9*#]{1,6}$/;
  const CONFERENCE_PIN_RE = /^\d{4,8}$/;
  const PARK_RESERVED = new Set(Array.from({ length: 21 }, (_, i) => String(700 + i))); // 700-720 (§3)
  // M3a §2 — webrtc=true bo'lsa kodeklar shu to'plamning bo'sh bo'lmagan qism to'plami bo'lishi kerak.
  const DEFAULT_WEBRTC_CODECS: WebrtcCodec[] = ['opus', 'ulaw', 'alaw'];

  /** webrtc/codecs juftligini tekshiradi va saqlanadigan kodeklar ro'yxatini qaytaradi (422 `webrtc_codec`, field `codecs`). */
  function resolveWebrtcCodecs(webrtc: boolean, codecs: string[] | undefined, existing: string[]): string[] {
    if (!webrtc) return codecs ?? existing;
    const next = codecs ?? (existing.length > 0 ? existing : DEFAULT_WEBRTC_CODECS);
    const valid = next.length > 0 && next.every((c) => (WEBRTC_CODECS as readonly string[]).includes(c));
    if (!valid) err(422, 'webrtc_codec', 'Brauzer softfoni uchun kamida bitta kodek kerak: opus, g722, ulaw, alaw.', { field: 'codecs' });
    return next;
  }
  const BLACKLIST_NUMBER_RE = /^[0-9]{3,15}$/;
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  const MISC_DIAL_RE = /^[0-9*#+]{1,32}$/;
  const MISC_CODE_RE = /^(\*[0-9*#]{1,6}|[0-9]{1,7})$/;
  const PIN_SET_PIN_RE = /^\d{4,12}$/;
  const EXT_NUMBER_RE = /^[0-9]{2,10}$/;
  const ALERT_INFO_RE = /^[A-Za-z0-9=<>:;/._@-]{1,128}$/;

  /** `""` — `null` kabi tozalaydi (§1); berilmagan maydon `undefined` holida qoladi. */
  function clearsEmpty(v: string | null | undefined): string | null | undefined {
    if (v === undefined || v === null) return v;
    return v === '' ? null : v;
  }

  // SIP paroli — backend bilan bitta shartnoma: `src/domain/sipPassword.ts`dagi sof funksiya orqali
  // tekshiriladi, shu yerda 422 `weak_password`ga aylantiriladi (field `password`).
  const SIP_PASSWORD_ERROR_MESSAGE: Record<SipPasswordIssue, string> = {
    too_short: 'SIP paroli kamida 8 belgidan iborat boʻlsin.',
    too_long: 'SIP paroli 64 belgidan oshmasin.',
    bad_chars: 'SIP parolida faqat lotin harflari, raqamlar va !@#$%^*_+=.,:- belgilari ruxsat etilgan.',
    no_letter: 'SIP parolida kamida bitta harf boʻlsin.',
    no_digit: 'SIP parolida kamida bitta raqam boʻlsin.',
    contains_number: 'SIP paroli ichki raqamni oʻz ichiga olmasin.',
  };

  /** Qo'lda kiritilgan SIP parolini tekshiradi — notoʻgʻri boʻlsa 422 `weak_password` otadi. */
  function checkSipPassword(password: string, extensionNumber: string) {
    const issue = validateSipPassword(password, extensionNumber);
    if (issue) err(422, 'weak_password', SIP_PASSWORD_ERROR_MESSAGE[issue], { field: 'password' });
  }

  /** SIP domeni — soʻrov kelgan server xosti (haqiqiy backend'da `Request.url.hostname`); fake'da brauzer manzili. */
  function sipDomain(): string {
    return typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : 'pbx.innova.local';
  }

  /** Ichki raqamning qoʻng'iroq sozlamalari (DND/yoʻnaltirish/pickup/chiquvchi) — yaratish VA tahrirlashda bir xil tekshiruv. */
  function resolveCallFields(payload: {
    forward_always?: string | null; forward_busy?: string | null; pickup_group?: string | null; outbound_callerid?: string | null;
  }, ownNumber: string) {
    const forwardAlways = clearsEmpty(payload.forward_always);
    const forwardBusy = clearsEmpty(payload.forward_busy);
    const pickupGroup = clearsEmpty(payload.pickup_group);
    const outboundCallerid = clearsEmpty(payload.outbound_callerid);
    if (forwardAlways != null && !FORWARD_NUMBER_RE.test(forwardAlways)) err(422, 'bad_number', 'Raqam notoʻgʻri — faqat raqamlar (2-15 ta).', { field: 'forward_always' });
    if (forwardBusy != null && !FORWARD_NUMBER_RE.test(forwardBusy)) err(422, 'bad_number', 'Raqam notoʻgʻri — faqat raqamlar (2-15 ta).', { field: 'forward_busy' });
    if (pickupGroup != null && !PICKUP_GROUP_RE.test(pickupGroup)) err(422, 'bad_pickup_group', 'Guruh nomi notoʻgʻri — kichik lotin harflari, raqam, `_`/`-` (1-32 belgi).', { field: 'pickup_group' });
    if (outboundCallerid != null && !FORWARD_NUMBER_RE.test(outboundCallerid)) err(422, 'bad_number', 'CallerID notoʻgʻri — faqat raqamlar (2-15 ta).', { field: 'outbound_callerid' });
    const nextForwardAlways = forwardAlways != null ? forwardAlways.replace(/^\+/, '') : forwardAlways;
    const nextForwardBusy = forwardBusy != null ? forwardBusy.replace(/^\+/, '') : forwardBusy;
    if (nextForwardAlways === ownNumber) err(422, 'bad_number', 'Oʻz raqamiga yoʻnaltirib boʻlmaydi.', { field: 'forward_always' });
    if (nextForwardBusy === ownNumber) err(422, 'bad_number', 'Oʻz raqamiga yoʻnaltirib boʻlmaydi.', { field: 'forward_busy' });
    return { forwardAlways: nextForwardAlways, forwardBusy: nextForwardBusy, pickupGroup, outboundCallerid };
  }

  /** M3c §1 — BITTA birlashtirish qoidasi (create VA update shu funksiyani chaqiradi, backend
   * `app/api/v1/extensions.py::_recording_changes` bilan bir xil): eski `recording` berilsa
   * IKKALASINI ham o'rnatadi (orqaga moslik); aniq `recording_in`/`recording_out` berilsa ular ustun turadi. */
  function resolveRecordingChanges(payload: {
    recording?: RecordingPolicy; recording_in?: RecordingPolicy; recording_out?: RecordingPolicy;
  }): { recording?: RecordingPolicy; recording_out?: RecordingPolicy } {
    const legacy = payload.recording;
    const recIn = payload.recording_in ?? legacy;
    const recOut = payload.recording_out ?? legacy;
    const changes: { recording?: RecordingPolicy; recording_out?: RecordingPolicy } = {};
    if (recIn !== undefined) changes.recording = recIn;
    if (recOut !== undefined) changes.recording_out = recOut;
    return changes;
  }

  /** `anonymous`/`restricted`/boʻsh — yashirin CallerID uchun bitta maxsus qiymatga keltiriladi (§5). */
  function normalizeBlacklistNumber(raw: string): string {
    const trimmed = raw.trim().toLowerCase();
    if (trimmed === '' || trimmed === 'anonymous' || trimmed === 'restricted') return 'anonymous';
    return raw.replace(/[\s()-]/g, '').replace(/^\+/, '');
  }

  /** Berilgan target id — kiruvchi marshrut/IVR/navbat/qoʻngʻiroq guruhi/vaqt sharti ichida ishlatilganmi (§4 oʻchirish). */
  function usagesForTargetId(id: string): Usage[] {
    const items: Usage[] = [];
    routes.forEach((r) => { if (!r.target.broken && r.target.id === id) items.push({ kind: 'inbound_route', id: r.id, label: r.name, field: 'target' }); });
    ivrs.forEach((v) => {
      v.options.forEach((o) => { if (o.target.id === id) items.push({ kind: 'ivr', id: v.id, label: v.name, field: `digit:${o.digit}` }); });
      if (v.timeout_target.id === id) items.push({ kind: 'ivr', id: v.id, label: v.name, field: 'timeout' });
      if (v.invalid_target.id === id) items.push({ kind: 'ivr', id: v.id, label: v.name, field: 'invalid' });
    });
    ringGroups.forEach((r) => { if (r.no_answer_target.id === id) items.push({ kind: 'ring_group', id: r.id, label: r.name, field: 'no_answer' }); });
    queues.forEach((q) => { if (q.timeout_target.id === id) items.push({ kind: 'queue', id: q.id, label: q.name, field: 'timeout' }); });
    timeConditions.forEach((c) => {
      if (c.open_target.id === id) items.push({ kind: 'time_condition', id: c.id, label: c.name, field: 'open' });
      if (c.closed_target.id === id) items.push({ kind: 'time_condition', id: c.id, label: c.name, field: 'closed' });
    });
    announcements.forEach((a) => { if (a.next_target.id === id) items.push({ kind: 'announcement', id: a.id, label: a.name, field: 'next' }); });
    dayNights.forEach((dn) => {
      if (dn.day_target.id === id) items.push({ kind: 'day_night', id: dn.id, label: dn.name, field: 'day' });
      if (dn.night_target.id === id) items.push({ kind: 'day_night', id: dn.id, label: dn.name, field: 'night' });
    });
    return items;
  }

  /** Ikki xususiyat kodi toʻqnashadimi — teng yoki biri ikkinchisining prefiksi (§2). */
  function codesConflict(a: string, b: string): boolean {
    return a === b || a.startsWith(b) || b.startsWith(a);
  }

  /** Xususiyat kodi — boshqa xususiyat kodlari VA vaqt sharti almashtirish kodlari (`toggle_code`) bilan toʻqnashmasin (§2/§9). */
  function checkFeatureCodeTaken(code: string, excludeFeature?: string) {
    const conflictFc = featureCodes.find((f) => f.feature !== excludeFeature && codesConflict(f.code, code));
    if (conflictFc) err(409, 'code_taken', `Bu kod «${conflictFc.code}» bilan toʻqnashadi.`, { field: 'code', details: { conflict: conflictFc.code } });
    const conflictTc = timeConditions.find((c) => c.toggle_code && codesConflict(c.toggle_code, code));
    if (conflictTc) err(409, 'code_taken', `Bu kod «${conflictTc.toggle_code}» bilan toʻqnashadi.`, { field: 'code', details: { conflict: conflictTc.toggle_code } });
  }

  /** Vaqt sharti almashtirish kodi (`toggle_code`) — xususiyat kodlari va boshqa shartlar bilan toʻqnashmasin (§2). */
  function checkToggleCodeTaken(code: string, excludeId?: string) {
    const conflictFc = featureCodes.find((f) => codesConflict(f.code, code));
    if (conflictFc) err(409, 'code_taken', `Bu kod «${conflictFc.code}» bilan toʻqnashadi.`, { field: 'toggle_code', details: { conflict: conflictFc.code } });
    const conflictTc = timeConditions.find((c) => c.id !== excludeId && c.toggle_code && codesConflict(c.toggle_code, code));
    if (conflictTc) err(409, 'code_taken', `Bu kod «${conflictTc.toggle_code}» bilan toʻqnashadi.`, { field: 'toggle_code', details: { conflict: conflictTc.toggle_code } });
  }

  /** Kun/tun `*28<code>` — boshqa xususiyat/almashtirish kodlari bilan toʻqnashmasin (M12 A1, `_validate_exten_code` bilan bir xil g'oya). */
  function checkDayNightCodeTaken(code: string, excludeId?: string) {
    const exten = `*28${code}`;
    const conflictFc = featureCodes.find((f) => codesConflict(f.code, exten));
    if (conflictFc) err(409, 'code_taken', `Bu kod «${conflictFc.code}» bilan toʻqnashadi.`, { field: 'code', details: { conflict: conflictFc.code } });
    const conflictTc = timeConditions.find((c) => c.toggle_code && codesConflict(c.toggle_code, exten));
    if (conflictTc) err(409, 'code_taken', `Bu kod «${conflictTc.toggle_code}» bilan toʻqnashadi.`, { field: 'code', details: { conflict: conflictTc.toggle_code } });
    const conflictDn = dayNights.find((d) => d.id !== excludeId && codesConflict(`*28${d.code}`, exten));
    if (conflictDn) err(409, 'code_taken', `Bu kod «*28${conflictDn.code}» bilan toʻqnashadi.`, { field: 'code', details: { conflict: `*28${conflictDn.code}` } });
  }

  function voicemailCounts(boxId: string) {
    const msgs = voicemailMessages.get(boxId) ?? [];
    return { new: msgs.filter((m) => m.folder === 'inbox').length, old: msgs.filter((m) => m.folder === 'old').length };
  }

  function voicemailBoxOut(b: VoicemailBox): VoicemailBox {
    return { ...b, counts: voicemailCounts(b.id) };
  }

  function toExtensionTarget(ext: Extension): Target {
    return { id: ext.id, kind: 'extension', label: `${ext.number} · ${ext.name}`, number: ext.number, broken: false };
  }

  /** `call_targets` — bitta polimorf id maydoni: barcha turlar bo'yicha qidiradi (shartnoma: `*_target_id`). */
  function findTargetAnyKind(id: string): Target | null {
    const e = extensions.find((x) => x.id === id);
    if (e) return toExtensionTarget(e);
    const r = ringGroups.find((x) => x.id === id);
    if (r) return { id: r.id, kind: 'ring_group', label: r.name, number: r.number, broken: false };
    const q = queues.find((x) => x.id === id);
    if (q) return { id: q.id, kind: 'queue', label: q.name, number: q.number, broken: false };
    const v = ivrs.find((x) => x.id === id);
    if (v) return { id: v.id, kind: 'ivr', label: v.name, number: v.number, broken: false };
    const c = timeConditions.find((x) => x.id === id);
    if (c) return { id: c.id, kind: 'time_condition', label: c.name, number: c.number, broken: false };
    const cf = conferences.find((x) => x.target_id === id);
    if (cf) return { id: cf.target_id, kind: 'conference', label: cf.name, number: cf.number, broken: false };
    const an = announcements.find((x) => x.target_id === id);
    if (an) return { id: an.target_id, kind: 'announcement', label: an.name, number: null, broken: false };
    const md = miscDestinations.find((x) => x.target_id === id);
    if (md) return { id: md.target_id, kind: 'misc', label: md.name, number: md.dial, broken: false };
    const dn = dayNights.find((x) => x.id === id);
    if (dn) return { id: dn.id, kind: 'day_night', label: dn.name, number: null, broken: false };
    const da = disas.find((x) => x.id === id);
    if (da) return { id: da.id, kind: 'disa', label: da.name, number: null, broken: false };
    if (id === SYS_HANGUP_TARGET.id) return SYS_HANGUP_TARGET;
    if (id === SYS_BUSY_TARGET.id) return SYS_BUSY_TARGET;
    return null;
  }

  function requireTarget(id: string, field: string): Target {
    const t = findTargetAnyKind(id);
    if (!t) err(404, 'not_found', 'Manzil topilmadi — oʻchirilgan boʻlishi mumkin.', { field });
    return t;
  }

  /** CID lookup manbasi — kiruvchi marshrutga bogʻlanadi (M9 B2). */
  function requireCidSource(id: string): CidSource {
    const s = cidSources.find((c) => c.id === id);
    if (!s) err(404, 'not_found', 'CID manbasi topilmadi.', { field: 'cid_lookup_source_id' });
    return s;
  }

  /** PIN toʻplami — chiquvchi marshrutga bogʻlanadi (M9 B1). */
  function requirePinSet(id: string): PinSet {
    const p = pinSets.find((x) => x.id === id);
    if (!p) err(404, 'not_found', 'PIN toʻplami topilmadi.', { field: 'pin_set_id' });
    return p;
  }

  function pinSetUsedBy(id: string): { id: string; name: string }[] {
    return outboundRoutes.filter((r) => r.pin_set?.id === id).map((r) => ({ id: r.id, name: r.name }));
  }

  function cidSourceUsedBy(id: string): { id: string; name: string }[] {
    return routes.filter((r) => r.cid_lookup_source?.id === id).map((r) => ({ id: r.id, name: r.name }));
  }

  function allTargets(): Target[] {
    return [
      ...extensions.map(toExtensionTarget),
      ...ringGroups.map((r): Target => ({ id: r.id, kind: 'ring_group', label: r.name, number: r.number, broken: false })),
      ...queues.map((q): Target => ({ id: q.id, kind: 'queue', label: q.name, number: q.number, broken: false })),
      ...ivrs.map((v): Target => ({ id: v.id, kind: 'ivr', label: v.name, number: v.number, broken: false })),
      ...timeConditions.map((c): Target => ({ id: c.id, kind: 'time_condition', label: c.name, number: c.number, broken: false })),
      ...conferences.map((cf): Target => ({ id: cf.target_id, kind: 'conference', label: cf.name, number: cf.number, broken: false })),
      ...announcements.map((an): Target => ({ id: an.target_id, kind: 'announcement', label: an.name, number: null, broken: false })),
      ...miscDestinations.map((md): Target => ({ id: md.target_id, kind: 'misc', label: md.name, number: md.dial, broken: false })),
      ...dayNights.map((dn): Target => ({ id: dn.id, kind: 'day_night', label: dn.name, number: null, broken: false })),
      ...disas.map((da): Target => ({ id: da.id, kind: 'disa', label: da.name, number: null, broken: false })),
      SYS_HANGUP_TARGET,
      SYS_BUSY_TARGET,
    ];
  }

  function allDialNumbers(excludeId?: string): string[] {
    const nums: string[] = [];
    extensions.forEach((e) => { if (e.id !== excludeId) nums.push(e.number); });
    ringGroups.forEach((r) => { if (r.number && r.id !== excludeId) nums.push(r.number); });
    queues.forEach((q) => { if (q.number && q.id !== excludeId) nums.push(q.number); });
    ivrs.forEach((v) => { if (v.number && v.id !== excludeId) nums.push(v.number); });
    timeConditions.forEach((c) => { if (c.number && c.id !== excludeId) nums.push(c.number); });
    conferences.forEach((cf) => { if (cf.number && cf.id !== excludeId) nums.push(cf.number); });
    return nums;
  }

  /** Maxsus kod (`misc_applications.code`) — xizmat kodlari, boshqa maxsus kodlar VA ichki raqamlar bilan toʻqnashmasin, prefiks ham (A2 §2). */
  function checkMiscCodeTaken(code: string, excludeId?: string) {
    const conflictMisc = miscApplications.find((m) => m.id !== excludeId && codesConflict(m.code, code));
    if (conflictMisc) err(409, 'code_taken', `Bu kod «${conflictMisc.code}» bilan toʻqnashadi.`, { field: 'code', details: { conflict: conflictMisc.code } });
    const conflictFc = featureCodes.find((f) => codesConflict(f.code, code));
    if (conflictFc) err(409, 'code_taken', `Bu kod «${conflictFc.code}» bilan toʻqnashadi.`, { field: 'code', details: { conflict: conflictFc.code } });
    const conflictNum = allDialNumbers().find((n) => codesConflict(n, code));
    if (conflictNum) err(409, 'code_taken', `Bu kod «${conflictNum}» raqami bilan toʻqnashadi.`, { field: 'code', details: { conflict: conflictNum } });
  }

  /** 700-720 — park uchun zahiralangan (§2/§3): har qanday raqam maydoni (ext/IVR/guruh/navbat/vaqt sharti/konferensiya) uchun bitta joy. */
  function checkNumberTaken(number: string | null | undefined, excludeId?: string) {
    if (!number) return;
    if (PARK_RESERVED.has(number)) err(409, 'number_taken', `${number} park uchun ajratilgan (700-720).`, { field: 'number', details: { reason: 'reserved' } });
    if (allDialNumbers(excludeId).includes(number)) err(409, 'number_taken', `${number} raqami band.`, { field: 'number' });
  }

  function validateRanges(ranges: TimeRange[]) {
    for (const r of ranges) {
      if (r.end <= r.start) err(422, 'range_order', 'Tugash vaqti boshlanish vaqtidan keyin boʻlishi kerak.', { field: 'ranges' });
    }
  }

  function tzParts(d: Date) {
    const fmt = new Intl.DateTimeFormat('en-GB', {
      timeZone: TZ, weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
      year: 'numeric', month: '2-digit', day: '2-digit',
    });
    const parts = fmt.formatToParts(d);
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
    const weekdayMap: Record<string, number> = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 };
    return { weekday: (weekdayMap[get('weekday')] ?? 1) as Weekday, hhmm: `${get('hour')}:${get('minute')}`, date: `${get('year')}-${get('month')}-${get('day')}` };
  }

  function isHoliday(dateStr: string): boolean {
    const [, m, d] = dateStr.split('-');
    return holidays.some((h) => h.day === dateStr || (h.recurring_yearly && h.day.slice(5) === `${m}-${d}`));
  }

  function computeStateNow(timeGroupId: string, honorHolidays: boolean): 'open' | 'closed' {
    const tg = timeGroups.find((t) => t.id === timeGroupId);
    if (!tg) return 'closed';
    const { weekday, hhmm, date } = tzParts(new Date());
    if (honorHolidays && isHoliday(date)) return 'closed';
    const open = tg.ranges.some((r) => r.weekdays.includes(weekday) && hhmm >= r.start && hhmm < r.end);
    return open ? 'open' : 'closed';
  }

  function stateForOverride(override: TimeCondition['override'], timeGroupId: string, honorHolidays: boolean): 'open' | 'closed' {
    if (override === 'force_open') return 'open';
    if (override === 'force_closed') return 'closed';
    return computeStateNow(timeGroupId, honorHolidays);
  }

  // --- IVR halqa tekshiruvi (timeout/invalid yo'li) ---
  function ivrEdgeLookup(overrideId?: string, overrideEdges?: IvrEdges): IvrEdgeLookup {
    return (ivrId: string): IvrEdges | null => {
      if (overrideId && ivrId === overrideId) return overrideEdges ?? null;
      const v = ivrs.find((x) => x.id === ivrId);
      if (!v) return null;
      return { timeout: { kind: v.timeout_target.kind, id: v.timeout_target.id }, invalid: { kind: v.invalid_target.kind, id: v.invalid_target.id } };
    };
  }

  function labelForIvrId(ivrId: string, tempId: string, tempName: string): string {
    if (ivrId === tempId) return tempName;
    return ivrs.find((v) => v.id === ivrId)?.name ?? ivrId;
  }

  function checkIvrLoop(id: string, name: string, timeoutTarget: Target, invalidTarget: Target) {
    const loop = findIvrLoop(id, ivrEdgeLookup(id, {
      timeout: { kind: timeoutTarget.kind, id: timeoutTarget.id },
      invalid: { kind: invalidTarget.kind, id: invalidTarget.id },
    }));
    if (loop) {
      const path = loop.path.map((pid) => labelForIvrId(pid, id, name));
      err(422, 'loop', 'Bu IVR chiqishsiz halqaga kiradi — timeout/invalid yoʻlini tekshiring.', { details: { path } });
    }
  }

  // --- Qo'ng'iroq oqimi grafigi (GET /flow/{id}) uchun qidiruv ---
  function lookupForFlow(ref: FlowRef): FlowLookupResult | null {
    const kind = ref.kind as TargetKind;
    if (kind === 'extension') {
      const e = extensions.find((x) => x.id === ref.id);
      return e ? { target: toExtensionTarget(e), edges: [] } : null;
    }
    if (kind === 'ring_group') {
      const r = ringGroups.find((x) => x.id === ref.id);
      if (!r) return null;
      return { target: { id: r.id, kind, label: r.name, number: r.number, broken: false }, edges: [{ edge: 'no_answer', ref: { kind: r.no_answer_target.kind, id: r.no_answer_target.id } }] };
    }
    if (kind === 'queue') {
      const q = queues.find((x) => x.id === ref.id);
      if (!q) return null;
      return { target: { id: q.id, kind, label: q.name, number: q.number, broken: false }, edges: [{ edge: 'timeout', ref: { kind: q.timeout_target.kind, id: q.timeout_target.id } }] };
    }
    if (kind === 'ivr') {
      const v = ivrs.find((x) => x.id === ref.id);
      if (!v) return null;
      const edges = [
        ...v.options.map((o) => ({ edge: `digit:${o.digit}`, ref: { kind: o.target.kind, id: o.target.id } })),
        { edge: 'timeout', ref: { kind: v.timeout_target.kind, id: v.timeout_target.id } },
        { edge: 'invalid', ref: { kind: v.invalid_target.kind, id: v.invalid_target.id } },
      ];
      return { target: { id: v.id, kind, label: v.name, number: v.number, broken: false }, edges };
    }
    if (kind === 'time_condition') {
      const c = timeConditions.find((x) => x.id === ref.id);
      if (!c) return null;
      return {
        target: { id: c.id, kind, label: c.name, number: c.number, broken: false },
        edges: [
          { edge: 'open', ref: { kind: c.open_target.kind, id: c.open_target.id } },
          { edge: 'closed', ref: { kind: c.closed_target.kind, id: c.closed_target.id } },
        ],
      };
    }
    if (kind === 'hangup') return { target: SYS_HANGUP_TARGET, edges: [] };
    if (kind === 'busy') return { target: SYS_BUSY_TARGET, edges: [] };
    return null;
  }

  function toFlowNodeApi(node: FlowGraphNode): FlowNodeApi {
    return {
      target: { ...node.target, kind: node.target.kind as TargetKind },
      edge: node.edge,
      loop: node.loop,
      broken: node.broken,
      children: node.children.map(toFlowNodeApi),
    };
  }

  function auditAdd(action: AuditEntry['action'], entity: string, entityId: string | null, label: string | null, diff: AuditEntry['diff']) {
    const user = currentUser ? { id: currentUser.id, login: currentUser.login } : null;
    auditLog = [{ id: randomId('au'), at: new Date().toISOString(), user, action, entity, entity_id: entityId, label, diff, ip: '10.0.0.5' }, ...auditLog];
  }

  function toSimRoute(r: OutboundRoute): SimRoute {
    return {
      id: r.id, name: r.name, priority: r.priority, enabled: r.enabled, patterns: r.patterns,
      trunks: r.trunks.map((t) => ({ id: t.trunk.id, name: t.trunk.name, health_state: t.trunk.health_state })),
      callerid: r.callerid, override_extension_callerid: r.override_extension_callerid,
      international: r.international, extensions: r.extensions === 'all' ? 'all' : r.extensions.map((e) => e.id),
    };
  }

  /** Qo'ng'iroq guruhining tashqi a'zosi uchun — ichki raqam ruxsati e'tiborga olinmaydi, qolgan qoidalar amal qiladi. */
  function hasOutboundRouteFor(number: string): boolean {
    const forAny = outboundRoutes.map((r) => ({ ...toSimRoute(r), extensions: 'all' as const }));
    return simulateOutbound(forAny, '__any__', number).allowed;
  }

  function outboundRouteUsages(trunkId: string): Usage[] {
    return outboundRoutes
      .filter((r) => r.trunks.some((t) => t.trunk.id === trunkId))
      .map((r) => ({ kind: 'outbound_route', id: r.id, label: r.name, field: 'trunks' }));
  }

  /** A'zo — ichki raqam yoki tashqi raqam (§3). Tashqi raqam uchun mos chiquvchi marshrut bo'lishi shart. */
  function resolveRingGroupMembers(input: CreateRingGroupPayload['members']): RingGroup['members'] {
    return input.map((m, i) => {
      if ('extension_id' in m && m.extension_id) {
        const e = extensions.find((x) => x.id === m.extension_id);
        if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'members' });
        return { position: i + 1, extension: { id: e.id, number: e.number, name: e.name }, external_number: null };
      }
      const number: string = 'external_number' in m && m.external_number ? m.external_number : '';
      if (!hasOutboundRouteFor(number)) err(422, 'no_outbound_route', `${number} uchun mos chiquvchi marshrut topilmadi.`, { field: 'members', details: { number } });
      return { position: i + 1, extension: null, external_number: number };
    });
  }

  function resolveMohClass(id: string | null | undefined): Queue['moh_class'] {
    if (!id) return null;
    const m = mohClasses.find((x) => x.id === id);
    if (!m) err(404, 'not_found', 'Kutish musiqasi sinfi topilmadi.', { field: 'moh_class_id' });
    return { id: m.id, name: m.name };
  }

  function resolveMohFiles(fileIds: string[]): Audio[] {
    return fileIds.map((fid) => {
      const a = audioList.find((x) => x.id === fid);
      if (!a) err(404, 'not_found', 'Audio fayl topilmadi.', { field: 'file_ids' });
      return a;
    });
  }

  function validateOutboundPatterns(patterns: OutboundPattern[]) {
    patterns.forEach((p, index) => {
      // backend (pydantic `str`) null'ni rad etadi — fake ham xuddi shunday (2026-11-02: UI null yuborardi)
      for (const f of ['strip_prefix', 'add_prefix', 'callerid_match'] as const) {
        if (typeof p[f] !== 'string') err(422, 'validation_error', "Soʻrov maʼlumotlari yaroqsiz", { field: `patterns.${index}.${f}` });
      }
      const parsed = parsePattern(p.pattern);
      // backend normallashtirmaydi: '_' yoki kichik harf — rad (canonicalPattern dan o'tmagan)
      if (!parsed.ok || parsed.normalized !== p.pattern) err(422, 'bad_pattern', 'Naqsh notoʻgʻri — qatorni tekshiring.', { details: { index, reason: parsed.ok ? 'not-normalized' : parsed.error.code } });
    });
  }

  function resolveOutboundTrunks(ids: string[]): OutboundTrunkRef[] {
    return ids.map((tid, i) => {
      const t = trunks.find((x) => x.id === tid);
      if (!t) err(404, 'not_found', 'Trunk topilmadi.', { field: 'trunk_ids' });
      return { position: i + 1, trunk: { id: t.id, name: t.name, health_state: t.health.state } };
    });
  }

  function resolveOutboundExtensions(input: 'all' | string[]): 'all' | OutboundExtensionRef[] {
    if (input === 'all') return 'all';
    return input.map((eid) => {
      const e = extensions.find((x) => x.id === eid);
      if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'extensions' });
      return { id: e.id, number: e.number, name: e.name };
    });
  }

  function validateSipPayload(payload: UpdateSipSettingsPayload) {
    (payload.local_nets ?? []).forEach((n) => { if (!isValidCidr(n)) err(422, 'bad_cidr', `${n} notoʻgʻri CIDR.`, { field: 'local_nets' }); });
    const start = payload.rtp_start ?? sipSettings.rtp_start;
    const end = payload.rtp_end ?? sipSettings.rtp_end;
    if (end - start < 100) err(422, 'rtp_range', 'RTP oraligʻi kamida 100 port boʻlishi kerak.', { field: 'rtp_end' });
    const udp = payload.sip_udp_port ?? sipSettings.sip_udp_port;
    const tls = payload.sip_tls_port !== undefined ? payload.sip_tls_port : sipSettings.sip_tls_port;
    if (tls !== null && tls === udp) err(422, 'bad_port', 'UDP va TLS portlari bir xil boʻlmasligi kerak.', { field: 'sip_tls_port' });
  }

  const RESTART_FIELDS = ['sip_udp_port', 'sip_tls_port', 'rtp_start', 'rtp_end', 'external_ip', 'external_host', 'local_nets'] as const;
  function sipPatchNeedsRestart(payload: UpdateSipSettingsPayload): boolean {
    return RESTART_FIELDS.some((f) => payload[f] !== undefined);
  }

  /** `0` — chegarasiz/muddatsiz maʼno beradi, shu sabab "0 yoki [min..max]" shaklida tekshiriladi (m2c-contract.md §1). */
  function checkBound(value: number | undefined, field: string, min: number, max: number, zeroMeansUnlimited: boolean) {
    if (value === undefined) return;
    if (zeroMeansUnlimited && value === 0) return;
    if (value < min || value > max) {
      const range = zeroMeansUnlimited ? `0 yoki ${min}–${max}` : `${min}–${max}`;
      err(422, 'bad_value', `Qiymat ${range} oraligʻida boʻlishi kerak.`, { field });
    }
  }

  function validateSecuritySettingsPayload(payload: UpdateSecuritySettingsPayload) {
    const sg = payload.sip_guard;
    if (sg) {
      checkBound(sg.max_failures, 'sip_guard.max_failures', 3, 100, false);
      checkBound(sg.window_s, 'sip_guard.window_s', 10, 3600, false);
      checkBound(sg.ban_s, 'sip_guard.ban_s', 10, 2592000, true);
      if (sg.trusted_nets) {
        if (sg.trusted_nets.length > 50) err(422, 'too_long', 'Koʻpi bilan 50 ta tarmoq.', { field: 'sip_guard.trusted_nets' });
        sg.trusted_nets.forEach((n) => { if (!isValidCidr(n)) err(422, 'bad_cidr', `${n} notoʻgʻri CIDR.`, { field: 'sip_guard.trusted_nets' }); });
      }
    }
    const tf = payload.toll_fraud;
    if (tf) {
      checkBound(tf.max_concurrent_outbound, 'toll_fraud.max_concurrent_outbound', 1, 500, true);
      checkBound(tf.ext_max_per_hour, 'toll_fraud.ext_max_per_hour', 1, 10000, true);
      checkBound(tf.ext_international_per_day, 'toll_fraud.ext_international_per_day', 1, 10000, true);
    }
  }

  function diskUsage() {
    return { used_pct: 42, free_gb: 118.3 };
  }

  function buildDashboard(): DashboardResult {
    const today = calls.filter((c) => Date.parse(c.started_at) >= Date.parse('2026-10-27T00:00:00Z'));
    const byHour = Array.from({ length: 24 }, (_, hour) => ({ hour, in: 0, out: 0, missed: 0 }));
    today.forEach((c) => {
      const h = byHour[new Date(c.started_at).getUTCHours()];
      if (!h) return;
      if (c.direction === 'in') h.in += 1; else if (c.direction === 'out') h.out += 1;
      if (c.disposition !== 'answered' && c.direction === 'in') h.missed += 1;
    });
    const missedCalls = today
      .filter((c) => c.direction === 'in' && c.disposition !== 'answered')
      .slice(0, 10)
      .map((c): DashboardResult['missed'][number] => ({
        uniqueid: c.uniqueid, started_at: c.started_at, src: c.src, did: c.did,
        called_back: today.some((o) => o.direction === 'out' && o.dst === c.src && o.disposition === 'answered' && Date.parse(o.started_at) > Date.parse(c.started_at)),
      }))
      .sort((a, b) => Number(a.called_back) - Number(b.called_back));
    const alerts: DashboardResult['alerts'] = [];
    trunks.forEach((t) => { if (t.enabled && t.health.state === 'unreachable') alerts.push({ level: 'danger', code: 'trunk_down', text: `${t.name} javob bermayapti`, link: '/trunks' }); });
    if (revisions[0]?.status === 'rolled_back') alerts.push({ level: 'warn', code: 'revision_rolled_back', text: `Reviziya r${revisions[0].id} qoʻllanmadi — oldingi holatga qaytarildi`, link: '/settings/revisions' });
    const answered = today.filter((c) => c.disposition === 'answered');
    return {
      health: {
        asterisk: { up: true, version: '22.4.0', uptime_s: 1_234_800 },
        db: { up: true },
        disk: diskUsage(),
        trunks: trunks.map((t) => ({ id: t.id, name: t.name, state: t.health.state, registration: t.health.registration, reason: t.health.reason })),
      },
      live: { active_calls: 0, calls: [] },
      queues: queues.map((q) => ({ id: q.id, name: q.name, waiting: q.live?.waiting ?? 0, members_online: q.live?.members_online ?? 0, longest_wait_s: 0 })),
      today: {
        total: today.length, answered: answered.length,
        missed: today.filter((c) => c.direction === 'in' && c.disposition !== 'answered').length,
        out: today.filter((c) => c.direction === 'out').length,
        avg_wait_s: answered.length ? Math.round(answered.reduce((s, c) => s + c.duration, 0) / answered.length) : null,
        by_hour: byHour,
      },
      missed: missedCalls,
      alerts,
    };
  }

  // ─────────────────────── Tizim holati (status/cleanup) — pbx-klon vazifa (2026-11-02) ───────────────────────

  const DISK_TOTAL_GB = 100;
  /** Asterisk/OS/DB va boshqa alohida hisoblanmaydigan hajm — kategoriyalar ustiga qo'shiladi. */
  const DISK_OTHER_GB = 21.8;
  const GB = 1024 ** 3;

  function diskCategories(): DiskCategory[] {
    const backupsBytes = backups.reduce((s, b) => s + (b.size_bytes ?? 0), 0);
    return [
      { key: 'recordings', bytes: diskRecordings.bytes, files: diskRecordings.files, cleanable: true },
      { key: 'backups', bytes: backupsBytes, files: backups.length, cleanable: true },
      { key: 'migrations', bytes: diskMigrations.bytes, files: diskMigrations.files, cleanable: true },
      { key: 'voicemail', bytes: diskVoicemail.bytes, files: diskVoicemail.files, cleanable: false },
      { key: 'logs', bytes: diskLogs.bytes, files: diskLogs.files, cleanable: false },
    ];
  }

  /** Kategoriyalar + "boshqa" (OS/Asterisk/DB) hajmidan hisoblanadi — tozalashdan keyin qayta chaqirilganda avtomatik kamayadi. */
  function buildDisk(): SystemDisk {
    const categories = diskCategories();
    const categoriesGb = categories.reduce((s, c) => s + c.bytes, 0) / GB;
    const usedGb = Math.min(DISK_TOTAL_GB, categoriesGb + DISK_OTHER_GB);
    return {
      total_gb: DISK_TOTAL_GB,
      used_gb: Math.round(usedGb * 10) / 10,
      free_gb: Math.round((DISK_TOTAL_GB - usedGb) * 10) / 10,
      used_pct: Math.round((usedGb / DISK_TOTAL_GB) * 100),
      categories,
    };
  }

  function buildSystemStatus(): SystemStatus {
    return {
      disk: buildDisk(),
      trunks: trunks.map((t) => ({ id: t.id, name: t.name, state: t.health.state, registration: t.health.registration, reason: t.health.reason })),
      internet: { up: true, dns_ok: true, latency_ms: 18, target: '1.1.1.1', error: null },
      sip: {
        asterisk_up: true,
        transports: [
          { name: 'udp', protocol: 'udp', bind: '0.0.0.0:5060' },
          { name: 'tcp', protocol: 'tcp', bind: '0.0.0.0:5060' },
          { name: 'wss', protocol: 'wss', bind: '0.0.0.0:8089' },
        ],
        endpoints_total: extensions.length,
        endpoints_online: extensions.filter((e) => e.status === 'online').length,
      },
    };
  }

  function clamp(v: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, v));
  }

  /** Kiritilgan parametrlarga qarab qancha bo'shaydi — kunlar qancha kichik bo'lsa, shuncha ko'p yozuv eskirgan hisoblanadi (demo formula). */
  function cleanupPlan(payload: CleanupIn): CleanupResult {
    const recordingsFraction = payload.recordings_older_than_days == null ? 0 : clamp(1 - payload.recordings_older_than_days / 365, 0.05, 0.95);
    const recordings = {
      files: Math.round(diskRecordings.files * recordingsFraction),
      bytes: Math.round(diskRecordings.bytes * recordingsFraction),
    };
    const excessBackups = payload.backups_keep_last == null ? [] : backups.slice(payload.backups_keep_last);
    const backupsResult = { files: excessBackups.length, bytes: excessBackups.reduce((s, b) => s + (b.size_bytes ?? 0), 0) };
    const migrationsResult = payload.migrations ? { files: diskMigrations.files, bytes: diskMigrations.bytes } : { files: 0, bytes: 0 };
    return {
      recordings,
      backups: backupsResult,
      migrations: migrationsResult,
      total_bytes: recordings.bytes + backupsResult.bytes + migrationsResult.bytes,
      errors: [],
    };
  }

  // ─────────────────────── Tarmoq sozlamalari (network) — M8 (../../replica/m8-network-contract.md) ───────────────────────

  /** Pending muddati o'tgan bo'lsa — jim o'zi avtomatik qaytaradi (real taymer o'rniga har chaqiriqda tekshiradi). */
  function checkNetworkPendingExpiry(): void {
    if (!netPending || Date.now() <= Date.parse(netPending.expires_at)) return;
    if (netPendingSnapshot) {
      netHostname = netPendingSnapshot.hostname;
      netDns = netPendingSnapshot.dns;
      netIfaces = netPendingSnapshot.interfaces;
      netRoutesStatic = netPendingSnapshot.routes;
    }
    netLastResult = { kind: 'rolled_back', at: new Date().toISOString(), message: 'Muddat tugadi — avtomatik qaytarildi.' };
    netPending = null;
    netPendingSnapshot = null;
  }

  function networkDefaultGateway(): { address: string | null; interface: string | null } {
    const withGw = netIfaces.find((i) => i.config.mode === 'static' && i.config.gateway);
    return { address: withGw?.config.gateway ?? null, interface: withGw?.name ?? null };
  }

  function buildNetworkState(): NetworkStateOut {
    checkNetworkPendingExpiry();
    return {
      helper: { available: true, version: '1.0.0', error: null },
      backend: 'ifupdown',
      editable: true,
      readonly_reason: null,
      hostname: netHostname,
      dns: { ...netDns, editable: true },
      default_gateway: networkDefaultGateway(),
      interfaces: netIfaces,
      routes: { static: netRoutesStatic, live: netRoutesStatic.map((r) => ({ ...r, protocol: 'static' })) },
      pending: netPending,
      last_result: netLastResult,
    };
  }

  /** `payload`dagi qiymatlarni joriy holatga ko'chiradi — faqat `applyNetwork` ichida, validatsiyadan keyin chaqiriladi. */
  function applyNetworkConfigToState(payload: NetworkConfigIn): void {
    netHostname = payload.hostname;
    netDns = { servers: payload.dns.servers, search: payload.dns.search };
    netIfaces = netIfaces.map((ifc) => {
      const next = payload.interfaces.find((i) => i.name === ifc.name);
      if (!next) return ifc;
      const isStatic = next.mode === 'static';
      const config = { mode: next.mode, address: isStatic ? next.address : null, gateway: isStatic ? next.gateway : null, mtu: next.mtu ?? ifc.mtu };
      const live_ipv4 = isStatic && next.address ? [next.address] : next.mode === 'dhcp' ? (ifc.live_ipv4.length ? ifc.live_ipv4 : ['192.168.10.55/24']) : [];
      return { ...ifc, config, live_ipv4, mtu: config.mtu };
    });
    netRoutesStatic = payload.routes.map((r) => ({ destination: r.destination, gateway: r.gateway, interface: r.interface, metric: r.metric }));
  }

  // ─────────────────────── Sana/vaqt (M12 B1) — ../../replica/m12-contract.md §B1 ───────────────────────

  function buildTimeState(): TimeStateOut {
    return {
      now_utc: new Date().toISOString(), timezone: timeTimezone, ntp_enabled: timeNtpEnabled,
      ntp_servers: timeNtpServers, synced: timeNtpEnabled, backend: 'timesyncd', readonly_reason: null,
      default_ntp_servers: defaultNtpServers(timeTimezone),
      sync_server: timeNtpEnabled ? (timeNtpServers[0] ?? defaultNtpServers(timeTimezone)[0] ?? null) : null,
    };
  }

  // ─────────────────────── Firewall GUI (M12 B3) — ../../replica/m12-contract.md §B3 ───────────────────────

  /** Pending muddati o'tgan bo'lsa — jim o'zi avtomatik qaytaradi (`checkNetworkPendingExpiry` bilan bir xil naqsh). */
  function checkFirewallPendingExpiry(): void {
    if (!fwPending || Date.now() <= Date.parse(fwPending.expires_at)) return;
    if (fwPendingSnapshot) {
      fwServices = fwPendingSnapshot.services;
      fwBlockedCidrs = fwPendingSnapshot.blockedCidrs;
    }
    fwLastResult = { kind: 'rolled_back', at: new Date().toISOString(), message: 'Muddat tugadi — avtomatik qaytarildi.' };
    fwPending = null;
    fwPendingSnapshot = null;
  }

  function buildFirewallState(): FirewallStateOut {
    checkFirewallPendingExpiry();
    return { services: fwServices, blocked_cidrs: fwBlockedCidrs, readonly_reason: null, pending: fwPending, last_result: fwLastResult };
  }

  function applyFirewallConfigToState(payload: FirewallConfigIn): void {
    fwServices = payload.services.map((s) => ({ name: s.name, mode: s.mode, allow: s.allow }));
    fwBlockedCidrs = payload.blocked_cidrs;
  }

  // ─────────────────────── M4a — qarang ../../replica/m4a-contract.md ───────────────────────

  /** 12 ta hex belgigacha tozalaydi (`:`/`-`/probel olib tashlanadi), kichik harfga keltiradi. Notoʻgʻri boʻlsa 422 `bad_value`. */
  function normalizeMac(raw: string): string {
    const mac = raw.toLowerCase().replace(/[:\-\s]/g, '');
    if (!/^[0-9a-f]{12}$/.test(mac)) err(422, 'bad_value', 'MAC manzil notoʻgʻri — 12 ta hex belgidan iborat boʻlishi kerak.', { field: 'mac' });
    return mac;
  }

  function deviceExtensionRef(id: string): Device['extension'] {
    const e = extensions.find((x) => x.id === id);
    return e ? { id: e.id, number: e.number, name: e.name } : null;
  }

  /** Ichki raqamga apparat biriktirish shartlari (shartnoma §5): webrtc yoqilgan raqamga boʻlmaydi,
   * bir raqamga `MAX_CONTACTS_PER_EXTENSION` dan ortiq apparat ulab boʻlmaydi. */
  function assertExtensionCanHaveDevice(extensionId: string, excludeDeviceId?: string) {
    const e = extensions.find((x) => x.id === extensionId);
    if (!e) err(422, 'bad_value', 'Ichki raqam topilmadi.', { field: 'extension_id' });
    if (e.webrtc) err(422, 'extension_webrtc', 'Brauzer softfoni yoqilgan ichki raqamga apparat ulab boʻlmaydi.', { field: 'extension_id' });
    const attached = devices.filter((d) => d.extension?.id === extensionId && d.id !== excludeDeviceId);
    if (attached.length >= MAX_CONTACTS_PER_EXTENSION) {
      err(422, 'max_contacts', `Bu ichki raqamga koʻpi bilan ${MAX_CONTACTS_PER_EXTENSION} ta apparat ulanishi mumkin.`, { field: 'extension_id' });
    }
  }

  /** BLF tugmalari faqat mavjud ichki raqamlarga, yorliqda yangi qator boʻlmasligi kerak (shartnoma §5). */
  function validateDeviceKeys(keys: DeviceKey[]) {
    for (const k of keys) {
      if (k.label && k.label.includes('\n')) err(422, 'bad_value', 'Yorliqda yangi qator boʻlishi mumkin emas.', { field: 'label' });
      if (k.type === 'blf' && k.value && !extensions.some((e) => e.number === k.value)) {
        err(422, 'bad_value', 'Bu raqamga BLF ulab boʻlmaydi — ichki raqamlar roʻyxatida yoʻq.', { field: 'value' });
      }
    }
  }

  function deviceModelLimit(vendor: Device['vendor'], model: string): number | null {
    return deviceModels.find((m) => m.vendor === vendor && m.model === model)?.keys ?? null;
  }

  /** Vendorga mos demo konfig matni — parol har doim `***` bilan maskalangan (hech qachon ochilmaydi). */
  function renderDeviceConfig(d: Device): DeviceConfigResult {
    const host = provisioningSettingsCore.sip_server_host ?? 'pbx.innova.local';
    if (d.vendor === 'grandstream') {
      return {
        filename: `cfg${d.mac}.xml`,
        content: [
          '<?xml version="1.0" encoding="UTF-8"?>',
          '<gs_provision version="1">',
          `  <config version="1" model="${d.model}">`,
          `    <P47>${host}</P47>`,
          '    <P35>***</P35>',
          `    <P270>${d.extension?.number ?? ''}</P270>`,
          '  </config>',
          '</gs_provision>',
        ].join('\n'),
      };
    }
    const lines = [
      `# ${d.vendor} ${d.model} — ${d.mac}`,
      `account.1.sip_server.1.address = ${host}`,
      `account.1.auth_name = ${d.extension?.number ?? ''}`,
      'account.1.password = ***',
      `account.1.label = ${d.label ?? d.extension?.name ?? ''}`,
    ];
    return { filename: d.vendor === 'fanvil' ? `${d.mac}.cfg` : `${d.mac}.boot`, content: lines.join('\n') };
  }

  // ─────────────────────── M5a — qarang ../../replica/m5a-contract.md (S36 «Ko'chirish») ───────────────────────

  /** `pre_import` zaxirani M4b mexanizmi bilan yaratadi (lokal, darhol tayyor) — `restoreBackup` keyin shundan tiklanadi. */
  function createPreImportBackup(): string {
    const now = new Date().toISOString();
    const id = randomId('bk');
    const fileName = backupFileName('innova-pbx1-pre-import', now, id);
    backups = [{
      id, kind: 'pre_import', status: 'ok', components: ['config'], step: null, progress: 100,
      file_name: fileName, sha256: randomSecret(), manifest: null, size_bytes: 1_048_576,
      copies: [{ target: 'local', status: 'ok', remote_path: `/var/lib/innova/backups/${fileName}`, size_bytes: 1_048_576, error: null, uploaded_at: now }],
      created_by: currentUser ? { id: currentUser.id, login: currentUser.login } : null, created_at: now,
    }, ...backups];
    return id;
  }

  function requireMigrationJob(id: string): FakeMigrationRecord {
    const rec = migrationJobs.get(id);
    if (!rec) err(404, 'not_found', "Ko'chirish ishi topilmadi.");
    return rec;
  }

  /** Joriy bosqichni (agar tugagan bo'lsa) yakunlab, dinamik `backup_ready`ni qo'shib javob shaklini qaytaradi. */
  function snapshotMigrationJob(rec: FakeMigrationRecord): MigrationJob {
    advanceMigrationJob(rec, finalizeMigrationAnalyze, finalizeMigrationApply);
    return { ...rec.job, backup_ready: !!backupPassphraseValue, source_meta: rec.bundleDeleted ? { ...rec.job.source_meta!, file_name: null, size_bytes: null } : rec.job.source_meta };
  }

  function finalizeMigrationAnalyze(rec: FakeMigrationRecord) {
    rec.plan = cloneFixturePlan();
    rec.ignored = [...FREEPBX_FIXTURE_IGNORED];
    rec.warnings = [...FREEPBX_FIXTURE_WARNINGS];
    const now = new Date().toISOString();
    rec.job = {
      ...rec.job, status: 'analyzed', step: null, progress: 100,
      source_meta: {
        file_name: rec.job.source_meta?.file_name ?? null, size_bytes: rec.job.source_meta?.size_bytes ?? null,
        host: rec.job.source_meta?.host ?? 'pbx-old.innova.local', freepbx_version: '17.0.33.2', asterisk_version: '20.9.0',
        created_at: rec.job.source_meta?.created_at ?? now,
      },
      summary: summarizePlan(rec.plan, rec.ignored.length, rec.warnings.length),
    };
    auditAdd('update', 'migration_job', rec.job.id, "FreePBX tahlili yakunlandi", {});
  }

  function finalizeMigrationApply(rec: FakeMigrationRecord) {
    const now = new Date().toISOString();
    if (rec.forceFail) {
      rec.job = { ...rec.job, status: 'failed', step: null, progress: 100, error: { code: 'apply_failed', message: "Qo'llash vaqtida xatolik — hech narsa o'zgarmadi (tranzaksiya qaytarildi)." }, finished_at: now };
      auditAdd('update', 'migration_job', rec.job.id, "FreePBX importi muvaffaqiyatsiz", {});
      return;
    }
    const created: Partial<Record<MigrationPlanItem['kind'], number>> = {};
    let skipped = 0;
    for (const item of rec.plan) {
      if (item.action === 'create') created[item.kind] = (created[item.kind] ?? 0) + 1;
      else if (item.action === 'skip') skipped += 1;
    }
    const totalWarnings = rec.plan.reduce((n, item) => n + item.warnings.length, 0) + rec.warnings.length;
    const revision = apply("FreePBX importi");
    rec.job = {
      ...rec.job, status: 'ok', step: null, progress: 100,
      result: { created, skipped, warnings: totalWarnings, revision_id: String(revision.revision) },
      finished_at: now,
    };
    auditAdd('update', 'migration_job', rec.job.id, "FreePBX importi qo'llanildi", {});
  }

  function migrationJobBusy(): boolean {
    if ([...backupJobs.values()].some((j) => jobProgress(j) < 100)) return true;
    return [...migrationJobs.values()].some((r) => r.phase !== null && migrationPhaseProgress(r) < 100);
  }

  function newMigrationJob(source: MigrationJob['source'], sourceMeta: MigrationJob['source_meta']): MigrationJob {
    const now = new Date().toISOString();
    return {
      id: randomId('mjob'), source, status: 'uploaded', step: null, progress: 0, source_meta: sourceMeta,
      summary: null, options: { rotate_weak_secrets: false }, result: null, error: null, pre_import_backup_id: null,
      backup_ready: !!backupPassphraseValue, created_by: currentUser ? { id: currentUser.id, login: currentUser.login } : null,
      created_at: now, finished_at: null,
    };
  }

  // ─────────────────────── M12 A1 — Kun/Tun rejimi (*28N) ───────────────────────
  let dayNights = seedDayNight(toExtensionTarget(extensions[0]!), { id: ringGroups[0]!.id, kind: 'ring_group', label: ringGroups[0]!.name, number: ringGroups[0]!.number, broken: false });
  const dayNightPins = new Map<string, string>();

  // ─────────────────────── M12 A2 — DISA ───────────────────────
  let disas = seedDisa();
  const disaPins = new Map<string, string>([[disas[0]!.id, SEED_DISA_PIN]]);

  return {
    async setupState() {
      await delay();
      return { needed };
    },

    async setup(payload: SetupPayload): Promise<AuthResult> {
      await delay();
      if (!needed) err(409, 'setup_done', 'Sozlash allaqachon bajarilgan.');
      const user: User = { id: 'u-admin', login: payload.admin.login, full_name: payload.admin.full_name, role: 'admin', permissions: SEED_ADMIN.permissions, language: payload.language };
      needed = false;
      createdAdmin = { login: payload.admin.login, password: payload.admin.password, user };
      users = [...users, {
        id: user.id, username: user.login, full_name: user.full_name, email: null, role: 'admin', extension: null,
        is_active: true, language: payload.language, must_change_password: false, totp_enabled: false,
        last_login_at: null, updated_at: new Date().toISOString(),
      }];
      userPasswords.set(user.id, payload.admin.password);
      const tokens = issueTokens(user);
      return { status: 'ok', ...tokens, user };
    },

    async login(login: string, password: string): Promise<AuthResult> {
      await delay();
      const rec = attempts.get(login);
      if (rec && rec.until > Date.now()) err(423, 'locked', 'Koʻp marta notoʻgʻri urinish. 15 daqiqadan keyin qayta urining.');
      let match: User | null = createdAdmin && login === createdAdmin.login && password === createdAdmin.password ? createdAdmin.user : null;
      if (!match) {
        const mu = users.find((u) => u.username === login);
        if (mu && mu.is_active && userPasswords.get(mu.id) === password) match = toSessionUser(mu);
      }
      if (!match) {
        const count = (rec?.count ?? 0) + 1;
        attempts.set(login, { count, until: count >= LOCK_AFTER ? Date.now() + LOCK_MS : 0 });
        if (count >= LOCK_AFTER) err(423, 'locked', 'Koʻp marta notoʻgʻri urinish. 15 daqiqadan keyin qayta urining.');
        err(401, 'bad_credentials', 'Login yoki parol notoʻgʻri.');
      }
      attempts.delete(login);
      // M10 B2 — 2FA yoqilgan bo'lsa tokenlar o'rniga challenge qaytadi (§B2).
      if (totpByUser.get(match.id)?.enabled) {
        const challenge = randomId('totpc');
        totpChallenges.set(challenge, { userId: match.id, attempts: 0 });
        return { status: 'totp_required', challenge };
      }
      users = users.map((u) => (u.id === match!.id ? { ...u, last_login_at: new Date().toISOString() } : u));
      const tokens = issueTokens(match);
      return { status: 'ok', ...tokens, user: match };
    },

    async loginTotp({ challenge, code }: LoginTotpPayload): Promise<AuthResult> {
      await delay();
      const pending = totpChallenges.get(challenge);
      if (!pending) err(401, 'bad_challenge', 'Tasdiqlash muddati tugagan. Qayta kiring.');
      const mu = requireManagedUser(pending.userId);
      const state = totpByUser.get(mu.id);
      const ok = state && (await verifyAnyTotpCode(state, code));
      if (!ok) {
        pending.attempts += 1;
        if (pending.attempts >= 5) { totpChallenges.delete(challenge); err(401, 'bad_challenge', 'Urinishlar tugadi. Qayta kiring.'); }
        err(401, 'bad_code', 'Kod notoʻgʻri.', { field: 'code' });
      }
      totpChallenges.delete(challenge);
      users = users.map((u) => (u.id === mu.id ? { ...u, last_login_at: new Date().toISOString() } : u));
      const match = toSessionUser(mu);
      const tokens = issueTokens(match);
      return { status: 'ok', ...tokens, user: match };
    },

    async refresh(refreshToken: string) {
      await delay(80);
      const userId = refreshTokens.get(refreshToken);
      if (!userId) err(401, 'bad_refresh', 'Sessiya tugagan. Qayta kiring.');
      refreshTokens.delete(refreshToken);
      const user = currentUser && currentUser.id === userId ? currentUser : SEED_ADMIN;
      return issueTokens(user);
    },

    async logout(refreshToken: string) {
      await delay(80);
      refreshTokens.delete(refreshToken);
      currentUser = null;
    },

    async me(): Promise<User> {
      await delay(80);
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      return currentUser;
    },

    async listExtensions({ q = '', page = 1, size = 50 }: ListExtensionsParams): Promise<Paged<Extension>> {
      await delay();
      const needle = q.trim().toLowerCase();
      const filtered = extensions.filter((e) => !needle || `${e.number} ${e.name}`.toLowerCase().includes(needle));
      const start = (page - 1) * size;
      return { items: filtered.slice(start, start + size), total: filtered.length };
    },

    async createExtension(payload: CreateExtensionPayload): Promise<Created<Extension>> {
      await delay();
      requireManage('pbx.manage');
      let number = payload.number?.trim();
      if (number) {
        checkNumberTaken(number);
      } else {
        const taken = new Set(allDialNumbers());
        number = Array.from({ length: 900 }, (_, i) => String(100 + i)).find((n) => !taken.has(n) && !PARK_RESERVED.has(n));
        if (!number) err(409, 'number_taken', 'Boʻsh raqam qolmadi.');
      }
      const webrtc = payload.webrtc ?? false;
      const codecs = resolveWebrtcCodecs(webrtc, payload.codecs, []);
      const call = resolveCallFields(payload, number);
      const recording = resolveRecordingChanges(payload);
      const password = payload.password ?? generateSipPassword(number);
      if (payload.password !== undefined) checkSipPassword(payload.password, number);
      const now = new Date().toISOString();
      const recordingIn = recording.recording ?? 'never';
      const item: Extension = {
        id: randomId('e'), number, name: payload.name.trim(), enabled: payload.enabled ?? true, status: 'unknown', contact: null, user_agent: null,
        dnd: payload.dnd ?? false,
        forward_always: call.forwardAlways ?? null, forward_busy: call.forwardBusy ?? null, pickup_group: call.pickupGroup ?? null,
        outbound_allowed: payload.outbound_allowed ?? true, outbound_callerid: call.outboundCallerid ?? null,
        updated_at: now,
        toll_blocked_at: null, toll_block_reason: null, webrtc, codecs,
        recording: recordingIn, recording_in: recordingIn, recording_out: recording.recording_out ?? 'never',
        call_waiting: payload.call_waiting ?? true,
      };
      extensions = [...extensions, item];
      const sip: SipCredentials = { username: number, password, domain: sipDomain(), port: 5060 };
      return { item, sip, apply: apply(`Ichki raqam ${number} qoʻshildi`, payload.name) };
    },

    async updateExtension(id: string, payload: UpdateExtensionPayload): Promise<Mutated<Extension>> {
      await delay();
      requireManage('pbx.manage');
      const cur = extensions.find((e) => e.id === id);
      if (!cur) err(404, 'not_found', 'Ichki raqam topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const call = resolveCallFields(payload, cur.number);
      const recording = resolveRecordingChanges(payload);
      const webrtc = payload.webrtc ?? cur.webrtc;
      const codecs = resolveWebrtcCodecs(webrtc, payload.codecs, cur.codecs);
      const now = new Date().toISOString();
      const recordingIn = recording.recording ?? cur.recording_in;
      const item: Extension = {
        ...cur,
        name: payload.name ?? cur.name,
        enabled: payload.enabled ?? cur.enabled,
        dnd: payload.dnd ?? cur.dnd,
        forward_always: payload.forward_always !== undefined ? (call.forwardAlways as string | null) : cur.forward_always,
        forward_busy: payload.forward_busy !== undefined ? (call.forwardBusy as string | null) : cur.forward_busy,
        pickup_group: payload.pickup_group !== undefined ? (call.pickupGroup as string | null) : cur.pickup_group,
        outbound_allowed: payload.outbound_allowed ?? cur.outbound_allowed,
        outbound_callerid: payload.outbound_callerid !== undefined ? (call.outboundCallerid as string | null) : cur.outbound_callerid,
        webrtc, codecs,
        recording: recordingIn, recording_in: recordingIn, recording_out: recording.recording_out ?? cur.recording_out,
        call_waiting: payload.call_waiting ?? cur.call_waiting,
        updated_at: now,
      };
      extensions = extensions.map((e) => (e.id === id ? item : e));
      // Faqat dnd/yo'naltirish/pickup/chiquvchi o'zgarsa — realtime (§1): reviziya/dialplan reload shart emas. webrtc/codecs — M3a §2: reload'siz (realtime).
      const callFieldsOnly = payload.name === undefined && payload.enabled === undefined
        && (payload.dnd !== undefined || payload.forward_always !== undefined || payload.forward_busy !== undefined || payload.pickup_group !== undefined
          || payload.outbound_allowed !== undefined || payload.outbound_callerid !== undefined
          || payload.webrtc !== undefined || payload.codecs !== undefined
          || payload.recording !== undefined || payload.recording_in !== undefined || payload.recording_out !== undefined
          || payload.call_waiting !== undefined);
      const applyResult: ApplyResult = callFieldsOnly ? { status: 'applied', revision: null, message: null } : apply(`Ichki raqam ${item.number} tahrirlandi`, payload.name);
      return { item, apply: applyResult };
    },

    async rotateExtensionSecret(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = extensions.find((e) => e.id === id);
      if (!cur) err(404, 'not_found', 'Ichki raqam topilmadi.');
      const sip: SipCredentials = { username: cur.number, password: generateSipPassword(cur.number), domain: sipDomain(), port: 5060 };
      return { sip, apply: { status: 'realtime', revision: null, message: null } as ApplyResult };
    },

    /** `PUT /extensions/{id}/secret` — admin oʻz parolini kiritadi; siyosatga mos boʻlmasa 422 `weak_password`. */
    async setExtensionSecret(id: string, password: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = extensions.find((e) => e.id === id);
      if (!cur) err(404, 'not_found', 'Ichki raqam topilmadi.');
      checkSipPassword(password, cur.number);
      const sip: SipCredentials = { username: cur.number, password, domain: sipDomain(), port: 5060 };
      return { sip, apply: { status: 'realtime', revision: null, message: null } as ApplyResult };
    },

    async deleteExtension(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = extensions.find((e) => e.id === id);
      if (!cur) err(404, 'not_found', 'Ichki raqam topilmadi.');
      const usages = routes.filter((r) => !r.target.broken && r.target.id === id).map((r) => ({ kind: 'inbound_route', id: r.id, label: r.name }));
      if (usages.length > 0) err(409, 'in_use', `${cur.number} hali ishlatilmoqda.`, { details: { usages } });
      extensions = extensions.filter((e) => e.id !== id);
      apply(`Ichki raqam ${cur.number} oʻchirildi`);
    },

    async listTrunks() {
      await delay();
      return { items: trunks };
    },

    async createTrunk(payload: CreateTrunkPayload): Promise<Mutated<Trunk>> {
      await delay();
      requireManage('trunks.manage');
      if (!isValidHost(payload.host)) err(422, 'bad_host', 'Trunk manzili notoʻgʻri — host yoki IP kiriting.', { field: 'host' });
      if (payload.auth_mode === 'register' && !payload.password) err(422, 'password_required', 'Register rejimida parol kerak.', { field: 'password' });
      const now = new Date().toISOString();
      const registration = payload.auth_mode === 'register' ? 'unregistered' : null;
      const item: Trunk = {
        id: randomId('t'), name: payload.name, host: payload.host, port: payload.port, match: payload.match,
        codecs: payload.codecs, max_channels: payload.max_channels, enabled: payload.enabled,
        auth_mode: payload.auth_mode, username: payload.username ?? null, has_password: !!payload.password,
        from_domain: payload.from_domain ?? null, outbound_callerid: payload.outbound_callerid ?? null,
        health: { state: payload.enabled ? 'unknown' : 'disabled', rtt_ms: null, checked_at: null, registration, reason: null },
        updated_at: now,
      };
      trunks = [...trunks, item];
      return { item, apply: apply(`Trunk ${item.name} qoʻshildi`, payload.name) };
    },

    async updateTrunk(id: string, payload: UpdateTrunkPayload): Promise<Mutated<Trunk>> {
      await delay();
      requireManage('trunks.manage');
      const cur = trunks.find((t) => t.id === id);
      if (!cur) err(404, 'not_found', 'Trunk topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu trunk boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.host !== undefined && !isValidHost(payload.host)) err(422, 'bad_host', 'Trunk manzili notoʻgʻri — host yoki IP kiriting.', { field: 'host' });
      const authMode = payload.auth_mode ?? cur.auth_mode;
      if (authMode === 'register' && !payload.password && !cur.has_password) err(422, 'password_required', 'Register rejimida parol kerak.', { field: 'password' });
      if (payload.password) auditAdd('update', 'trunk', id, cur.name, { password: ['***', '***'] });
      const now = new Date().toISOString();
      const item: Trunk = {
        ...cur,
        name: payload.name ?? cur.name, host: payload.host ?? cur.host, port: payload.port ?? cur.port,
        match: payload.match ?? cur.match, codecs: payload.codecs ?? cur.codecs,
        max_channels: payload.max_channels !== undefined ? payload.max_channels : cur.max_channels,
        enabled: payload.enabled ?? cur.enabled, auth_mode: authMode,
        username: payload.username !== undefined ? payload.username : cur.username,
        has_password: payload.password ? true : cur.has_password,
        from_domain: payload.from_domain !== undefined ? payload.from_domain : cur.from_domain,
        outbound_callerid: payload.outbound_callerid !== undefined ? payload.outbound_callerid : cur.outbound_callerid,
        health: payload.enabled === false ? { ...cur.health, state: 'disabled' } : cur.health,
        updated_at: now,
      };
      trunks = trunks.map((t) => (t.id === id ? item : t));
      return { item, apply: apply(`Trunk ${item.name} tahrirlandi`, payload.name) };
    },

    async deleteTrunk(id: string) {
      await delay();
      requireManage('trunks.manage');
      const cur = trunks.find((t) => t.id === id);
      if (!cur) err(404, 'not_found', 'Trunk topilmadi.');
      const usages = outboundRouteUsages(id);
      if (usages.length > 0) err(409, 'in_use', `${cur.name} hali ishlatilmoqda.`, { details: { usages } });
      trunks = trunks.filter((t) => t.id !== id);
      apply(`Trunk ${cur.name} oʻchirildi`);
    },

    async testTrunk(id: string): Promise<TrunkTestResult> {
      await delay(500);
      const cur = trunks.find((t) => t.id === id);
      if (!cur) err(404, 'not_found', 'Trunk topilmadi.');
      if (!cur.enabled) return { ok: false, rtt_ms: null, detail: 'Trunk oʻchirilgan — avval yoqing.' };
      if (cur.health.state === 'unreachable') return { ok: false, rtt_ms: null, detail: 'OPTIONS javobsiz: soʻrov vaqti tugadi (timeout).' };
      return { ok: true, rtt_ms: 18 + Math.round(Math.random() * 30), detail: 'OPTIONS 200 OK.' };
    },

    async listInboundRoutes() {
      await delay();
      return { items: routes };
    },

    async createInboundRoute(payload: CreateInboundRoutePayload): Promise<Mutated<InboundRoute>> {
      await delay();
      requireManage('routes.manage');
      const conflict = routes.find((r) => (r.did ?? null) === (payload.did ?? null) && (r.cid ?? null) === (payload.cid ?? null));
      if (conflict) err(409, 'did_conflict', 'Bu DID + CallerID kombinatsiyasi allaqachon ishlatilgan.', { field: 'did' });
      const target = requireTarget(payload.target_id, 'target_id');
      if (payload.alert_info != null && !ALERT_INFO_RE.test(payload.alert_info)) err(422, 'bad_alert_info', 'Alert-Info notoʻgʻri.', { field: 'alert_info' });
      const cidLookupSource = payload.cid_lookup_source_id ? requireCidSource(payload.cid_lookup_source_id) : null;
      const now = new Date().toISOString();
      const item: InboundRoute = {
        id: randomId('r'), name: payload.name, did: payload.did, cid: payload.cid, target, enabled: payload.enabled, updated_at: now,
        cid_name_prefix: payload.cid_name_prefix ?? null, alert_info: payload.alert_info ?? null,
        cid_lookup_source: cidLookupSource ? { id: cidLookupSource.id, name: cidLookupSource.name } : null,
      };
      routes = [...routes, item];
      return { item, apply: apply(`Kiruvchi marshrut «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateInboundRoute(id: string, payload: UpdateInboundRoutePayload): Promise<Mutated<InboundRoute>> {
      await delay();
      requireManage('routes.manage');
      const cur = routes.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Marshrut topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu marshrut boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      const nextDid = payload.did !== undefined ? payload.did : cur.did;
      const nextCid = payload.cid !== undefined ? payload.cid : cur.cid;
      const conflict = routes.find((r) => r.id !== id && (r.did ?? null) === (nextDid ?? null) && (r.cid ?? null) === (nextCid ?? null));
      if (conflict) err(409, 'did_conflict', 'Bu DID + CallerID kombinatsiyasi allaqachon ishlatilgan.', { field: 'did' });
      const target = payload.target_id ? requireTarget(payload.target_id, 'target_id') : cur.target;
      if (payload.alert_info != null && !ALERT_INFO_RE.test(payload.alert_info)) err(422, 'bad_alert_info', 'Alert-Info notoʻgʻri.', { field: 'alert_info' });
      const cidLookupSource = payload.cid_lookup_source_id !== undefined
        ? (payload.cid_lookup_source_id ? requireCidSource(payload.cid_lookup_source_id) : null)
        : null;
      const now = new Date().toISOString();
      const item: InboundRoute = {
        ...cur, name: payload.name ?? cur.name, did: nextDid, cid: nextCid, target, enabled: payload.enabled ?? cur.enabled,
        cid_name_prefix: payload.cid_name_prefix !== undefined ? payload.cid_name_prefix : cur.cid_name_prefix,
        alert_info: payload.alert_info !== undefined ? payload.alert_info : cur.alert_info,
        cid_lookup_source: payload.cid_lookup_source_id !== undefined
          ? (cidLookupSource ? { id: cidLookupSource.id, name: cidLookupSource.name } : null)
          : cur.cid_lookup_source,
        updated_at: now,
      };
      routes = routes.map((r) => (r.id === id ? item : r));
      return { item, apply: apply(`Kiruvchi marshrut «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteInboundRoute(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = routes.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Marshrut topilmadi.');
      routes = routes.filter((r) => r.id !== id);
      apply(`Kiruvchi marshrut «${cur.name}» oʻchirildi`);
    },

    async listTargets({ kind, q = '' }: ListTargetsParams): Promise<{ items: Target[] }> {
      await delay(150);
      const kinds = kind ? kind.split(',').map((s) => s.trim()).filter(Boolean) : null;
      const needle = q.trim().toLowerCase();
      const items = allTargets().filter((t) => (!kinds || kinds.includes(t.kind)) && (!needle || `${t.label} ${t.number ?? ''}`.toLowerCase().includes(needle)));
      return { items };
    },

    async targetUsages(id: string): Promise<{ items: Usage[] }> {
      await delay(150);
      return { items: usagesForTargetId(id) };
    },

    async parking(): Promise<Parking> {
      await delay(150);
      requireManage('pbx.manage'); // §3 — faqat admin; operatorda 403 (dashboard kartasi shunga ko'ra yashiriladi)
      return parkingState;
    },

    async flow(inboundRouteId: string): Promise<FlowResult> {
      await delay(200);
      const route = routes.find((r) => r.id === inboundRouteId);
      if (!route) err(404, 'not_found', 'Marshrut topilmadi.');
      const graph = buildFlowGraph({ kind: route.target.kind, id: route.target.id }, lookupForFlow as FlowLookup, 'target');
      return { root: toFlowNodeApi(graph) };
    },

    async numbersFree({ from = 100, to = 999, limit = 5 }: NumbersFreeParams): Promise<{ items: string[] }> {
      await delay(120);
      const taken = new Set(allDialNumbers());
      const items: string[] = [];
      for (let n = from; n <= to && items.length < limit; n += 1) {
        const s = String(n);
        if (!taken.has(s) && !PARK_RESERVED.has(s)) items.push(s);
      }
      return { items };
    },

    async listCalls(params: ListCallsParams): Promise<Paged<Call>> {
      await delay();
      const { page = 1, size = 50 } = params;
      const filtered = filterCallsFor(calls, params);
      const start = (page - 1) * size;
      // M10 B1 — `qa` maydoni alohida so'rovsiz: baholovlar xaritasidan shu yerda to'ldiriladi.
      const pageItems = filtered.slice(start, start + size).map((c) => ({ ...c, qa: qaOf(c.uniqueid) }));
      return { items: pageItems, total: filtered.length };
    },

    /** CDR CSV eksport — xuddi `listCalls` bilan bir xil filtr, sahifalashsiz (hammasi). */
    async exportCallsCsv(params: ListCallsParams): Promise<Blob> {
      await delay();
      return new Blob([callsToCsv(filterCallsFor(calls, params))], { type: 'text/csv;charset=utf-8' });
    },

    async systemHealth(): Promise<SystemHealth> {
      await delay(150);
      return { asterisk: { up: true, version: '22.4.0', uptime_s: 1_234_800 }, db: { up: true }, revision: revisionNumber };
    },

    async configRevisions(limit = 20): Promise<{ items: ConfigRevision[] }> {
      await delay(150);
      return { items: revisions.slice(0, limit) };
    },

    // ─────────────────────── M1a ───────────────────────

    async listTimeGroups() {
      await delay();
      return { items: timeGroups };
    },

    async createTimeGroup(payload: CreateTimeGroupPayload): Promise<Mutated<TimeGroup>> {
      await delay();
      requireManage('routes.manage');
      validateRanges(payload.ranges);
      const now = new Date().toISOString();
      const item: TimeGroup = { id: randomId('tg'), name: payload.name, ranges: payload.ranges, updated_at: now };
      timeGroups = [...timeGroups, item];
      return { item, apply: apply(`Ish vaqti guruhi «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateTimeGroup(id: string, payload: UpdateTimeGroupPayload): Promise<Mutated<TimeGroup>> {
      await delay();
      requireManage('routes.manage');
      const cur = timeGroups.find((t) => t.id === id);
      if (!cur) err(404, 'not_found', 'Ish vaqti guruhi topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu guruh boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      const ranges = payload.ranges ?? cur.ranges;
      validateRanges(ranges);
      const now = new Date().toISOString();
      const item: TimeGroup = { ...cur, name: payload.name ?? cur.name, ranges, updated_at: now };
      timeGroups = timeGroups.map((t) => (t.id === id ? item : t));
      return { item, apply: apply(`Ish vaqti guruhi «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteTimeGroup(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = timeGroups.find((t) => t.id === id);
      if (!cur) err(404, 'not_found', 'Ish vaqti guruhi topilmadi.');
      const usages = timeConditions.filter((c) => c.time_group.id === id).map((c) => ({ kind: 'time_condition', id: c.id, label: c.name, field: 'time_group' }));
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      timeGroups = timeGroups.filter((t) => t.id !== id);
      apply(`Ish vaqti guruhi «${cur.name}» oʻchirildi`);
    },

    async listHolidays() {
      await delay();
      return { items: holidays };
    },

    async createHoliday(payload: CreateHolidayPayload): Promise<Mutated<Holiday>> {
      await delay();
      requireManage('routes.manage');
      const item: Holiday = { id: randomId('hd'), name: payload.name, day: payload.day, recurring_yearly: payload.recurring_yearly };
      holidays = [...holidays, item];
      return { item, apply: apply(`Bayram «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateHoliday(id: string, payload: UpdateHolidayPayload): Promise<Mutated<Holiday>> {
      await delay();
      requireManage('routes.manage');
      const cur = holidays.find((h) => h.id === id);
      if (!cur) err(404, 'not_found', 'Bayram topilmadi.');
      const item: Holiday = { ...cur, ...payload };
      holidays = holidays.map((h) => (h.id === id ? item : h));
      return { item, apply: apply(`Bayram «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteHoliday(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = holidays.find((h) => h.id === id);
      if (!cur) err(404, 'not_found', 'Bayram topilmadi.');
      holidays = holidays.filter((h) => h.id !== id);
      apply(`Bayram «${cur.name}» oʻchirildi`);
    },

    async importUzHolidays({ year }: ImportUzHolidaysPayload): Promise<ImportUzHolidaysResult> {
      await delay(400);
      requireManage('routes.manage');
      const created: Holiday[] = [];
      for (const h of UZ_FIXED_HOLIDAYS) {
        const day = `${year}-${pad2(h.month)}-${pad2(h.day)}`;
        const exists = holidays.some((x) => x.day === day && x.recurring_yearly);
        if (!exists) {
          const item: Holiday = { id: randomId('hd'), name: h.name, day, recurring_yearly: true };
          holidays = [...holidays, item];
          created.push(item);
        }
      }
      if (created.length > 0) apply(`${year}-yil Oʻzbekiston bayramlari qoʻshildi (${created.length} ta)`);
      return { items: holidays, created: created.length, skipped: ['ramazon_hayit', 'qurbon_hayit'] };
    },

    async listTimeConditions() {
      await delay();
      timeConditions = timeConditions.map((c) => (c.override === 'auto' ? { ...c, state_now: computeStateNow(c.time_group.id, c.honor_holidays) } : c));
      return { items: timeConditions };
    },

    async createTimeCondition(payload: CreateTimeConditionPayload): Promise<Mutated<TimeCondition>> {
      await delay();
      requireManage('routes.manage');
      const tg = timeGroups.find((t) => t.id === payload.time_group_id);
      if (!tg) err(404, 'not_found', 'Ish vaqti guruhi topilmadi.', { field: 'time_group_id' });
      checkNumberTaken(payload.number ?? undefined);
      if (payload.toggle_code) checkToggleCodeTaken(payload.toggle_code);
      const openTarget = requireTarget(payload.open_target_id, 'open_target_id');
      const closedTarget = requireTarget(payload.closed_target_id, 'closed_target_id');
      const now = new Date().toISOString();
      const item: TimeCondition = {
        id: randomId('tc'), name: payload.name, number: payload.number ?? null, time_group: { id: tg.id, name: tg.name },
        honor_holidays: payload.honor_holidays, open_target: openTarget, closed_target: closedTarget,
        override: 'auto', toggle_code: payload.toggle_code ?? null,
        state_now: computeStateNow(tg.id, payload.honor_holidays), updated_at: now,
      };
      timeConditions = [...timeConditions, item];
      return { item, apply: apply(`Ish vaqti sharti «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateTimeCondition(id: string, payload: UpdateTimeConditionPayload): Promise<Mutated<TimeCondition>> {
      await delay();
      requireManage('routes.manage');
      const cur = timeConditions.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'Ish vaqti sharti topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu shart boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.number !== undefined) checkNumberTaken(payload.number ?? undefined, id);
      if (payload.toggle_code) checkToggleCodeTaken(payload.toggle_code, id);
      const tg = payload.time_group_id ? timeGroups.find((t) => t.id === payload.time_group_id) : undefined;
      if (payload.time_group_id && !tg) err(404, 'not_found', 'Ish vaqti guruhi topilmadi.', { field: 'time_group_id' });
      const openTarget = payload.open_target_id ? requireTarget(payload.open_target_id, 'open_target_id') : cur.open_target;
      const closedTarget = payload.closed_target_id ? requireTarget(payload.closed_target_id, 'closed_target_id') : cur.closed_target;
      const honorHolidays = payload.honor_holidays ?? cur.honor_holidays;
      const timeGroupRef = tg ? { id: tg.id, name: tg.name } : cur.time_group;
      const now = new Date().toISOString();
      const item: TimeCondition = {
        ...cur, name: payload.name ?? cur.name, number: payload.number !== undefined ? payload.number : cur.number,
        time_group: timeGroupRef, honor_holidays: honorHolidays, open_target: openTarget, closed_target: closedTarget,
        toggle_code: payload.toggle_code !== undefined ? payload.toggle_code : cur.toggle_code,
        state_now: stateForOverride(cur.override, timeGroupRef.id, honorHolidays), updated_at: now,
      };
      timeConditions = timeConditions.map((c) => (c.id === id ? item : c));
      return { item, apply: apply(`Ish vaqti sharti «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteTimeCondition(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = timeConditions.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'Ish vaqti sharti topilmadi.');
      const usages = routes.filter((r) => !r.target.broken && r.target.id === id).map((r) => ({ kind: 'inbound_route', id: r.id, label: r.name, field: 'target' }));
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      timeConditions = timeConditions.filter((c) => c.id !== id);
      apply(`Ish vaqti sharti «${cur.name}» oʻchirildi`);
    },

    async overrideTimeCondition(id: string, { override }: OverrideTimeConditionPayload): Promise<Mutated<TimeCondition>> {
      await delay(150);
      requireManage('routes.manage');
      const cur = timeConditions.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'Ish vaqti sharti topilmadi.');
      const now = new Date().toISOString();
      const item: TimeCondition = { ...cur, override, state_now: stateForOverride(override, cur.time_group.id, cur.honor_holidays), updated_at: now };
      timeConditions = timeConditions.map((c) => (c.id === id ? item : c));
      const label = override === 'force_closed' ? 'Tungi rejim yoqildi' : override === 'force_open' ? 'Majburiy ochiq rejim yoqildi' : 'Avtomatik rejimga qaytarildi';
      return { item, apply: apply(`«${item.name}»: ${label}`) };
    },

    async listIvrs() {
      await delay();
      return { items: ivrs };
    },

    async createIvr(payload: CreateIvrPayload): Promise<Mutated<Ivr>> {
      await delay();
      requireManage('routes.manage');
      checkNumberTaken(payload.number ?? undefined);
      const dup = findDuplicateDigit(payload.options);
      if (dup) err(422, 'duplicate_digit', `«${dup}» tugmasi ikki marta ishlatilgan.`, { field: 'options' });
      const greeting = audioList.find((a) => a.id === payload.greeting_audio_id);
      if (!greeting) err(404, 'not_found', 'Salomlashuv audiosi topilmadi.', { field: 'greeting_audio_id' });
      const invalidAudio = payload.invalid_audio_id ? audioList.find((a) => a.id === payload.invalid_audio_id) ?? null : null;
      if (payload.invalid_audio_id && !invalidAudio) err(404, 'not_found', 'Xato audio topilmadi.', { field: 'invalid_audio_id' });
      const options = payload.options.map((o) => ({ digit: o.digit, target: requireTarget(o.target_id, 'options') }));
      const timeoutTarget = requireTarget(payload.timeout_target_id, 'timeout_target_id');
      const invalidTarget = requireTarget(payload.invalid_target_id, 'invalid_target_id');
      const id = randomId('ivr');
      checkIvrLoop(id, payload.name, timeoutTarget, invalidTarget);
      const now = new Date().toISOString();
      const item: Ivr = {
        id, name: payload.name, number: payload.number ?? null, greeting, invalid_audio: invalidAudio,
        timeout_seconds: payload.timeout_seconds, repeats: payload.repeats, direct_dial: payload.direct_dial,
        options, timeout_target: timeoutTarget, invalid_target: invalidTarget, updated_at: now,
      };
      ivrs = [...ivrs, item];
      return { item, apply: apply(`IVR «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateIvr(id: string, payload: UpdateIvrPayload): Promise<Mutated<Ivr>> {
      await delay();
      requireManage('routes.manage');
      const cur = ivrs.find((v) => v.id === id);
      if (!cur) err(404, 'not_found', 'IVR topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu IVR boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.number !== undefined) checkNumberTaken(payload.number ?? undefined, id);
      const dup = payload.options ? findDuplicateDigit(payload.options) : null;
      if (dup) err(422, 'duplicate_digit', `«${dup}» tugmasi ikki marta ishlatilgan.`, { field: 'options' });
      const greeting = payload.greeting_audio_id ? audioList.find((a) => a.id === payload.greeting_audio_id) : undefined;
      if (payload.greeting_audio_id && !greeting) err(404, 'not_found', 'Salomlashuv audiosi topilmadi.', { field: 'greeting_audio_id' });
      const invalidAudio = payload.invalid_audio_id !== undefined ? (payload.invalid_audio_id ? audioList.find((a) => a.id === payload.invalid_audio_id) ?? null : null) : cur.invalid_audio;
      const options = payload.options ? payload.options.map((o) => ({ digit: o.digit, target: requireTarget(o.target_id, 'options') })) : cur.options;
      const timeoutTarget = payload.timeout_target_id ? requireTarget(payload.timeout_target_id, 'timeout_target_id') : cur.timeout_target;
      const invalidTarget = payload.invalid_target_id ? requireTarget(payload.invalid_target_id, 'invalid_target_id') : cur.invalid_target;
      checkIvrLoop(id, payload.name ?? cur.name, timeoutTarget, invalidTarget);
      const now = new Date().toISOString();
      const item: Ivr = {
        ...cur, name: payload.name ?? cur.name, number: payload.number !== undefined ? payload.number : cur.number,
        greeting: greeting ?? cur.greeting, invalid_audio: invalidAudio, options,
        timeout_seconds: payload.timeout_seconds ?? cur.timeout_seconds, repeats: payload.repeats ?? cur.repeats,
        direct_dial: payload.direct_dial ?? cur.direct_dial, timeout_target: timeoutTarget, invalid_target: invalidTarget,
        updated_at: now,
      };
      ivrs = ivrs.map((v) => (v.id === id ? item : v));
      return { item, apply: apply(`IVR «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteIvr(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = ivrs.find((v) => v.id === id);
      if (!cur) err(404, 'not_found', 'IVR topilmadi.');
      const usages = [
        ...routes.filter((r) => !r.target.broken && r.target.id === id).map((r) => ({ kind: 'inbound_route', id: r.id, label: r.name, field: 'target' })),
        ...timeConditions.filter((c) => c.open_target.id === id || c.closed_target.id === id).map((c) => ({ kind: 'time_condition', id: c.id, label: c.name, field: c.open_target.id === id ? 'open' : 'closed' })),
        ...ivrs.filter((v) => v.id !== id && (v.timeout_target.id === id || v.invalid_target.id === id || v.options.some((o) => o.target.id === id))).map((v) => ({ kind: 'ivr', id: v.id, label: v.name, field: 'target' })),
      ];
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      ivrs = ivrs.filter((v) => v.id !== id);
      apply(`IVR «${cur.name}» oʻchirildi`);
    },

    async listRingGroups() {
      await delay();
      return { items: ringGroups };
    },

    async createRingGroup(payload: CreateRingGroupPayload): Promise<Mutated<RingGroup>> {
      await delay();
      requireManage('routes.manage');
      checkNumberTaken(payload.number ?? undefined);
      const noAnswerTarget = requireTarget(payload.no_answer_target_id, 'no_answer_target_id');
      const members = resolveRingGroupMembers(payload.members);
      const now = new Date().toISOString();
      const item: RingGroup = {
        id: randomId('rg'), name: payload.name, number: payload.number ?? null, strategy: payload.strategy,
        ring_seconds: payload.ring_seconds, members, no_answer_target: noAnswerTarget,
        callerid_prefix: payload.callerid_prefix ?? null, updated_at: now,
      };
      ringGroups = [...ringGroups, item];
      return { item, apply: apply(`Qoʻngʻiroq guruhi «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateRingGroup(id: string, payload: UpdateRingGroupPayload): Promise<Mutated<RingGroup>> {
      await delay();
      requireManage('routes.manage');
      const cur = ringGroups.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Qoʻngʻiroq guruhi topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu guruh boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.number !== undefined) checkNumberTaken(payload.number ?? undefined, id);
      const noAnswerTarget = payload.no_answer_target_id ? requireTarget(payload.no_answer_target_id, 'no_answer_target_id') : cur.no_answer_target;
      const members = payload.members ? resolveRingGroupMembers(payload.members) : cur.members;
      const now = new Date().toISOString();
      const item: RingGroup = {
        ...cur, name: payload.name ?? cur.name, number: payload.number !== undefined ? payload.number : cur.number,
        strategy: payload.strategy ?? cur.strategy, ring_seconds: payload.ring_seconds ?? cur.ring_seconds,
        members, no_answer_target: noAnswerTarget, callerid_prefix: payload.callerid_prefix !== undefined ? payload.callerid_prefix : cur.callerid_prefix,
        updated_at: now,
      };
      ringGroups = ringGroups.map((r) => (r.id === id ? item : r));
      return { item, apply: apply(`Qoʻngʻiroq guruhi «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteRingGroup(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = ringGroups.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Qoʻngʻiroq guruhi topilmadi.');
      const usages = [
        ...routes.filter((r) => !r.target.broken && r.target.id === id).map((r) => ({ kind: 'inbound_route', id: r.id, label: r.name, field: 'target' })),
        ...ivrs.filter((v) => v.timeout_target.id === id || v.invalid_target.id === id || v.options.some((o) => o.target.id === id)).map((v) => ({ kind: 'ivr', id: v.id, label: v.name, field: 'target' })),
        ...timeConditions.filter((c) => c.open_target.id === id || c.closed_target.id === id).map((c) => ({ kind: 'time_condition', id: c.id, label: c.name, field: c.open_target.id === id ? 'open' : 'closed' })),
      ];
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      ringGroups = ringGroups.filter((r) => r.id !== id);
      apply(`Qoʻngʻiroq guruhi «${cur.name}» oʻchirildi`);
    },

    async listQueues() {
      await delay();
      return { items: queues };
    },

    async createQueue(payload: CreateQueuePayload): Promise<Mutated<Queue>> {
      await delay();
      requireManage('routes.manage');
      checkNumberTaken(payload.number ?? undefined);
      const timeoutTarget = requireTarget(payload.timeout_target_id, 'timeout_target_id');
      const now = new Date().toISOString();
      const members = payload.members.map(({ extension_id, penalty }) => {
        const e = extensions.find((x) => x.id === extension_id);
        if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'members' });
        // Konfiguratsiyadan qoʻshilgan a'zo — statik, boshlanishda tizimga kirgan deb hisoblanadi (M2b §1).
        return { extension: { id: e.id, number: e.number, name: e.name }, penalty, dynamic: false, logged_in: true, paused: false, pause_reason: null, state_at: now };
      });
      const mohClass = resolveMohClass(payload.moh_class_id);
      const item: Queue = {
        id: randomId('q'), name: payload.name, number: payload.number ?? null, strategy: payload.strategy,
        agent_ring_seconds: payload.agent_ring_seconds, retry_seconds: payload.retry_seconds, wrapup_seconds: payload.wrapup_seconds,
        max_wait_seconds: payload.max_wait_seconds, max_callers: payload.max_callers, announce_position: payload.announce_position,
        announce_frequency_seconds: payload.announce_frequency_seconds, sla_seconds: payload.sla_seconds, join_empty: payload.join_empty,
        record: payload.record, members, timeout_target: timeoutTarget, live: { waiting: 0, members_online: 0 },
        moh_class: mohClass, updated_at: now,
      };
      queues = [...queues, item];
      return { item, apply: apply(`Navbat «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateQueue(id: string, payload: UpdateQueuePayload): Promise<Mutated<Queue>> {
      await delay();
      requireManage('routes.manage');
      const cur = queues.find((q) => q.id === id);
      if (!cur) err(404, 'not_found', 'Navbat topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu navbat boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.number !== undefined) checkNumberTaken(payload.number ?? undefined, id);
      const timeoutTarget = payload.timeout_target_id ? requireTarget(payload.timeout_target_id, 'timeout_target_id') : cur.timeout_target;
      const now = new Date().toISOString();
      const members = payload.members
        ? payload.members.map(({ extension_id, penalty }) => {
            const e = extensions.find((x) => x.id === extension_id);
            if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'members' });
            // Mavjud a'zoning jonli holatini (login/pauza) saqlab qolamiz, faqat penalty/roʻyxat oʻzgaradi.
            const prev = cur.members.find((m) => m.extension.id === e.id);
            return prev
              ? { ...prev, extension: { id: e.id, number: e.number, name: e.name }, penalty }
              : { extension: { id: e.id, number: e.number, name: e.name }, penalty, dynamic: false, logged_in: true, paused: false, pause_reason: null, state_at: now };
          })
        : cur.members;
      const mohClass = payload.moh_class_id !== undefined ? resolveMohClass(payload.moh_class_id) : cur.moh_class;
      const item: Queue = {
        ...cur, name: payload.name ?? cur.name, number: payload.number !== undefined ? payload.number : cur.number,
        strategy: payload.strategy ?? cur.strategy, agent_ring_seconds: payload.agent_ring_seconds ?? cur.agent_ring_seconds,
        retry_seconds: payload.retry_seconds ?? cur.retry_seconds, wrapup_seconds: payload.wrapup_seconds ?? cur.wrapup_seconds,
        max_wait_seconds: payload.max_wait_seconds ?? cur.max_wait_seconds, max_callers: payload.max_callers !== undefined ? payload.max_callers : cur.max_callers,
        announce_position: payload.announce_position ?? cur.announce_position, announce_frequency_seconds: payload.announce_frequency_seconds ?? cur.announce_frequency_seconds,
        sla_seconds: payload.sla_seconds ?? cur.sla_seconds, join_empty: payload.join_empty ?? cur.join_empty, record: payload.record ?? cur.record,
        members, timeout_target: timeoutTarget, moh_class: mohClass, updated_at: now,
      };
      queues = queues.map((q) => (q.id === id ? item : q));
      return { item, apply: apply(`Navbat «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteQueue(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = queues.find((q) => q.id === id);
      if (!cur) err(404, 'not_found', 'Navbat topilmadi.');
      const usages = [
        ...routes.filter((r) => !r.target.broken && r.target.id === id).map((r) => ({ kind: 'inbound_route', id: r.id, label: r.name, field: 'target' })),
        ...ivrs.filter((v) => v.timeout_target.id === id || v.invalid_target.id === id || v.options.some((o) => o.target.id === id)).map((v) => ({ kind: 'ivr', id: v.id, label: v.name, field: 'target' })),
        ...timeConditions.filter((c) => c.open_target.id === id || c.closed_target.id === id).map((c) => ({ kind: 'time_condition', id: c.id, label: c.name, field: c.open_target.id === id ? 'open' : 'closed' })),
      ];
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      queues = queues.filter((q) => q.id !== id);
      apply(`Navbat «${cur.name}» oʻchirildi`);
    },

    // ─────────────────────── M2b §1 — navbat a'zosi real holati ───────────────────────

    async updateQueueMember(queueId: string, extensionId: string, payload: UpdateQueueMemberPayload): Promise<{ item: QueueMember }> {
      await delay();
      requireManage('routes.manage');
      const q = queues.find((x) => x.id === queueId);
      if (!q) err(404, 'not_found', 'Navbat topilmadi.');
      const idx = q.members.findIndex((m) => m.extension.id === extensionId);
      if (idx < 0) err(404, 'not_found', 'Bu ichki raqam navbat aʼzosi emas.');
      const members = [...q.members];
      members[idx] = { ...members[idx]!, ...(payload.penalty !== undefined ? { penalty: payload.penalty } : {}), ...(payload.dynamic !== undefined ? { dynamic: payload.dynamic } : {}) };
      queues = queues.map((x) => (x.id === queueId ? { ...q, members, updated_at: new Date().toISOString() } : x));
      return { item: members[idx]! };
    },

    async queueMemberAction(queueId: string, extensionId: string, action: QueueMemberAction, payload?: QueueMemberActionPayload): Promise<{ item: QueueMember }> {
      await delay();
      requireManage('pbx.manage');
      const q = queues.find((x) => x.id === queueId);
      if (!q) err(404, 'not_found', 'Navbat topilmadi.');
      const members = applyQueueMemberAction(q, extensionId, action, payload?.reason);
      queues = queues.map((x) => (x.id === queueId ? { ...q, members, updated_at: new Date().toISOString() } : x));
      return { item: members.find((m) => m.extension.id === extensionId)! };
    },

    async listAudio() {
      await delay();
      return { items: audioList };
    },

    async uploadAudio(file: File, name: string) {
      await delay(500);
      requireManage('routes.manage');
      const ext = (file.name.split('.').pop() ?? '').toLowerCase();
      const FORMATS = ['wav', 'mp3', 'ogg', 'webm'] as const;
      const format = FORMATS.find((f) => f === ext);
      if (!format) err(415, 'bad_format', 'Faqat wav, mp3, ogg yoki webm fayllar qabul qilinadi.', { field: 'file' });
      const MAX_BYTES = 20 * 1024 * 1024;
      if (file.size > MAX_BYTES) err(413, 'too_large', 'Fayl hajmi 20 MB dan oshmasligi kerak.', { field: 'file' });
      const duration_ms = 3000 + Math.round(Math.random() * 6000);
      const MAX_RECORDING_MS = 5 * 60 * 1000;
      if ((format === 'webm' || format === 'ogg') && duration_ms > MAX_RECORDING_MS) err(413, 'too_long', 'Yozuv 5 daqiqadan oshmasligi kerak.', { field: 'file' });
      const now = new Date().toISOString();
      const item: Audio = { id: randomId('au'), name: name.trim() || file.name, duration_ms, format, created_at: now };
      audioList = [...audioList, item];
      return { item };
    },

    async deleteAudio(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = audioList.find((a) => a.id === id);
      if (!cur) err(404, 'not_found', 'Audio topilmadi.');
      const usages = ivrs.filter((v) => v.greeting.id === id || v.invalid_audio?.id === id).map((v) => ({ kind: 'ivr', id: v.id, label: v.name, field: v.greeting.id === id ? 'greeting' : 'invalid_audio' }));
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      audioList = audioList.filter((a) => a.id !== id);
      apply(`Audio «${cur.name}» oʻchirildi`);
    },

    async fetchAudio(id: string) {
      await delay();
      const cur = audioList.find((a) => a.id === id);
      if (!cur) err(404, 'not_found', 'Audio topilmadi.');
      return toneWav(cur.duration_ms);
    },

    // ─────────────────────── M1b — qarang ../../replica/m1b-contract.md ───────────────────────

    async listOutboundRoutes() {
      await delay();
      return { items: [...outboundRoutes].sort((a, b) => a.priority - b.priority) };
    },

    async createOutboundRoute(payload: CreateOutboundRoutePayload): Promise<Mutated<OutboundRoute>> {
      await delay();
      requireManage('routes.manage');
      validateOutboundPatterns(payload.patterns);
      if (payload.trunk_ids.length === 0) err(422, 'no_trunk', 'Kamida bitta trunk tanlang.', { field: 'trunk_ids' });
      const trunkRefs = resolveOutboundTrunks(payload.trunk_ids);
      const extRefs = resolveOutboundExtensions(payload.extensions);
      const id = randomId('or');
      if (payload.pin) outboundPins.set(id, payload.pin);
      const pinSet = payload.pin_set_id ? requirePinSet(payload.pin_set_id) : null;
      const now = new Date().toISOString();
      const item: OutboundRoute = {
        id, name: payload.name, priority: outboundRoutes.length + 1, enabled: payload.enabled, patterns: payload.patterns,
        trunks: trunkRefs, callerid: payload.callerid ?? null, override_extension_callerid: payload.override_extension_callerid,
        has_pin: !!payload.pin, international: payload.international, extensions: extRefs, updated_at: now,
        pin_set: pinSet ? { id: pinSet.id, name: pinSet.name } : null,
      };
      outboundRoutes = [...outboundRoutes, item];
      auditAdd('create', 'outbound_route', id, item.name, { name: [null, item.name] });
      return { item, apply: apply(`Chiquvchi marshrut «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateOutboundRoute(id: string, payload: UpdateOutboundRoutePayload): Promise<Mutated<OutboundRoute>> {
      await delay();
      requireManage('routes.manage');
      const cur = outboundRoutes.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Chiquvchi marshrut topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu marshrut boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.patterns) validateOutboundPatterns(payload.patterns);
      if (payload.trunk_ids && payload.trunk_ids.length === 0) err(422, 'no_trunk', 'Kamida bitta trunk tanlang.', { field: 'trunk_ids' });
      const trunkRefs = payload.trunk_ids ? resolveOutboundTrunks(payload.trunk_ids) : cur.trunks;
      const extRefs = payload.extensions ? resolveOutboundExtensions(payload.extensions) : cur.extensions;
      if (payload.pin !== undefined) {
        if (payload.pin === null) outboundPins.delete(id); else outboundPins.set(id, payload.pin);
      }
      const pinSet = payload.pin_set_id !== undefined
        ? (payload.pin_set_id ? requirePinSet(payload.pin_set_id) : null)
        : null;
      const now = new Date().toISOString();
      const item: OutboundRoute = {
        ...cur, name: payload.name ?? cur.name, enabled: payload.enabled ?? cur.enabled,
        patterns: payload.patterns ?? cur.patterns, trunks: trunkRefs,
        callerid: payload.callerid !== undefined ? payload.callerid : cur.callerid,
        override_extension_callerid: payload.override_extension_callerid ?? cur.override_extension_callerid,
        has_pin: payload.pin !== undefined ? payload.pin !== null : cur.has_pin,
        international: payload.international ?? cur.international, extensions: extRefs, updated_at: now,
        pin_set: payload.pin_set_id !== undefined ? (pinSet ? { id: pinSet.id, name: pinSet.name } : null) : cur.pin_set,
      };
      outboundRoutes = outboundRoutes.map((r) => (r.id === id ? item : r));
      auditAdd('update', 'outbound_route', id, item.name, { name: [cur.name, item.name] });
      return { item, apply: apply(`Chiquvchi marshrut «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteOutboundRoute(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = outboundRoutes.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Chiquvchi marshrut topilmadi.');
      outboundRoutes = outboundRoutes.filter((r) => r.id !== id).map((r, i) => ({ ...r, priority: i + 1 }));
      outboundPins.delete(id);
      auditAdd('delete', 'outbound_route', id, cur.name, { name: [cur.name, null] });
      apply(`Chiquvchi marshrut «${cur.name}» oʻchirildi`);
    },

    async reorderOutboundRoutes({ ids }: OutboundOrderPayload) {
      await delay();
      requireManage('routes.manage');
      const byId = new Map(outboundRoutes.map((r) => [r.id, r]));
      const reordered = ids.map((id) => byId.get(id)).filter((r): r is OutboundRoute => !!r);
      if (reordered.length !== outboundRoutes.length) err(422, 'bad_order', 'Roʻyxat notoʻgʻri — barcha marshrutlar bitta marta boʻlishi kerak.', { field: 'ids' });
      outboundRoutes = reordered.map((r, i) => ({ ...r, priority: i + 1 }));
      apply('Chiquvchi marshrutlar tartibi oʻzgartirildi');
      return { items: outboundRoutes };
    },

    async simulateOutboundRoute({ extension, number }: OutboundSimulateParams): Promise<OutboundSimulateResult> {
      await delay(200);
      const ext = extensions.find((e) => e.number === extension || e.id === extension);
      const extId = ext?.id ?? extension;
      const simRoutes = outboundRoutes.map(toSimRoute);
      const outcome = simulateOutbound(simRoutes, extId, number);
      return { ...outcome, trunks: outcome.trunks.map((t) => ({ id: t.id, name: t.name, health_state: t.health_state as Trunk['health']['state'] })) };
    },

    async sipSettings(): Promise<SipSettings> {
      await delay(150);
      return sipSettings;
    },

    async updateSipSettings(payload: UpdateSipSettingsPayload): Promise<Mutated<SipSettings>> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== sipSettings.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      validateSipPayload(payload);
      const restartRequired = sipPatchNeedsRestart(payload);
      const now = new Date().toISOString();
      sipSettings = {
        ...sipSettings,
        external_ip: payload.external_ip !== undefined ? payload.external_ip : sipSettings.external_ip,
        external_host: payload.external_host !== undefined ? payload.external_host : sipSettings.external_host,
        local_nets: payload.local_nets ?? sipSettings.local_nets,
        sip_udp_port: payload.sip_udp_port ?? sipSettings.sip_udp_port,
        sip_tls_port: payload.sip_tls_port !== undefined ? payload.sip_tls_port : sipSettings.sip_tls_port,
        rtp_start: payload.rtp_start ?? sipSettings.rtp_start,
        rtp_end: payload.rtp_end ?? sipSettings.rtp_end,
        codecs: payload.codecs ?? sipSettings.codecs,
        restart_required: sipSettings.restart_required || restartRequired,
        updated_at: now,
      };
      const applied = apply('SIP va tarmoq sozlamalari tahrirlandi');
      return { item: sipSettings, apply: restartRequired ? { ...applied, status: 'realtime', message: 'Saqlandi — Asterisk qayta ishga tushirilishi kerak.' } : applied };
    },

    async restartAsterisk(force = false): Promise<RestartAsteriskResult> {
      await delay(800);
      requireManage('system.manage');
      const activeCalls = fakeActiveCallCount;
      if (activeCalls > 0 && !force) err(409, 'active_calls', `${activeCalls} ta faol qoʻngʻiroq bor.`, { details: { count: activeCalls } });
      sipSettings = { ...sipSettings, restart_required: false };
      auditAdd('restart', 'system', null, 'Asterisk', {});
      return { ok: true };
    },

    async dashboard(): Promise<DashboardResult> {
      await delay(200);
      return buildDashboard();
    },

    async systemStatus(): Promise<SystemStatus> {
      requireManage('*');
      await delay(200);
      return buildSystemStatus();
    },

    async previewCleanup(payload: CleanupIn): Promise<CleanupResult> {
      requireManage('*');
      await delay(150);
      return cleanupPlan(payload);
    },

    async cleanup(payload: CleanupIn): Promise<CleanupResult> {
      requireManage('*');
      await delay(300);
      const result = cleanupPlan(payload);
      diskRecordings = { bytes: diskRecordings.bytes - result.recordings.bytes, files: diskRecordings.files - result.recordings.files };
      if (payload.backups_keep_last != null) backups = backups.slice(0, payload.backups_keep_last);
      if (payload.migrations) diskMigrations = { bytes: 0, files: 0 };
      auditAdd('delete', 'system', null, 'Disk tozalash', { freed_bytes: [null, result.total_bytes] });
      return result;
    },

    // M8 — qarang ../../replica/m8-network-contract.md
    async networkState(): Promise<NetworkStateOut> {
      requireManage('*');
      await delay(150);
      return buildNetworkState();
    },

    async validateNetwork(payload: NetworkConfigIn): Promise<NetworkValidateResult> {
      requireManage('*');
      await delay(150);
      checkNetworkPendingExpiry();
      const errors = validateNetworkConfig(payload, netIfaces);
      const warnings = buildNetworkWarnings(payload, netIfaces, typeof window !== 'undefined' ? window.location.hostname : null, payload.timeout_s);
      const diff = buildNetworkDiff(payload, { hostname: netHostname, dns: netDns, interfaces: netIfaces, routes: netRoutesStatic });
      return { ok: errors.length === 0, errors, warnings, diff };
    },

    async applyNetwork(payload: NetworkConfigIn): Promise<NetworkStateOut> {
      requireManage('*');
      await delay(250);
      checkNetworkPendingExpiry();
      if (netPending) err(409, 'pending_exists', 'Boshqa oʻzgarish hali tasdiqlanishini kutmoqda.');
      const errors = validateNetworkConfig(payload, netIfaces);
      if (errors.length > 0) err(422, 'validation_failed', 'Tekshiruvdan oʻtmadi.', { details: { fields: errors } });
      netPendingSnapshot = { hostname: netHostname, dns: netDns, interfaces: netIfaces, routes: netRoutesStatic };
      const summary = buildNetworkDiff(payload, { hostname: netHostname, dns: netDns, interfaces: netIfaces, routes: netRoutesStatic });
      applyNetworkConfigToState(payload);
      const appliedAt = new Date();
      const timeoutS = clamp(payload.timeout_s, 60, 600);
      netPending = { id: randomId('netpending'), applied_at: appliedAt.toISOString(), expires_at: new Date(appliedAt.getTime() + timeoutS * 1000).toISOString(), summary };
      netLastResult = null;
      auditAdd('update', 'network', netPending.id, 'Tarmoq sozlamalari qoʻllandi', {});
      return buildNetworkState();
    },

    async confirmNetwork(pendingId: string): Promise<NetworkStateOut> {
      requireManage('*');
      await delay(200);
      checkNetworkPendingExpiry();
      if (!netPending || netPending.id !== pendingId) err(404, 'not_found', 'Kutilayotgan oʻzgarish topilmadi (muddati oʻtgan boʻlishi mumkin).');
      netLastResult = { kind: 'confirmed', at: new Date().toISOString(), message: null };
      netPending = null;
      netPendingSnapshot = null;
      auditAdd('update', 'network', pendingId, 'Tarmoq sozlamalari tasdiqlandi', {});
      return buildNetworkState();
    },

    async rollbackNetwork(pendingId: string): Promise<NetworkStateOut> {
      requireManage('*');
      await delay(200);
      checkNetworkPendingExpiry();
      if (!netPending || netPending.id !== pendingId) err(404, 'not_found', 'Kutilayotgan oʻzgarish topilmadi (muddati oʻtgan boʻlishi mumkin).');
      if (netPendingSnapshot) {
        netHostname = netPendingSnapshot.hostname;
        netDns = netPendingSnapshot.dns;
        netIfaces = netPendingSnapshot.interfaces;
        netRoutesStatic = netPendingSnapshot.routes;
      }
      netLastResult = { kind: 'rolled_back', at: new Date().toISOString(), message: null };
      netPending = null;
      netPendingSnapshot = null;
      auditAdd('update', 'network', pendingId, 'Tarmoq sozlamalari qaytarildi', {});
      return buildNetworkState();
    },

    // M12 B1 — qarang ../../replica/m12-contract.md §B1 (pending/confirm yo'q, to'g'ridan-to'g'ri qo'llanadi)
    async systemTime(): Promise<TimeStateOut> {
      requireManage('*');
      await delay(150);
      return buildTimeState();
    },

    async applyTime(payload: TimeConfigIn): Promise<TimeStateOut> {
      requireManage('*');
      await delay(250);
      const errors = validateTimeConfig(payload);
      if (errors.length > 0) err(422, 'validation_failed', 'Tekshiruvdan oʻtmadi.', { details: { fields: errors } });
      const tzChanged = timeTimezone !== payload.timezone;
      timeTimezone = payload.timezone;
      timeNtpServers = payload.ntp_servers;
      timeNtpEnabled = payload.ntp_enabled;
      auditAdd('update', 'system_time', null, 'Sana va vaqt sozlamalari', {});
      return { ...buildTimeState(), apply: tzChanged ? apply(`Vaqt zonasi: ${payload.timezone}`) : null };
    },

    async syncTime(): Promise<TimeStateOut> {
      requireManage('*');
      await delay(400);
      if (!timeNtpEnabled) err(409, 'ntp_disabled', 'NTP oʻchirilgan — avval yoqing.');
      auditAdd('update', 'system_time', null, 'Vaqt NTP bilan sinxronlandi', {});
      return buildTimeState();
    },

    // M12 B2 — qarang ../../replica/m12-contract.md §B2
    async systemPower(): Promise<PowerStatusOut> {
      requireManage('*');
      await delay(150);
      return { hostname: netHostname, active_calls: fakeActiveCallCount, readonly_reason: null };
    },

    async executePower(payload: PowerActionIn): Promise<PowerActionOut> {
      requireManage('*');
      await delay(200);
      if (payload.confirm !== netHostname) {
        err(422, 'hostname_mismatch', "Hostname mos kelmadi — qo'lda aniq yozing", { field: 'confirm' });
      }
      auditAdd('restart', 'system_power', null, `Tizim ${payload.action === 'reboot' ? 'qayta yuklanadi' : 'o\'chiriladi'}`,
        { action: [null, payload.action] });
      return { action: payload.action, delay_s: 10, scheduled: true, active_calls: fakeActiveCallCount };
    },

    // M12 B3 — qarang ../../replica/m12-contract.md §B3
    async firewallState(): Promise<FirewallStateOut> {
      requireManage('*');
      await delay(150);
      return buildFirewallState();
    },

    async validateFirewall(payload: FirewallConfigIn): Promise<FirewallValidateOut> {
      requireManage('*');
      await delay(150);
      checkFirewallPendingExpiry();
      const errors = validateFirewallConfig(payload);
      checkFirewallSelfLockout(payload, typeof window !== 'undefined' ? window.location.hostname : null, errors);
      const diff = buildFirewallDiff(payload, { services: fwServices, blocked_cidrs: fwBlockedCidrs });
      return { ok: errors.length === 0, errors, warnings: [], diff };
    },

    async applyFirewall(payload: FirewallConfigIn): Promise<FirewallStateOut> {
      requireManage('*');
      await delay(250);
      checkFirewallPendingExpiry();
      if (fwPending) err(409, 'pending_exists', 'Boshqa oʻzgarish hali tasdiqlanishini kutmoqda.');
      const errors = validateFirewallConfig(payload);
      checkFirewallSelfLockout(payload, typeof window !== 'undefined' ? window.location.hostname : null, errors);
      if (errors.length > 0) err(422, 'validation_failed', 'Tekshiruvdan oʻtmadi.', { details: { fields: errors } });
      fwPendingSnapshot = { services: fwServices, blockedCidrs: fwBlockedCidrs };
      const summary = buildFirewallDiff(payload, { services: fwServices, blocked_cidrs: fwBlockedCidrs });
      applyFirewallConfigToState(payload);
      const appliedAt = new Date();
      const timeoutS = clamp(payload.timeout_s, 30, 600);
      fwPending = { id: randomId('fwpending'), applied_at: appliedAt.toISOString(), expires_at: new Date(appliedAt.getTime() + timeoutS * 1000).toISOString(), summary };
      fwLastResult = null;
      auditAdd('update', 'firewall', fwPending.id, 'Firewall sozlamalari qoʻllandi', {});
      return buildFirewallState();
    },

    async confirmFirewall(pendingId: string): Promise<FirewallStateOut> {
      requireManage('*');
      await delay(200);
      checkFirewallPendingExpiry();
      if (!fwPending || fwPending.id !== pendingId) err(404, 'not_found', 'Kutilayotgan oʻzgarish topilmadi (muddati oʻtgan boʻlishi mumkin).');
      fwLastResult = { kind: 'confirmed', at: new Date().toISOString(), message: null };
      fwPending = null;
      fwPendingSnapshot = null;
      auditAdd('update', 'firewall', pendingId, 'Firewall sozlamalari tasdiqlandi', {});
      return buildFirewallState();
    },

    async rollbackFirewall(pendingId: string): Promise<FirewallStateOut> {
      requireManage('*');
      await delay(200);
      checkFirewallPendingExpiry();
      if (!fwPending || fwPending.id !== pendingId) err(404, 'not_found', 'Kutilayotgan oʻzgarish topilmadi (muddati oʻtgan boʻlishi mumkin).');
      if (fwPendingSnapshot) {
        fwServices = fwPendingSnapshot.services;
        fwBlockedCidrs = fwPendingSnapshot.blockedCidrs;
      }
      fwLastResult = { kind: 'rolled_back', at: new Date().toISOString(), message: null };
      fwPending = null;
      fwPendingSnapshot = null;
      auditAdd('update', 'firewall', pendingId, 'Firewall sozlamalari qaytarildi', {});
      return buildFirewallState();
    },

    // M11 — qarang ../../replica/m11-update-contract.md
    async systemUpdate(): Promise<SystemUpdateOut> {
      requireManage('*');
      await delay(80);
      if (updateScenario === 'restart_502' && updState === 'updating' && !updRestartFired) {
        updRestartFired = true;
        err(502, 'bad_gateway', 'Tizim qayta ishga tushmoqda.');
      }
      advanceUpdateJob();
      return buildSystemUpdateOut();
    },

    async checkSystemUpdate(): Promise<SystemUpdateOut> {
      requireManage('*');
      await delay(100);
      if (!updAgent) err(503, 'update_agent_missing', "Paneldan yangilash o'rnatilmagan — hostda agent topilmadi.");
      advanceUpdateJob();
      if (updPending || updState === 'checking' || updState === 'updating') err(409, 'update_busy', 'Boshqa yangilanish amali hali ketmoqda.');
      updState = 'checking';
      updPending = 'check';
      updCheckStartedAt = Date.now();
      return buildSystemUpdateOut();
    },

    async startSystemUpdate({ version }: StartSystemUpdatePayload): Promise<SystemUpdateOut> {
      requireManage('*');
      await delay(100);
      if (!updAgent) err(503, 'update_agent_missing', "Paneldan yangilash o'rnatilmagan — hostda agent topilmadi.");
      advanceUpdateJob();
      if (updPending || updState === 'checking' || updState === 'updating') err(409, 'update_busy', 'Boshqa yangilanish amali hali ketmoqda.');
      if (!updAvailable) err(409, 'update_not_available', "Yangi versiya yo'q.");
      if (version !== updLatest) err(409, 'update_version_mismatch', "Versiya mos kelmadi — sahifa eskirgan, qayta tekshiring.");
      updState = 'updating';
      updPhase = 'backup';
      updPending = 'update';
      updStartedAt = new Date().toISOString();
      updFinishedAt = null;
      updError = null;
      updBackup = null;
      updJobStartedAt = Date.now();
      updRestartFired = false;
      auditAdd('update', 'system_update', 'update', `${updCurrent} → ${version}`, {});
      return buildSystemUpdateOut();
    },

    async systemUpdateLog(offset: number): Promise<SystemUpdateLog> {
      requireManage('*');
      await delay(60);
      advanceUpdateJob();
      const text = currentUpdateLogText();
      if (offset > text.length) return { offset: 0, size: 0, text: '' };
      return { offset: text.length, size: text.length, text: text.slice(offset) };
    },

    async listAudit({ entity, user_id, action, from, to, q = '', page = 1, size = 50 }: ListAuditParams): Promise<Paged<AuditEntry>> {
      await delay();
      const needle = q.trim().toLowerCase();
      const fromTs = from ? Date.parse(from) : -Infinity;
      const toTs = to ? Date.parse(to) : Infinity;
      const filtered = auditLog.filter((a) => {
        const ts = Date.parse(a.at);
        if (ts < fromTs || ts > toTs) return false;
        if (entity && a.entity !== entity) return false;
        if (user_id && a.user?.id !== user_id) return false;
        if (action && a.action !== action) return false;
        if (needle && !`${a.label ?? ''} ${a.entity} ${a.user?.login ?? ''}`.toLowerCase().includes(needle)) return false;
        return true;
      });
      const start = (page - 1) * size;
      return { items: filtered.slice(start, start + size), total: filtered.length };
    },

    async revisionDetail(id: string): Promise<RevisionDetail> {
      await delay(150);
      const cur = revisions.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Reviziya topilmadi.');
      return { ...cur, dialplan: revisionDialplans.get(id) ?? '; boʻsh\n' };
    },

    async revisionDiff(id: string, against: RevisionDiffAgainst): Promise<RevisionDiff> {
      await delay(150);
      const idx = revisions.findIndex((r) => r.id === id);
      if (idx < 0) err(404, 'not_found', 'Reviziya topilmadi.');
      const cur = revisions[idx]!;
      const other = against === 'prev' ? revisions[idx + 1] : revisions[0];
      const curText = revisionDialplans.get(cur.id) ?? '';
      const otherText = other ? revisionDialplans.get(other.id) ?? '' : '';
      return { unified: unifiedDiff(otherText, curText, other?.id ?? '∅', cur.id) };
    },

    async restoreRevision(id: string): Promise<RestoreRevisionResult> {
      await delay(400);
      requireManage('system.manage');
      const cur = revisions.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Reviziya topilmadi.');
      if (cur.status !== 'applied') err(409, 'not_applied', 'Faqat muvaffaqiyatli qoʻllangan reviziyani tiklash mumkin.');
      const applied = apply(`Reviziya r${id} holatiga qaytarildi`);
      const item = revisions[0]!;
      auditAdd('restore', 'config_revision', id, `r${id}`, { revision: [revisions[1]?.id ?? null, id] });
      return { item, apply: applied, drift: true };
    },

    async listMohClasses() {
      await delay();
      return { items: mohClasses };
    },

    async createMohClass(payload: CreateMohClassPayload): Promise<Mutated<MohClass>> {
      await delay();
      requireManage('routes.manage');
      const files = resolveMohFiles(payload.file_ids);
      const now = new Date().toISOString();
      const item: MohClass = { id: randomId('moh'), name: payload.name, shuffle: payload.shuffle, files, updated_at: now };
      mohClasses = [...mohClasses, item];
      return { item, apply: apply(`Kutish musiqasi sinfi «${item.name}» qoʻshildi`, payload.name) };
    },

    async updateMohClass(id: string, payload: UpdateMohClassPayload): Promise<Mutated<MohClass>> {
      await delay();
      requireManage('routes.manage');
      const cur = mohClasses.find((m) => m.id === id);
      if (!cur) err(404, 'not_found', 'Kutish musiqasi sinfi topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu sinf boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      const files = payload.file_ids ? resolveMohFiles(payload.file_ids) : cur.files;
      const now = new Date().toISOString();
      const item: MohClass = { ...cur, name: payload.name ?? cur.name, shuffle: payload.shuffle ?? cur.shuffle, files, updated_at: now };
      mohClasses = mohClasses.map((m) => (m.id === id ? item : m));
      return { item, apply: apply(`Kutish musiqasi sinfi «${item.name}» tahrirlandi`, payload.name) };
    },

    async deleteMohClass(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = mohClasses.find((m) => m.id === id);
      if (!cur) err(404, 'not_found', 'Kutish musiqasi sinfi topilmadi.');
      if (cur.name === 'default') err(409, 'in_use', '«default» sinfini oʻchirib boʻlmaydi.', { details: { usages: [{ kind: 'moh_class', id: cur.id, label: cur.name, field: 'name' }] } });
      const usages = queues.filter((q) => q.moh_class?.id === id).map((q) => ({ kind: 'queue', id: q.id, label: q.name, field: 'moh_class_id' }));
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      mohClasses = mohClasses.filter((m) => m.id !== id);
      apply(`Kutish musiqasi sinfi «${cur.name}» oʻchirildi`);
    },

    async updateMe({ language }: UpdateMePayload): Promise<User> {
      await delay(80);
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      currentUser = { ...currentUser, language };
      return currentUser;
    },

    // M1c — ../../replica/m1c-contract.md
    async listVoicemailBoxes({ extension_id }: ListVoicemailBoxesParams): Promise<{ items: VoicemailBox[] }> {
      await delay();
      const items = voicemailBoxes.filter((b) => !extension_id || b.extension?.id === extension_id);
      return { items: items.map(voicemailBoxOut) };
    },

    async createVoicemailBox(payload: CreateVoicemailBoxPayload): Promise<Mutated<VoicemailBox>> {
      await delay();
      requireManageAny(['pbx.manage', 'system.manage']);
      if ((payload.extension_id == null) === (payload.mailbox == null)) {
        err(422, 'owner_required', 'Ichki raqam yoki umumiy quti raqami — aynan bittasi kerak.', { field: 'extension_id' });
      }
      if (!PIN_RE.test(payload.pin)) err(422, 'bad_pin', 'PIN 4–8 ta raqamdan iborat boʻlishi kerak.', { field: 'pin' });
      if (payload.email && !EMAIL_RE.test(payload.email)) err(422, 'bad_email', 'Email manzili notoʻgʻri.', { field: 'email' });
      if (payload.telegram_chat_id && !CHAT_ID_RE.test(payload.telegram_chat_id)) err(422, 'bad_chat_id', 'Telegram chat ID notoʻgʻri.', { field: 'telegram_chat_id' });

      let ext: Extension | null = null;
      let mailbox: string;
      if (payload.extension_id != null) {
        const found = extensions.find((e) => e.id === payload.extension_id);
        if (!found) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'extension_id' });
        ext = found;
        mailbox = found.number;
      } else {
        mailbox = payload.mailbox!;
        if (!MAILBOX_RE.test(mailbox)) err(422, 'bad_mailbox', 'Quti raqami 2–10 ta raqamdan iborat boʻlishi kerak.', { field: 'mailbox' });
        if (extensions.some((e) => e.number === mailbox)) err(409, 'mailbox_taken', 'Bu quti raqami band.', { field: 'mailbox' });
      }
      if (voicemailBoxes.some((b) => b.mailbox === mailbox)) {
        err(409, 'mailbox_taken', 'Bu quti raqami band.', { field: ext ? 'extension_id' : 'mailbox' });
      }
      let greeting: VoicemailBox['greeting'] = null;
      if (payload.greeting_audio_id) {
        const audio = audioList.find((a) => a.id === payload.greeting_audio_id);
        if (!audio) err(404, 'not_found', 'Audio topilmadi.', { field: 'greeting_audio_id' });
        greeting = { id: audio.id, name: audio.name };
      }
      const now = new Date().toISOString();
      const item: VoicemailBox = {
        id: randomId('vm'), mailbox, extension: ext ? { id: ext.id, number: ext.number, name: ext.name } : null,
        email: payload.email ?? null, email_notify: payload.email_notify ?? false,
        telegram_notify: payload.telegram_notify ?? false, telegram_chat_id: payload.telegram_chat_id ?? null,
        attach_audio: payload.attach_audio ?? false, greeting, has_pin: true, counts: { new: 0, old: 0 }, updated_at: now,
      };
      voicemailBoxes = [...voicemailBoxes, item];
      voicemailPins.set(item.id, payload.pin);
      voicemailMessages.set(item.id, []);
      return { item: voicemailBoxOut(item), apply: apply(`Ovozli pochta qutisi ${mailbox} qoʻshildi`, mailbox) };
    },

    async updateVoicemailBox(id: string, payload: UpdateVoicemailBoxPayload): Promise<Mutated<VoicemailBox>> {
      await delay();
      requireManageAny(['pbx.manage', 'system.manage']);
      const cur = voicemailBoxes.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Ovozli pochta qutisi topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu quti boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.pin != null && !PIN_RE.test(payload.pin)) err(422, 'bad_pin', 'PIN 4–8 ta raqamdan iborat boʻlishi kerak.', { field: 'pin' });
      if (payload.email && !EMAIL_RE.test(payload.email)) err(422, 'bad_email', 'Email manzili notoʻgʻri.', { field: 'email' });
      if (payload.telegram_chat_id && !CHAT_ID_RE.test(payload.telegram_chat_id)) err(422, 'bad_chat_id', 'Telegram chat ID notoʻgʻri.', { field: 'telegram_chat_id' });
      let greeting = cur.greeting;
      if (payload.greeting_audio_id !== undefined) {
        if (payload.greeting_audio_id === null) {
          greeting = null;
        } else {
          const audio = audioList.find((a) => a.id === payload.greeting_audio_id);
          if (!audio) err(404, 'not_found', 'Audio topilmadi.', { field: 'greeting_audio_id' });
          greeting = { id: audio.id, name: audio.name };
        }
      }
      const now = new Date().toISOString();
      const item: VoicemailBox = {
        ...cur, email: payload.email !== undefined ? payload.email : cur.email,
        email_notify: payload.email_notify ?? cur.email_notify, telegram_notify: payload.telegram_notify ?? cur.telegram_notify,
        telegram_chat_id: payload.telegram_chat_id !== undefined ? payload.telegram_chat_id : cur.telegram_chat_id,
        attach_audio: payload.attach_audio ?? cur.attach_audio, greeting, updated_at: now,
      };
      voicemailBoxes = voicemailBoxes.map((b) => (b.id === id ? item : b));
      if (payload.pin != null) voicemailPins.set(id, payload.pin);
      return { item: voicemailBoxOut(item), apply: apply(`Ovozli pochta qutisi ${item.mailbox} tahrirlandi`, item.mailbox) };
    },

    async deleteVoicemailBox(id: string) {
      await delay();
      requireManageAny(['pbx.manage', 'system.manage']);
      const cur = voicemailBoxes.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Ovozli pochta qutisi topilmadi.');
      // Frontend'da `voicemail` turidagi call target ishlatilmaydi (TargetKind'da yoʻq) — real `in_use`
      // holati faqat backend'da (IVR/marshrut/navbat `no_answer`) yuzaga kelishi mumkin.
      voicemailBoxes = voicemailBoxes.filter((b) => b.id !== id);
      voicemailPins.delete(id);
      voicemailMessages.delete(id);
      apply(`Ovozli pochta qutisi ${cur.mailbox} oʻchirildi`);
    },

    async listVoicemailMessages(boxId: string): Promise<{ items: VoicemailMessage[] }> {
      await delay();
      if (!voicemailBoxes.some((b) => b.id === boxId)) err(404, 'not_found', 'Ovozli pochta qutisi topilmadi.');
      return { items: voicemailMessages.get(boxId) ?? [] };
    },

    async fetchVoicemailMessageAudio(boxId: string, msg: string): Promise<Blob> {
      await delay(150);
      const message = (voicemailMessages.get(boxId) ?? []).find((m) => m.id === msg);
      if (!message) err(404, 'not_found', 'Xabar topilmadi.');
      return toneWav(message.duration_s * 1000);
    },

    async markVoicemailMessageHeard(boxId: string, msg: string) {
      await delay();
      const list = voicemailMessages.get(boxId) ?? [];
      const message = list.find((m) => m.id === msg);
      if (!message) err(404, 'not_found', 'Xabar topilmadi.');
      if (message.folder === 'inbox') {
        voicemailMessages.set(boxId, list.map((m) => (m.id === msg ? { ...m, folder: 'old' as const, heard: true } : m)));
      }
    },

    async deleteVoicemailMessage(boxId: string, msg: string) {
      await delay();
      const list = voicemailMessages.get(boxId) ?? [];
      if (!list.some((m) => m.id === msg)) err(404, 'not_found', 'Xabar topilmadi.');
      voicemailMessages.set(boxId, list.filter((m) => m.id !== msg));
    },

    async notifySettings(): Promise<NotifySettings> {
      await delay(150);
      return notifySettings;
    },

    async updateNotifySettings(payload: UpdateNotifySettingsPayload): Promise<NotifySettings> {
      await delay();
      requireManage('system.manage');
      if (payload.smtp_port !== undefined && (payload.smtp_port < 1 || payload.smtp_port > 65535)) err(422, 'bad_port', 'Port 1–65535 oraligʻida boʻlishi kerak.', { field: 'smtp_port' });
      if (payload.from_email && !EMAIL_RE.test(payload.from_email)) err(422, 'bad_email', 'Email manzili notoʻgʻri.', { field: 'from_email' });
      if (payload.telegram_api_base && !TELEGRAM_API_RE.test(payload.telegram_api_base)) err(422, 'bad_url', 'Havola notoʻgʻri.', { field: 'telegram_api_base' });
      if (payload.smtp_password !== undefined) { notifySecrets.smtp_password = payload.smtp_password ?? ''; }
      if (payload.telegram_token !== undefined) { notifySecrets.telegram_token = payload.telegram_token || null; }
      const now = new Date().toISOString();
      notifySettings = {
        ...notifySettings,
        smtp_host: payload.smtp_host !== undefined ? payload.smtp_host : notifySettings.smtp_host,
        smtp_port: payload.smtp_port ?? notifySettings.smtp_port,
        smtp_tls: payload.smtp_tls ?? notifySettings.smtp_tls,
        smtp_user: payload.smtp_user !== undefined ? payload.smtp_user : notifySettings.smtp_user,
        has_smtp_password: payload.smtp_password !== undefined ? !!payload.smtp_password : notifySettings.has_smtp_password,
        from_email: payload.from_email !== undefined ? payload.from_email : notifySettings.from_email,
        has_telegram_token: payload.telegram_token !== undefined ? !!payload.telegram_token : notifySettings.has_telegram_token,
        telegram_api_base: payload.telegram_api_base ?? notifySettings.telegram_api_base,
        updated_at: now,
      };
      return notifySettings;
    },

    async testNotify({ channel, to }: NotifyTestPayload): Promise<NotifyTestResult> {
      await delay(400);
      requireManage('system.manage');
      if (to.includes('NOTIFY_XATO')) {
        err(502, 'notify_failed', 'Xabar yetkazilmadi.', { details: { reason: channel === 'email' ? 'smtp_connection_failed' : 'telegram_bad_token' } });
      }
      return { ok: true };
    },

    async sipTls(): Promise<SipTls> {
      await delay(150);
      return sipTls;
    },

    async uploadSipTlsCertificate(cert: File, key: File, _chain?: File): Promise<SipTls> {
      await delay(400);
      requireManage('system.manage');
      if (cert.size === 0 || key.size === 0) err(422, 'bad_certificate', 'Sertifikat fayli notoʻgʻri.', { details: { reason: 'not_pem' } });
      const now = new Date();
      const notAfter = new Date(now);
      notAfter.setDate(notAfter.getDate() + 365);
      sipTls = {
        enabled: true, port: sipSettings.sip_tls_port,
        certificate: { subject: `CN=${cert.name.replace(/\.\w+$/, '')}`, issuer: 'Yuklangan CA', not_after: notAfter.toISOString(), self_signed: false, fingerprint_sha256: randomSecret() },
        restart_required: true,
      };
      return sipTls;
    },

    async createSelfSignedSipTls({ common_name }: SelfSignedTlsPayload): Promise<SipTls> {
      await delay(400);
      requireManage('system.manage');
      if (!common_name.trim()) err(422, 'bad_common_name', 'Umumiy nom (CN) kerak.', { field: 'common_name' });
      const now = new Date();
      const notAfter = new Date(now);
      notAfter.setDate(notAfter.getDate() + 365);
      sipTls = {
        enabled: true, port: sipSettings.sip_tls_port,
        certificate: { subject: `CN=${common_name}`, issuer: `CN=${common_name}`, not_after: notAfter.toISOString(), self_signed: true, fingerprint_sha256: randomSecret() },
        restart_required: true,
      };
      return sipTls;
    },

    // ─────────────────────── M2a — qarang ../../replica/m2a-contract.md ───────────────────────

    async listFeatureCodes(): Promise<{ items: FeatureCode[] }> {
      await delay(120);
      return { items: featureCodes };
    },

    async updateFeatureCode(feature: string, payload: UpdateFeatureCodePayload): Promise<Mutated<FeatureCode>> {
      await delay();
      requireManage('pbx.manage');
      const cur = featureCodes.find((f) => f.feature === feature);
      if (!cur) err(404, 'not_found', 'Xususiyat kodi topilmadi.');
      const nextCode = payload.code !== undefined ? payload.code : cur.code;
      if (!FEATURE_CODE_RE.test(nextCode)) err(422, 'bad_code', 'Kod notoʻgʻri — `*`/raqam/`#` (1-6 belgi).', { field: 'code' });
      checkFeatureCodeTaken(nextCode, feature);
      const nextEnabled = payload.enabled ?? cur.enabled;
      if (nextCode === cur.code && nextEnabled === cur.enabled) {
        return { item: cur, apply: { status: 'unchanged', revision: null, message: null } };
      }
      const item: FeatureCode = { ...cur, code: nextCode, enabled: nextEnabled };
      featureCodes = featureCodes.map((f) => (f.feature === feature ? item : f));
      return { item, apply: apply(`Xususiyat kodi «${feature}» tahrirlandi`, feature) };
    },

    async resetFeatureCode(feature: string): Promise<Mutated<FeatureCode>> {
      await delay();
      requireManage('pbx.manage');
      const cur = featureCodes.find((f) => f.feature === feature);
      if (!cur) err(404, 'not_found', 'Xususiyat kodi topilmadi.');
      const item: FeatureCode = { ...cur, code: cur.default_code, enabled: true };
      featureCodes = featureCodes.map((f) => (f.feature === feature ? item : f));
      return { item, apply: apply(`Xususiyat kodi «${feature}» standart holatga qaytarildi`, feature) };
    },

    async listConferences(): Promise<{ items: Conference[] }> {
      await delay();
      return { items: conferences };
    },

    async createConference(payload: CreateConferencePayload): Promise<Mutated<Conference>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      let number = payload.number?.trim();
      if (number) {
        checkNumberTaken(number);
      } else {
        const taken = new Set(allDialNumbers());
        number = Array.from({ length: 900 }, (_, i) => String(100 + i)).find((n) => !taken.has(n) && !PARK_RESERVED.has(n));
        if (!number) err(409, 'number_taken', 'Boʻsh raqam qolmadi.');
      }
      if (payload.pin != null && !CONFERENCE_PIN_RE.test(payload.pin)) err(422, 'bad_pin', 'PIN 4-8 raqamdan iborat boʻlishi kerak.', { field: 'pin' });
      if (payload.admin_pin != null && !CONFERENCE_PIN_RE.test(payload.admin_pin)) err(422, 'bad_pin', 'Admin PIN 4-8 raqamdan iborat boʻlishi kerak.', { field: 'admin_pin' });
      if (payload.max_members != null && (payload.max_members < 2 || payload.max_members > 100)) err(422, 'bad_max_members', 'Aʼzolar soni 2-100 orasida boʻlishi kerak.', { field: 'max_members' });
      const id = randomId('conf');
      const now = new Date().toISOString();
      if (payload.pin) conferencePins.set(id, payload.pin);
      if (payload.admin_pin) conferenceAdminPins.set(id, payload.admin_pin);
      const item: Conference = {
        id, name, number, has_pin: !!payload.pin, has_admin_pin: !!payload.admin_pin,
        record: payload.record, max_members: payload.max_members, target_id: id, updated_at: now,
        live: { members: 0 },
      };
      conferences = [...conferences, item];
      return { item, apply: apply(`Konferensiya «${name}» qoʻshildi`, name) };
    },

    async updateConference(id: string, payload: UpdateConferencePayload): Promise<Mutated<Conference>> {
      await delay();
      requireManage('pbx.manage');
      const cur = conferences.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'Konferensiya topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const nextNumber = payload.number !== undefined ? payload.number.trim() : cur.number;
      if (nextNumber !== cur.number) checkNumberTaken(nextNumber, id);
      if (payload.pin != null && !CONFERENCE_PIN_RE.test(payload.pin)) err(422, 'bad_pin', 'PIN 4-8 raqamdan iborat boʻlishi kerak.', { field: 'pin' });
      if (payload.admin_pin != null && !CONFERENCE_PIN_RE.test(payload.admin_pin)) err(422, 'bad_pin', 'Admin PIN 4-8 raqamdan iborat boʻlishi kerak.', { field: 'admin_pin' });
      if (payload.max_members !== undefined && payload.max_members != null && (payload.max_members < 2 || payload.max_members > 100)) err(422, 'bad_max_members', 'Aʼzolar soni 2-100 orasida boʻlishi kerak.', { field: 'max_members' });
      if (payload.pin !== undefined) { if (payload.pin) conferencePins.set(id, payload.pin); else conferencePins.delete(id); }
      if (payload.admin_pin !== undefined) { if (payload.admin_pin) conferenceAdminPins.set(id, payload.admin_pin); else conferenceAdminPins.delete(id); }
      const now = new Date().toISOString();
      const item: Conference = {
        ...cur,
        name: payload.name ?? cur.name,
        number: nextNumber,
        has_pin: payload.pin !== undefined ? !!payload.pin : cur.has_pin,
        has_admin_pin: payload.admin_pin !== undefined ? !!payload.admin_pin : cur.has_admin_pin,
        record: payload.record ?? cur.record,
        max_members: payload.max_members !== undefined ? payload.max_members : cur.max_members,
        updated_at: now,
      };
      conferences = conferences.map((c) => (c.id === id ? item : c));
      return { item, apply: apply(`Konferensiya «${item.name}» tahrirlandi`, item.name) };
    },

    async deleteConference(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = conferences.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'Konferensiya topilmadi.');
      const usages = usagesForTargetId(cur.target_id);
      if (usages.length > 0) err(409, 'in_use', `${cur.name} hali ishlatilmoqda.`, { details: { usages } });
      conferences = conferences.filter((c) => c.id !== id);
      conferencePins.delete(id);
      conferenceAdminPins.delete(id);
      apply(`Konferensiya «${cur.name}» oʻchirildi`);
    },

    // ─────────────────────── M9 A1 — E'lonlar (Announcements) ───────────────────────

    async listAnnouncements(): Promise<Paged<Announcement>> {
      await delay();
      return { items: announcements, total: announcements.length };
    },

    async createAnnouncement(payload: CreateAnnouncementPayload): Promise<Mutated<Announcement>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const nextTarget = requireTarget(payload.next_target_id, 'next_target_id');
      const id = randomId('an');
      const now = new Date().toISOString();
      const item: Announcement = {
        id, name, audio_file_id: payload.audio_file_id, audio_name: audioList.find((a) => a.id === payload.audio_file_id)?.name ?? payload.audio_file_id,
        next_target: nextTarget, allow_skip: payload.allow_skip ?? false, repeat_key: payload.repeat_key ?? null,
        answer: payload.answer ?? true, target_id: id, updated_at: now,
      };
      announcements = [...announcements, item];
      return { item, apply: apply(`Eʼlon «${name}» qoʻshildi`, name) };
    },

    async updateAnnouncement(id: string, payload: UpdateAnnouncementPayload): Promise<Mutated<Announcement>> {
      await delay();
      requireManage('pbx.manage');
      const cur = announcements.find((a) => a.id === id);
      if (!cur) err(404, 'not_found', 'Eʼlon topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      let nextTarget = cur.next_target;
      if (payload.next_target_id !== undefined) {
        if (payload.next_target_id === cur.target_id) err(422, 'bad_target', 'Eʼlon oʻz-oʻziga yoʻnaltirilmaydi.', { field: 'next_target_id' });
        nextTarget = requireTarget(payload.next_target_id, 'next_target_id');
      }
      const now = new Date().toISOString();
      const item: Announcement = {
        ...cur, name, next_target: nextTarget,
        audio_file_id: payload.audio_file_id ?? cur.audio_file_id,
        audio_name: payload.audio_file_id !== undefined ? (audioList.find((a) => a.id === payload.audio_file_id)?.name ?? payload.audio_file_id) : cur.audio_name,
        allow_skip: payload.allow_skip ?? cur.allow_skip,
        repeat_key: payload.repeat_key !== undefined ? payload.repeat_key : cur.repeat_key,
        answer: payload.answer ?? cur.answer,
        updated_at: now,
      };
      announcements = announcements.map((a) => (a.id === id ? item : a));
      return { item, apply: apply(`Eʼlon «${item.name}» tahrirlandi`, item.name) };
    },

    async deleteAnnouncement(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = announcements.find((a) => a.id === id);
      if (!cur) err(404, 'not_found', 'Eʼlon topilmadi.');
      const usages = usagesForTargetId(cur.target_id);
      if (usages.length > 0) err(409, 'in_use', `${cur.name} hali ishlatilmoqda.`, { details: { usages } });
      announcements = announcements.filter((a) => a.id !== id);
      apply(`Eʼlon «${cur.name}» oʻchirildi`);
    },

    // ─────────────────────── M9 A2 — Boshqa manzillar / Maxsus kodlar ───────────────────────

    async listMiscDestinations(): Promise<Paged<MiscDestination>> {
      await delay();
      return { items: miscDestinations, total: miscDestinations.length };
    },

    async createMiscDestination(payload: CreateMiscDestinationPayload): Promise<Mutated<MiscDestination>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const dial = payload.dial.trim();
      if (!MISC_DIAL_RE.test(dial)) err(422, 'bad_dial', 'Terish qiymati notoʻgʻri — raqam/`*`/`#`/`+` (1-32 belgi).', { field: 'dial' });
      const id = randomId('md');
      const now = new Date().toISOString();
      const item: MiscDestination = { id, name, dial, target_id: id, updated_at: now };
      miscDestinations = [...miscDestinations, item];
      return { item, apply: apply(`Manzil «${name}» qoʻshildi`, name) };
    },

    async updateMiscDestination(id: string, payload: UpdateMiscDestinationPayload): Promise<Mutated<MiscDestination>> {
      await delay();
      requireManage('pbx.manage');
      const cur = miscDestinations.find((m) => m.id === id);
      if (!cur) err(404, 'not_found', 'Manzil topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const dial = payload.dial !== undefined ? payload.dial.trim() : cur.dial;
      if (!MISC_DIAL_RE.test(dial)) err(422, 'bad_dial', 'Terish qiymati notoʻgʻri — raqam/`*`/`#`/`+` (1-32 belgi).', { field: 'dial' });
      const now = new Date().toISOString();
      const item: MiscDestination = { ...cur, name, dial, updated_at: now };
      miscDestinations = miscDestinations.map((m) => (m.id === id ? item : m));
      return { item, apply: apply(`Manzil «${item.name}» tahrirlandi`, item.name) };
    },

    async deleteMiscDestination(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = miscDestinations.find((m) => m.id === id);
      if (!cur) err(404, 'not_found', 'Manzil topilmadi.');
      const usages = usagesForTargetId(cur.target_id);
      if (usages.length > 0) err(409, 'in_use', `${cur.name} hali ishlatilmoqda.`, { details: { usages } });
      miscDestinations = miscDestinations.filter((m) => m.id !== id);
      apply(`Manzil «${cur.name}» oʻchirildi`);
    },

    async listMiscApplications(): Promise<Paged<MiscApplication>> {
      await delay();
      return { items: miscApplications, total: miscApplications.length };
    },

    async createMiscApplication(payload: CreateMiscApplicationPayload): Promise<Mutated<MiscApplication>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const code = payload.code.trim();
      if (!MISC_CODE_RE.test(code)) err(422, 'bad_code', 'Kod notoʻgʻri — `*`/raqam/`#` (1-7 belgi).', { field: 'code' });
      checkMiscCodeTaken(code);
      const target = requireTarget(payload.target_id, 'target_id');
      const id = randomId('ma');
      const now = new Date().toISOString();
      const item: MiscApplication = { id, name, code, target, enabled: payload.enabled ?? true, updated_at: now };
      miscApplications = [...miscApplications, item];
      return { item, apply: apply(`Maxsus kod «${name}» qoʻshildi`, name) };
    },

    async updateMiscApplication(id: string, payload: UpdateMiscApplicationPayload): Promise<Mutated<MiscApplication>> {
      await delay();
      requireManage('pbx.manage');
      const cur = miscApplications.find((m) => m.id === id);
      if (!cur) err(404, 'not_found', 'Maxsus kod topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const code = payload.code !== undefined ? payload.code.trim() : cur.code;
      if (!MISC_CODE_RE.test(code)) err(422, 'bad_code', 'Kod notoʻgʻri — `*`/raqam/`#` (1-7 belgi).', { field: 'code' });
      if (code !== cur.code) checkMiscCodeTaken(code, id);
      const target = payload.target_id !== undefined ? requireTarget(payload.target_id, 'target_id') : cur.target;
      const now = new Date().toISOString();
      const item: MiscApplication = { ...cur, name, code, target, enabled: payload.enabled ?? cur.enabled, updated_at: now };
      miscApplications = miscApplications.map((m) => (m.id === id ? item : m));
      return { item, apply: apply(`Maxsus kod «${item.name}» tahrirlandi`, item.name) };
    },

    async deleteMiscApplication(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = miscApplications.find((m) => m.id === id);
      if (!cur) err(404, 'not_found', 'Maxsus kod topilmadi.');
      miscApplications = miscApplications.filter((m) => m.id !== id);
      apply(`Maxsus kod «${cur.name}» oʻchirildi`);
    },

    // ─────────────────────── M9 A3 — Parkovka sozlamalari ───────────────────────

    async parkingSettings(): Promise<ParkingSettings> {
      await delay();
      return parkingSettingsCore;
    },

    async updateParkingSettings(payload: UpdateParkingSettingsPayload): Promise<Mutated<ParkingSettings>> {
      await delay();
      requireManage('pbx.manage');
      if (payload.updated_at !== parkingSettingsCore.updated_at) err(409, 'stale', 'Bu sozlama boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: parkingSettingsCore } });
      if (!/^\d{3,4}$/.test(payload.lot_number)) err(422, 'bad_lot', 'Lot raqami notoʻgʻri.', { field: 'lot_number' });
      if (payload.slot_count < 1 || payload.slot_count > 200) err(422, 'bad_slot_count', 'Joylar soni 1-200 orasida boʻlishi kerak.', { field: 'slot_count' });
      if (payload.timeout_s < 10 || payload.timeout_s > 3600) err(422, 'bad_timeout', 'Kutish vaqti 10-3600 soniya orasida boʻlishi kerak.', { field: 'timeout_s' });
      const timeoutTarget = payload.timeout_target_id ? requireTarget(payload.timeout_target_id, 'timeout_target_id') : null;
      const now = new Date().toISOString();
      parkingSettingsCore = {
        lot_number: payload.lot_number, first_slot: payload.first_slot, slot_count: payload.slot_count,
        timeout_s: payload.timeout_s, on_timeout: payload.on_timeout, timeout_target: timeoutTarget,
        moh_class_id: payload.moh_class_id, updated_at: now,
      };
      return { item: parkingSettingsCore, apply: apply('Parkovka sozlamalari saqlandi') };
    },

    async parkedCalls(): Promise<Paged<ParkingCall>> {
      await delay(120);
      return { items: parkingCalls, total: parkingCalls.length };
    },

    // ─────────────────────── M9 A4 — Paging / Intercom ───────────────────────

    async listPageGroups(): Promise<Paged<PageGroup>> {
      await delay();
      return { items: pageGroups, total: pageGroups.length };
    },

    async createPageGroup(payload: CreatePageGroupPayload): Promise<Mutated<PageGroup>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const number = payload.number.trim();
      checkNumberTaken(number);
      if (payload.member_ids.length === 0) err(422, 'bad_members', 'Kamida bitta aʼzo kerak.', { field: 'member_ids' });
      const members = payload.member_ids.map((mid) => {
        const e = extensions.find((x) => x.id === mid);
        if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'member_ids' });
        return { id: e.id, number: e.number, name: e.name };
      });
      const id = randomId('pg');
      const now = new Date().toISOString();
      const item: PageGroup = { id, name, number, duplex: payload.duplex, skip_busy: payload.skip_busy, beep: payload.beep, members, updated_at: now };
      pageGroups = [...pageGroups, item];
      return { item, apply: apply(`Paging guruhi «${name}» qoʻshildi`, name) };
    },

    async updatePageGroup(id: string, payload: UpdatePageGroupPayload): Promise<Mutated<PageGroup>> {
      await delay();
      requireManage('pbx.manage');
      const cur = pageGroups.find((p) => p.id === id);
      if (!cur) err(404, 'not_found', 'Paging guruhi topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const number = payload.number !== undefined ? payload.number.trim() : cur.number;
      if (number !== cur.number) checkNumberTaken(number, id);
      let members = cur.members;
      if (payload.member_ids !== undefined) {
        if (payload.member_ids.length === 0) err(422, 'bad_members', 'Kamida bitta aʼzo kerak.', { field: 'member_ids' });
        members = payload.member_ids.map((mid) => {
          const e = extensions.find((x) => x.id === mid);
          if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'member_ids' });
          return { id: e.id, number: e.number, name: e.name };
        });
      }
      const now = new Date().toISOString();
      const item: PageGroup = {
        ...cur, name, number, duplex: payload.duplex ?? cur.duplex, skip_busy: payload.skip_busy ?? cur.skip_busy,
        beep: payload.beep ?? cur.beep, members, updated_at: now,
      };
      pageGroups = pageGroups.map((p) => (p.id === id ? item : p));
      return { item, apply: apply(`Paging guruhi «${item.name}» tahrirlandi`, item.name) };
    },

    async deletePageGroup(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = pageGroups.find((p) => p.id === id);
      if (!cur) err(404, 'not_found', 'Paging guruhi topilmadi.');
      pageGroups = pageGroups.filter((p) => p.id !== id);
      apply(`Paging guruhi «${cur.name}» oʻchirildi`);
    },

    // ─────────────────────── M9 B1 — PIN toʻplamlari ───────────────────────

    async listPinSets(): Promise<Paged<PinSet>> {
      await delay();
      const items = pinSets.map((p) => ({ ...p, used_by: pinSetUsedBy(p.id) }));
      return { items, total: items.length };
    },

    async createPinSet(payload: CreatePinSetPayload): Promise<Mutated<PinSet>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const id = randomId('ps');
      const now = new Date().toISOString();
      const item: PinSet = { id, name, record_in_cdr: payload.record_in_cdr ?? false, pin_count: 0, used_by: [], updated_at: now };
      pinSets = [...pinSets, item];
      pinSetPins.set(id, []);
      return { item, apply: apply(`PIN toʻplami «${name}» qoʻshildi`, name) };
    },

    async updatePinSet(id: string, payload: UpdatePinSetPayload): Promise<Mutated<PinSet>> {
      await delay();
      requireManage('pbx.manage');
      const cur = pinSets.find((p) => p.id === id);
      if (!cur) err(404, 'not_found', 'PIN toʻplami topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const now = new Date().toISOString();
      const item: PinSet = { ...cur, name, record_in_cdr: payload.record_in_cdr ?? cur.record_in_cdr, updated_at: now };
      pinSets = pinSets.map((p) => (p.id === id ? item : p));
      return { item, apply: apply(`PIN toʻplami «${item.name}» tahrirlandi`, item.name) };
    },

    async deletePinSet(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = pinSets.find((p) => p.id === id);
      if (!cur) err(404, 'not_found', 'PIN toʻplami topilmadi.');
      const usedBy = pinSetUsedBy(id);
      if (usedBy.length > 0) err(409, 'in_use', `${cur.name} hali ishlatilmoqda.`, { details: { usages: usedBy.map((u) => ({ kind: 'outbound_route', id: u.id, label: u.name })) } });
      pinSets = pinSets.filter((p) => p.id !== id);
      pinSetPins.delete(id);
      apply(`PIN toʻplami «${cur.name}» oʻchirildi`);
    },

    async listPinSetPins(id: string): Promise<{ items: PinSetPin[] }> {
      await delay();
      const pins = pinSetPins.get(id);
      if (!pins) err(404, 'not_found', 'PIN toʻplami topilmadi.');
      return { items: pins.map((p) => ({ id: p.id, label: p.label })) };
    },

    async addPinSetPins(id: string, payload: AddPinsPayload): Promise<{ items: PinSetPin[] }> {
      await delay();
      requireManage('pbx.manage');
      const set = pinSets.find((p) => p.id === id);
      const pins = pinSetPins.get(id);
      if (!set || !pins) err(404, 'not_found', 'PIN toʻplami topilmadi.');
      const existing = new Set(pins.map((p) => p.pin));
      const added: { id: string; pin: string; label: string }[] = [];
      for (const row of payload.pins) {
        const pin = row.pin.trim();
        if (!PIN_SET_PIN_RE.test(pin)) err(422, 'bad_pin', `PIN «${pin}» notoʻgʻri — 4-12 ta raqam.`, { field: 'pin' });
        if (existing.has(pin) || added.some((a) => a.pin === pin)) err(409, 'pin_taken', `PIN «${pin}» allaqachon mavjud.`, { field: 'pin' });
        added.push({ id: randomId('pin'), pin, label: row.label.trim() });
      }
      const next = [...pins, ...added];
      pinSetPins.set(id, next);
      pinSets = pinSets.map((p) => (p.id === id ? { ...p, pin_count: next.length } : p));
      apply(`${added.length} ta PIN «${set.name}» toʻplamiga qoʻshildi`, set.name);
      return { items: next.map((p) => ({ id: p.id, label: p.label })) };
    },

    async deletePinSetPin(id: string, pinId: string) {
      await delay();
      requireManage('pbx.manage');
      const pins = pinSetPins.get(id);
      if (!pins) err(404, 'not_found', 'PIN toʻplami topilmadi.');
      const next = pins.filter((p) => p.id !== pinId);
      pinSetPins.set(id, next);
      pinSets = pinSets.map((p) => (p.id === id ? { ...p, pin_count: next.length } : p));
      apply('PIN oʻchirildi');
    },

    // ─────────────────────── M9 B2 — Telefon kitobi + CID Lookup ───────────────────────

    async listPhonebook({ q = '' }: ListPhonebookParams): Promise<Paged<Contact>> {
      await delay();
      const needle = q.trim().toLowerCase();
      const items = contacts.filter((c) => !needle
        || c.name.toLowerCase().includes(needle)
        || (c.company ?? '').toLowerCase().includes(needle)
        || c.numbers.some((n) => n.number.includes(needle)));
      return { items, total: items.length };
    },

    async createContact(payload: CreateContactPayload): Promise<Mutated<Contact>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Ism kerak.', { field: 'name' });
      if (payload.numbers.length === 0) err(422, 'bad_numbers', 'Kamida bitta raqam kerak.', { field: 'numbers' });
      const id = randomId('ct');
      const now = new Date().toISOString();
      const item: Contact = { id, name, company: payload.company ?? null, note: payload.note ?? null, numbers: payload.numbers, updated_at: now };
      contacts = [...contacts, item];
      return { item, apply: apply(`Kontakt «${name}» qoʻshildi`, name) };
    },

    async updateContact(id: string, payload: UpdateContactPayload): Promise<Mutated<Contact>> {
      await delay();
      requireManage('pbx.manage');
      const cur = contacts.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'Kontakt topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Ism kerak.', { field: 'name' });
      const numbers = payload.numbers ?? cur.numbers;
      if (numbers.length === 0) err(422, 'bad_numbers', 'Kamida bitta raqam kerak.', { field: 'numbers' });
      const now = new Date().toISOString();
      const item: Contact = { ...cur, name, company: payload.company !== undefined ? payload.company : cur.company, note: payload.note !== undefined ? payload.note : cur.note, numbers, updated_at: now };
      contacts = contacts.map((c) => (c.id === id ? item : c));
      return { item, apply: apply(`Kontakt «${item.name}» tahrirlandi`, item.name) };
    },

    async deleteContact(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = contacts.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'Kontakt topilmadi.');
      contacts = contacts.filter((c) => c.id !== id);
      apply(`Kontakt «${cur.name}» oʻchirildi`);
    },

    async exportPhonebookCsv(): Promise<Blob> {
      await delay();
      const header = 'name,company,note,numbers\n';
      const rows = contacts.map((c) => [c.name, c.company ?? '', c.note ?? '', c.numbers.map((n) => `${n.number}:${n.label}`).join('|')].map(csvCell).join(','));
      return new Blob([header + rows.join('\n') + '\n'], { type: 'text/csv;charset=utf-8' });
    },

    async importPhonebookCsv(params: ImportPhonebookParams): Promise<ImportPhonebookResult> {
      await delay(200);
      requireManage('pbx.manage');
      const text = await params.file.text();
      const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '');
      const result: ImportPhonebookResult = { created: 0, updated: 0, skipped: 0, errors: [] };
      lines.slice(1).forEach((line, idx) => {
        const row = idx + 2;
        const cells = splitCsvRow(line);
        const [name, company, note, numbersRaw] = cells;
        if (!name?.trim()) { result.errors.push({ row, message: 'Ism kerak.' }); return; }
        const numbers: PhonebookNumber[] = (numbersRaw ?? '').split('|').filter(Boolean).map((part) => {
          const [number, label] = part.split(':');
          return { number: (number ?? '').trim(), label: (label ?? '').trim() };
        });
        if (numbers.length === 0) { result.errors.push({ row, message: 'Kamida bitta raqam kerak.' }); return; }
        const existing = contacts.find((c) => c.name.toLowerCase() === name.trim().toLowerCase());
        if (!params.dry_run) {
          const now = new Date().toISOString();
          if (existing) {
            contacts = contacts.map((c) => (c.id === existing.id ? { ...c, company: company?.trim() || null, note: note?.trim() || null, numbers, updated_at: now } : c));
          } else {
            contacts = [...contacts, { id: randomId('ct'), name: name.trim(), company: company?.trim() || null, note: note?.trim() || null, numbers, updated_at: now }];
          }
        }
        if (existing) result.updated += 1; else result.created += 1;
      });
      if (!params.dry_run && result.created + result.updated > 0) apply(`Telefon kitobi CSV: ${result.created} qoʻshildi, ${result.updated} tahrirlandi`);
      return result;
    },

    async listCidSources(): Promise<Paged<CidSource>> {
      await delay();
      const items = cidSources.map((c) => ({ ...c, used_by: cidSourceUsedBy(c.id) }));
      return { items, total: items.length };
    },

    async createCidSource(payload: CreateCidSourcePayload): Promise<Mutated<CidSource>> {
      await delay();
      requireManage('pbx.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      if (payload.kind === 'http' && !payload.http_url) err(422, 'bad_url', 'HTTP URL kerak.', { field: 'http_url' });
      const id = randomId('cs');
      const now = new Date().toISOString();
      const item: CidSource = {
        id, name, kind: payload.kind, http_url: payload.http_url ?? null, http_json_path: payload.http_json_path ?? null,
        timeout_ms: payload.timeout_ms ?? 1500, cache_ttl_s: payload.cache_ttl_s ?? 3600, enabled: payload.enabled ?? true,
        used_by: [], updated_at: now,
      };
      cidSources = [...cidSources, item];
      return { item, apply: apply(`CID manbasi «${name}» qoʻshildi`, name) };
    },

    async updateCidSource(id: string, payload: UpdateCidSourcePayload): Promise<Mutated<CidSource>> {
      await delay();
      requireManage('pbx.manage');
      const cur = cidSources.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'CID manbasi topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const kind = payload.kind ?? cur.kind;
      const httpUrl = payload.http_url !== undefined ? payload.http_url : cur.http_url;
      if (kind === 'http' && !httpUrl) err(422, 'bad_url', 'HTTP URL kerak.', { field: 'http_url' });
      const now = new Date().toISOString();
      const item: CidSource = {
        ...cur, name, kind, http_url: httpUrl,
        http_json_path: payload.http_json_path !== undefined ? payload.http_json_path : cur.http_json_path,
        timeout_ms: payload.timeout_ms ?? cur.timeout_ms, cache_ttl_s: payload.cache_ttl_s ?? cur.cache_ttl_s,
        enabled: payload.enabled ?? cur.enabled, updated_at: now,
      };
      cidSources = cidSources.map((c) => (c.id === id ? item : c));
      return { item, apply: apply(`CID manbasi «${item.name}» tahrirlandi`, item.name) };
    },

    async deleteCidSource(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = cidSources.find((c) => c.id === id);
      if (!cur) err(404, 'not_found', 'CID manbasi topilmadi.');
      const usedBy = cidSourceUsedBy(id);
      if (usedBy.length > 0) err(409, 'in_use', `${cur.name} hali ishlatilmoqda.`, { details: { usages: usedBy.map((u) => ({ kind: 'inbound_route', id: u.id, label: u.name })) } });
      cidSources = cidSources.filter((c) => c.id !== id);
      apply(`CID manbasi «${cur.name}» oʻchirildi`);
    },

    async testCidSource(id: string, number: string): Promise<CidSourceTestResult> {
      await delay(400);
      const source = cidSources.find((c) => c.id === id);
      if (!source) err(404, 'not_found', 'CID manbasi topilmadi.');
      if (!FORWARD_NUMBER_RE.test(number)) err(422, 'bad_number', 'Raqam notoʻgʻri.', { field: 'number' });
      const started = Date.now();
      if (source.kind === 'phonebook') {
        const contact = contacts.find((c) => c.numbers.some((n) => n.number === number));
        return { name: contact?.name ?? null, ms: Date.now() - started + 8, error: contact ? null : 'Topilmadi' };
      }
      return { name: null, ms: source.timeout_ms, error: 'Bu demo muhitda tashqi manba chaqirilmaydi.' };
    },

    // ─────────────────────── M9 B4 — Ichki raqamlar CSV import/eksport ───────────────────────

    async exportExtensionsCsv(): Promise<Blob> {
      await delay();
      const header = EXTENSIONS_CSV_COLUMNS.join(',') + '\n';
      const rows = extensions.map((e) => EXTENSIONS_CSV_COLUMNS.map((col) => {
        const raw = col === 'voicemail' ? (voicemailBoxes.some((v) => v.extension?.id === e.id) ? 'yes' : 'no') : (col === 'email' || col === 'language' || col === 'max_contacts' ? '' : (e as unknown as Record<string, unknown>)[col]);
        return csvCell(String(raw ?? ''));
      }).join(','));
      return new Blob([header + rows.join('\n') + '\n'], { type: 'text/csv;charset=utf-8' });
    },

    async importExtensionsCsv(params: ImportExtensionsParams): Promise<ImportExtensionsResult> {
      await delay(250);
      requireManage('pbx.manage');
      const text = await params.file.text();
      if (text.length > 1_000_000) err(413, 'too_large', 'Fayl 1 MBdan katta.');
      const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '');
      if (lines.length - 1 > 2000) err(422, 'too_many_rows', 'Fayl 2000 qatordan koʻp.');
      const recPolicy = (v: string | undefined, fallback: RecordingPolicy): RecordingPolicy => (
        v === 'always' || v === 'never' || v === 'on_demand' ? v : fallback
      );
      type PlannedRow = { row: number; number: string; action: ExtensionImportRowAction; message: string | null; existing: Extension | null; name: string; outboundCid: string | null; recordIn: string | undefined; recordOut: string | undefined; callWaiting: boolean; enabled: boolean };
      const seenNumbers = new Set<string>();
      const planned: PlannedRow[] = lines.slice(1).map((line, idx) => {
        const row = idx + 2;
        const cells = splitCsvRow(line);
        // Ustunlar (§B4): number,name,email,outbound_cid,language,voicemail,record_in,record_out,max_contacts,call_waiting,enabled.
        // email/language/max_contacts/voicemail — bu frontend-mock'da saqlanmaydi (Extension modelida yo'q); backend bo'lak B o'z CRUD'ida ishlatadi.
        const [numberRaw, nameRaw, , outboundCid, , , recordIn, recordOut, , callWaiting, enabled] = cells;
        const number = (numberRaw ?? '').trim();
        const name = (nameRaw ?? '').trim();
        const base = { row, number, name, outboundCid: outboundCid?.trim() || null, recordIn, recordOut, callWaiting: callWaiting?.trim() === 'yes' || callWaiting?.trim() === 'true', enabled: enabled?.trim() !== 'no' && enabled?.trim() !== 'false', existing: null };
        if (!number || !EXT_NUMBER_RE.test(number)) return { ...base, action: 'error' as const, message: 'Raqam notoʻgʻri.' };
        if (!name) return { ...base, action: 'error' as const, message: 'Ism kerak.' };
        if (seenNumbers.has(number)) return { ...base, action: 'error' as const, message: 'Faylda shu raqam takrorlanmoqda.' };
        seenNumbers.add(number);
        const existing = extensions.find((e) => e.number === number) ?? null;
        return { ...base, existing, action: existing ? 'update' as const : 'create' as const, message: null };
      });
      const errors = planned.filter((p) => p.action === 'error').length;
      const created = planned.filter((p) => p.action === 'create').length;
      const updated = planned.filter((p) => p.action === 'update').length;
      const passwordLines: string[] = ['number,password'];
      if (!params.dry_run && errors === 0) {
        const now = new Date().toISOString();
        for (const p of planned) {
          if (p.action === 'update' && p.existing) {
            const item: Extension = {
              ...p.existing, name: p.name, outbound_callerid: p.outboundCid, call_waiting: p.callWaiting, enabled: p.enabled,
              recording_in: recPolicy(p.recordIn, p.existing.recording_in), recording_out: recPolicy(p.recordOut, p.existing.recording_out),
              updated_at: now,
            };
            extensions = extensions.map((e) => (e.id === p.existing!.id ? item : e));
          } else if (p.action === 'create') {
            const password = generateSipPassword(p.number);
            const recIn = recPolicy(p.recordIn, 'never');
            const item: Extension = {
              id: randomId('e'), number: p.number, name: p.name, enabled: p.enabled, status: 'unknown',
              contact: null, user_agent: null, dnd: false, forward_always: null, forward_busy: null, pickup_group: null,
              outbound_allowed: true, outbound_callerid: p.outboundCid, updated_at: now,
              toll_blocked_at: null, toll_block_reason: null, webrtc: false, codecs: [],
              recording: recIn, recording_in: recIn, recording_out: recPolicy(p.recordOut, 'never'), call_waiting: p.callWaiting,
            };
            extensions = [...extensions, item];
            passwordLines.push(`${item.number},${password}`);
          }
        }
        if (created + updated > 0) apply(`Ichki raqamlar CSV: ${created} qoʻshildi, ${updated} tahrirlandi`);
      }
      const rows = planned.map((p) => ({ row: p.row, number: p.number, action: p.action, message: p.message }));
      const secretsCsv = !params.dry_run && errors === 0 && passwordLines.length > 1 ? passwordLines.join('\n') + '\n' : null;
      return { rows, created, updated, errors, secrets_csv: secretsCsv };
    },

    async listBlacklist({ q = '' }: ListBlacklistParams): Promise<{ items: BlacklistEntry[] }> {
      await delay();
      const needle = q.trim().toLowerCase();
      const items = blacklist.filter((b) => !needle || b.number.includes(needle) || (b.reason ?? '').toLowerCase().includes(needle));
      return { items };
    },

    async createBlacklistEntry(payload: CreateBlacklistPayload): Promise<{ item: BlacklistEntry }> {
      await delay();
      requireManage('pbx.manage');
      const number = normalizeBlacklistNumber(payload.number);
      if (number !== 'anonymous' && !BLACKLIST_NUMBER_RE.test(number)) err(422, 'bad_number', 'Raqam notoʻgʻri — 3-15 ta raqam.', { field: 'number' });
      if (blacklist.some((b) => b.number === number)) err(409, 'exists', `${number} allaqachon qora roʻyxatda.`, { field: 'number' });
      const item: BlacklistEntry = { number, reason: payload.reason?.trim() || null, created_at: new Date().toISOString() };
      blacklist = [item, ...blacklist];
      auditAdd('create', 'blacklist', number, number, { number: [null, number] });
      return { item };
    },

    async deleteBlacklistEntry(number: string) {
      await delay();
      requireManage('pbx.manage');
      const normalized = normalizeBlacklistNumber(number);
      const cur = blacklist.find((b) => b.number === normalized);
      if (!cur) err(404, 'not_found', 'Qora roʻyxatda topilmadi.');
      blacklist = blacklist.filter((b) => b.number !== normalized);
      auditAdd('delete', 'blacklist', normalized, normalized, { number: [normalized, null] });
    },

    // ─────────────────────── M2b §2 — jonli monitoring (S29) ───────────────────────

    async live(): Promise<LiveSnapshot> {
      await delay(80);
      requireManage('pbx.manage');
      return {
        at: new Date().toISOString(),
        calls: liveCalls,
        queues: queues.map((q) => ({
          id: q.id, name: q.name, number: q.number,
          waiting: liveCalls
            .filter((c) => c.queue_id === q.id && c.state === 'queued')
            .map((c, i) => ({ from: c.from, since: c.started_at, position: i + 1 })),
          agents: q.members.map((m) => {
            const ext = extensions.find((e) => e.id === m.extension.id);
            return {
              extension: m.extension.number, name: m.extension.name, dynamic: m.dynamic, logged_in: m.logged_in,
              paused: m.paused, pause_reason: m.pause_reason, state: agentStateFor(m, ext),
              answered_today: calls.filter((c) => c.disposition === 'answered' && callAgentNumber(c) === m.extension.number).length,
            };
          }),
        })),
        extensions: extensions.map((e) => ({ number: e.number, name: e.name, state: extensionStateFor(e), dnd: e.dnd })),
      };
    },

    async liveSpy(payload: LiveSpyPayload): Promise<LiveSpyResult> {
      await delay();
      requireManage('pbx.manage');
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      const mu = requireManagedUser(currentUser.id);
      if (!mu.extension) err(409, 'no_extension', 'Tinglash uchun profilingizga ichki raqam bogʻlanishi kerak.');
      const call = payload.call_id
        ? liveCalls.find((c) => c.id === payload.call_id)
        : liveCalls.find((c) => c.channels.includes(payload.channel ?? ''));
      if (!call) err(404, 'not_found', 'Qoʻngʻiroq topilmadi — balki tugagan.');
      auditAdd('spy', 'live_call', call.id, call.id, { mode: [null, payload.mode] });
      return { status: 'calling' };
    },

    // ─────────────────────── M2b §3 — foydalanuvchilar (S31) ───────────────────────

    async listUsers(): Promise<{ items: ManagedUser[] }> {
      await delay();
      requireManage('system.manage');
      return { items: users };
    },

    async createUser(payload: CreateUserPayload): Promise<{ item: ManagedUser }> {
      await delay();
      requireManage('system.manage');
      const username = payload.username.trim();
      if (!username) err(422, 'bad_username', 'Login kiritilishi shart.', { field: 'username' });
      if (users.some((u) => u.username === username)) err(409, 'username_taken', `«${username}» login band.`, { field: 'username' });
      if (payload.password.length < 10) err(422, 'weak_password', 'Parol kamida 10 belgidan iborat boʻlishi kerak.', { field: 'password' });
      if (!roles.some((r) => r.name === payload.role)) err(422, 'validation_error', 'Bunday rol topilmadi.', { field: 'role' });
      let extRef: ManagedUser['extension'] = null;
      if (payload.extension_id) {
        const e = extensions.find((x) => x.id === payload.extension_id);
        if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'extension_id' });
        const other = users.find((u) => u.extension?.id === e.id);
        if (other) err(409, 'extension_taken', `${e.number} allaqachon «${other.username}»ga bogʻlangan.`, { field: 'extension_id', details: { username: other.username } });
        extRef = { id: e.id, number: e.number, name: e.name };
      }
      const now = new Date().toISOString();
      const item: ManagedUser = {
        id: randomId('u'), username, full_name: payload.full_name.trim(), email: payload.email?.trim() || null,
        role: payload.role, extension: extRef, is_active: true, language: payload.language ?? 'uz',
        must_change_password: true, totp_enabled: false, last_login_at: null, updated_at: now,
      };
      users = [...users, item];
      userPasswords.set(item.id, payload.password);
      auditAdd('create', 'user', item.id, item.username, { username: [null, item.username] });
      return { item };
    },

    async updateUser(id: string, payload: UpdateUserPayload): Promise<{ item: ManagedUser }> {
      await delay();
      requireManage('system.manage');
      const mu = requireManagedUser(id);
      if (payload.updated_at !== mu.updated_at) err(409, 'stale', 'Bu foydalanuvchi boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      const nextIsActive = payload.is_active ?? mu.is_active;
      const nextRole = payload.role ?? mu.role;
      if (payload.role !== undefined && !roles.some((r) => r.name === payload.role)) {
        err(422, 'validation_error', 'Bunday rol topilmadi.', { field: 'role' });
      }
      checkSelfLockout(id, nextIsActive, nextRole);
      checkLastAdmin(id, nextIsActive, nextRole);
      if (payload.password !== undefined && payload.password.length < 10) err(422, 'weak_password', 'Parol kamida 10 belgidan iborat boʻlishi kerak.', { field: 'password' });
      let extRef = mu.extension;
      if (payload.extension_id !== undefined) {
        if (payload.extension_id === null) {
          extRef = null;
        } else {
          const e = extensions.find((x) => x.id === payload.extension_id);
          if (!e) err(404, 'not_found', 'Ichki raqam topilmadi.', { field: 'extension_id' });
          const other = users.find((u) => u.id !== id && u.extension?.id === e.id);
          if (other) err(409, 'extension_taken', `${e.number} allaqachon «${other.username}»ga bogʻlangan.`, { field: 'extension_id', details: { username: other.username } });
          extRef = { id: e.id, number: e.number, name: e.name };
        }
      }
      const now = new Date().toISOString();
      const item: ManagedUser = {
        ...mu, full_name: payload.full_name ?? mu.full_name, email: payload.email !== undefined ? payload.email : mu.email,
        role: nextRole, extension: extRef, is_active: nextIsActive, updated_at: now,
      };
      users = users.map((u) => (u.id === id ? item : u));
      if (payload.password !== undefined) userPasswords.set(id, payload.password);
      if (currentUser && currentUser.id === id) currentUser = toSessionUser(item);
      auditAdd('update', 'user', id, item.username, { role: [mu.role, item.role] });
      return { item };
    },

    async deleteUser(id: string) {
      await delay();
      requireManage('system.manage');
      const mu = requireManagedUser(id);
      checkSelfLockout(id, false, mu.role);
      checkLastAdmin(id, false, mu.role);
      users = users.filter((u) => u.id !== id);
      userPasswords.delete(id);
      auditAdd('delete', 'user', id, mu.username, { username: [mu.username, null] });
    },

    async changePassword(payload: ChangePasswordPayload) {
      await delay();
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      if (userPasswords.get(currentUser.id) !== payload.current) err(401, 'bad_credentials', 'Joriy parol notoʻgʻri.', { field: 'current' });
      if (payload.new.length < 10) err(422, 'weak_password', 'Parol kamida 10 belgidan iborat boʻlishi kerak.', { field: 'new' });
      userPasswords.set(currentUser.id, payload.new);
      const now = new Date().toISOString();
      users = users.map((u) => (u.id === currentUser!.id ? { ...u, must_change_password: false, updated_at: now } : u));
      currentUser = { ...currentUser, must_change_password: false };
      auditAdd('update', 'user', currentUser.id, currentUser.login, { password: ['***', '***'] });
      return issueTokens(currentUser);
    },

    // ─────────────────────── M7 §2 — rollar (qarang ../../replica/m7-roles-contract.md) ───────────────────────

    async listRoles(): Promise<{ items: RoleOut[] }> {
      await delay();
      requireManage('system.manage');
      return { items: sortedRoles().map(roleToOut) };
    },

    async createRole(payload: CreateRolePayload): Promise<{ item: RoleOut }> {
      await delay();
      requireManage('system.manage');
      const name = validateRoleName(payload.name);
      const permissions = normalizeRolePermissions(payload.permissions);
      const now = new Date().toISOString();
      const item: FakeRoleSeed = { id: randomId('role'), name, permissions, is_system: false, updated_at: now };
      roles = [...roles, item];
      auditAdd('create', 'role', item.id, item.name, { name: [null, item.name] });
      return { item: roleToOut(item) };
    },

    async updateRole(id: string, payload: UpdateRolePayload): Promise<{ item: RoleOut }> {
      await delay();
      requireManage('system.manage');
      const cur = roles.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Rol topilmadi.');
      if (cur.is_system) err(409, 'system_role', 'Tizim roli oʻzgartirilmaydi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu rol boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      const name = payload.name !== undefined ? validateRoleName(payload.name, id) : cur.name;
      const permissions = payload.permissions !== undefined ? normalizeRolePermissions(payload.permissions) : cur.permissions;
      const now = new Date().toISOString();
      const item: FakeRoleSeed = { ...cur, name, permissions, updated_at: now };
      roles = roles.map((r) => (r.id === id ? item : r));
      if (name !== cur.name) users = users.map((u) => (u.role === cur.name ? { ...u, role: name, updated_at: now } : u));
      if (currentUser && currentUser.role === cur.name) currentUser = { ...currentUser, role: name, permissions: permissionsForRole(name) };
      auditAdd('update', 'role', id, item.name, { name: [cur.name, item.name] });
      return { item: roleToOut(item) };
    },

    async deleteRole(id: string) {
      await delay();
      requireManage('system.manage');
      const cur = roles.find((r) => r.id === id);
      if (!cur) err(404, 'not_found', 'Rol topilmadi.');
      if (cur.is_system) err(409, 'system_role', 'Tizim rolini oʻchirib boʻlmaydi.');
      const userCount = users.filter((u) => u.role === cur.name).length;
      if (userCount > 0) {
        err(409, 'role_in_use', 'Bu rolga foydalanuvchilar bogʻlangan — avval ularni boshqa rolga oʻtkazing.', { details: { user_count: userCount } });
      }
      roles = roles.filter((r) => r.id !== id);
      auditAdd('delete', 'role', id, cur.name, { name: [cur.name, null] });
    },

    // ─────────────────────── M2b §4 — mening kabinetim (S30) ───────────────────────

    async meOverview(): Promise<MeOverview> {
      await delay();
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      const mu = requireManagedUser(currentUser.id);
      const ext = mu.extension ? extensions.find((e) => e.id === mu.extension!.id) : undefined;
      const extensionOverview = ext ? {
        id: ext.id, number: ext.number, name: ext.name, dnd: ext.dnd, forward_always: ext.forward_always, forward_busy: ext.forward_busy,
        outbound_allowed: extensionOutboundAllowed(ext.id), voicemail_box_id: voicemailBoxes.find((b) => b.extension?.id === ext.id)?.id ?? null,
        updated_at: ext.updated_at,
      } : null;
      const queueOverviews = ext
        ? queues.filter((q) => q.members.some((m) => m.extension.id === ext.id)).map((q) => {
            const m = q.members.find((mm) => mm.extension.id === ext.id)!;
            return { id: q.id, name: q.name, number: q.number, dynamic: m.dynamic, logged_in: m.logged_in, paused: m.paused, pause_reason: m.pause_reason };
          })
        : [];
      // Demo maʼlumoti tarixiy sanaga bogʻlangani uchun "bugungi" statistika — shu ichki raqamning barcha qoʻngʻiroqlari (soddalashtirish).
      const own = ext ? calls.filter((c) => c.src === ext.number || c.dst === ext.number) : [];
      const today = {
        answered: own.filter((c) => c.disposition === 'answered').length,
        missed: own.filter((c) => c.disposition === 'no_answer').length,
        talk_seconds: own.reduce((s, c) => s + c.billsec, 0),
      };
      return { user: mu, extension: extensionOverview, queues: queueOverviews, today };
    },

    async patchMeExtension(payload: PatchMeExtensionPayload): Promise<{ item: MeOverview['extension'] }> {
      await delay();
      const ext = requireOwnExtension();
      if (payload.updated_at !== ext.updated_at) err(409, 'stale', 'Ichki raqam boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      const forwardAlways = clearsEmpty(payload.forward_always);
      const forwardBusy = clearsEmpty(payload.forward_busy);
      if (forwardAlways != null && !FORWARD_NUMBER_RE.test(forwardAlways)) err(422, 'bad_number', 'Raqam notoʻgʻri — faqat raqamlar (2-15 ta).', { field: 'forward_always' });
      if (forwardBusy != null && !FORWARD_NUMBER_RE.test(forwardBusy)) err(422, 'bad_number', 'Raqam notoʻgʻri — faqat raqamlar (2-15 ta).', { field: 'forward_busy' });
      const now = new Date().toISOString();
      const item: Extension = {
        ...ext,
        dnd: payload.dnd ?? ext.dnd,
        forward_always: payload.forward_always !== undefined ? (forwardAlways as string | null) : ext.forward_always,
        forward_busy: payload.forward_busy !== undefined ? (forwardBusy as string | null) : ext.forward_busy,
        updated_at: now,
      };
      extensions = extensions.map((e) => (e.id === item.id ? item : e));
      auditAdd('update', 'extension', item.id, item.number, { dnd: [ext.dnd, item.dnd] });
      return {
        item: {
          id: item.id, number: item.number, name: item.name, dnd: item.dnd, forward_always: item.forward_always, forward_busy: item.forward_busy,
          outbound_allowed: extensionOutboundAllowed(item.id), voicemail_box_id: voicemailBoxes.find((b) => b.extension?.id === item.id)?.id ?? null,
          updated_at: item.updated_at,
        },
      };
    },

    // M3a §2 — qarang ../../replica/m3a-contract.md §2. Har chaqiruv yangi ticket (demo: TTL 10 daqiqa).
    async meSoftphone(): Promise<SoftphoneInfo> {
      await delay();
      const ext = requireSoftphoneExtension();
      return {
        number: ext.number,
        display_name: ext.name,
        ws_path: '/sip-ws',
        ticket: randomSecret(),
        ticket_expires_at: new Date(Date.now() + 600_000).toISOString(),
        sip: { uri: `sip:t1-${ext.number}@innova`, auth_user: `t1-${ext.number}`, password: randomSecret(), realm: 'asterisk' },
        ice_servers: [],
      };
    },

    async meSoftphoneStatus(): Promise<void> {
      await delay();
      requireSoftphoneExtension();
    },

    async meQueueAction(queueId: string, action: QueueMemberAction, payload?: QueueMemberActionPayload): Promise<{ item: MeOverview['queues'][number] }> {
      await delay();
      const ext = requireOwnExtension();
      const q = queues.find((x) => x.id === queueId);
      if (!q) err(404, 'not_found', 'Navbat topilmadi.');
      const members = applyQueueMemberAction(q, ext.id, action, payload?.reason);
      const item: Queue = { ...q, members, updated_at: new Date().toISOString() };
      queues = queues.map((x) => (x.id === queueId ? item : x));
      const m = item.members.find((mm) => mm.extension.id === ext.id)!;
      return { item: { id: item.id, name: item.name, number: item.number, dynamic: m.dynamic, logged_in: m.logged_in, paused: m.paused, pause_reason: m.pause_reason } };
    },

    async meCalls(params: ListCallsParams): Promise<Paged<Call>> {
      await delay();
      const ext = requireOwnExtension();
      const { from, to, q = '', direction, page = 1, size = 50 } = params;
      const needle = q.trim().toLowerCase();
      const fromTs = from ? Date.parse(from) : -Infinity;
      const toTs = to ? Date.parse(to) : Infinity;
      const filtered = calls.filter((c) => {
        if (c.src !== ext.number && c.dst !== ext.number) return false;
        const ts = Date.parse(c.started_at);
        if (ts < fromTs || ts > toTs) return false;
        if (direction && c.direction !== direction) return false;
        if (needle && !`${c.src} ${c.dst} ${c.did ?? ''}`.toLowerCase().includes(needle)) return false;
        return true;
      });
      const start = (page - 1) * size;
      return { items: filtered.slice(start, start + size), total: filtered.length };
    },

    async meVoicemailMessages(): Promise<{ items: VoicemailMessage[] }> {
      await delay();
      const box = requireOwnVoicemailBox();
      return { items: voicemailMessages.get(box.id) ?? [] };
    },

    async meVoicemailAudio(msg: string): Promise<Blob> {
      await delay(150);
      const box = requireOwnVoicemailBox();
      const message = (voicemailMessages.get(box.id) ?? []).find((m) => m.id === msg);
      if (!message) err(404, 'not_found', 'Xabar topilmadi.');
      return toneWav(message.duration_s * 1000);
    },

    async meVoicemailHeard(msg: string) {
      await delay();
      const box = requireOwnVoicemailBox();
      const list = voicemailMessages.get(box.id) ?? [];
      const message = list.find((m) => m.id === msg);
      if (!message) err(404, 'not_found', 'Xabar topilmadi.');
      if (message.folder === 'inbox') {
        voicemailMessages.set(box.id, list.map((m) => (m.id === msg ? { ...m, folder: 'old' as const, heard: true } : m)));
      }
    },

    async meVoicemailDelete(msg: string) {
      await delay();
      const box = requireOwnVoicemailBox();
      const list = voicemailMessages.get(box.id) ?? [];
      if (!list.some((m) => m.id === msg)) err(404, 'not_found', 'Xabar topilmadi.');
      voicemailMessages.set(box.id, list.filter((m) => m.id !== msg));
    },

    // ─────────────────────── M2b §5 — analitika (S13) ───────────────────────

    async reportsSummary(params: ReportRangeParams): Promise<ReportsSummary> {
      await delay(150);
      requireManage('pbx.manage');
      validateReportRange(params);
      const list = callsInRange(params).filter((c) => !params.queue_id || assignedQueueId(c) === params.queue_id);
      const answeredList = list.filter((c) => c.disposition === 'answered');
      const total = list.length;
      const hourCounts = new Map<number, number>();
      list.forEach((c) => { const h = new Date(c.started_at).getUTCHours(); hourCounts.set(h, (hourCounts.get(h) ?? 0) + 1); });
      let busiest_hour: number | null = null;
      let max = -1;
      hourCounts.forEach((v, h) => { if (v > max) { max = v; busiest_hour = h; } });
      return {
        from: params.from, to: params.to, timezone: TZ,
        total, inbound: list.filter((c) => c.direction === 'in').length, outbound: list.filter((c) => c.direction === 'out').length,
        internal: list.filter((c) => c.direction === 'internal').length, answered: answeredList.length,
        missed: list.filter((c) => c.disposition === 'no_answer').length,
        blocked: list.filter((c) => c.disposition === 'busy' || c.disposition === 'failed').length,
        avg_wait_seconds: answeredList.length ? Math.round(answeredList.reduce((s, c) => s + Math.max(0, c.duration - c.billsec), 0) / answeredList.length) : null,
        avg_talk_seconds: answeredList.length ? Math.round(answeredList.reduce((s, c) => s + c.billsec, 0) / answeredList.length) : null,
        sla_percent: total ? Math.round((answeredList.length / total) * 1000) / 10 : null,
        busiest_hour,
      };
    },

    async reportsQueues(params: ReportRangeParams): Promise<{ items: ReportsQueueRow[] }> {
      await delay(150);
      requireManage('pbx.manage');
      validateReportRange(params);
      const list = callsInRange(params);
      const items = queues.filter((q) => !params.queue_id || q.id === params.queue_id).map((q) => {
        const qCalls = list.filter((c) => assignedQueueId(c) === q.id);
        const answeredList = qCalls.filter((c) => c.disposition === 'answered');
        const entered = qCalls.length;
        return {
          queue_id: q.id, name: q.name, entered, answered: answeredList.length,
          abandoned: qCalls.filter((c) => c.disposition === 'no_answer').length,
          timeout: qCalls.filter((c) => c.disposition === 'busy' || c.disposition === 'failed').length,
          avg_wait_seconds: answeredList.length ? Math.round(answeredList.reduce((s, c) => s + Math.max(0, c.duration - c.billsec), 0) / answeredList.length) : null,
          max_wait_seconds: answeredList.length ? Math.max(...answeredList.map((c) => Math.max(0, c.duration - c.billsec))) : null,
          sla_percent: entered ? Math.round((answeredList.length / entered) * 1000) / 10 : null,
        };
      });
      return { items };
    },

    async reportsAgents(params: ReportRangeParams): Promise<{ items: ReportsAgentRow[] }> {
      await delay(150);
      requireManage('pbx.manage');
      validateReportRange(params);
      const list = callsInRange(params).filter((c) => !params.queue_id || assignedQueueId(c) === params.queue_id);
      const items = extensions.map((e) => {
        const own = list.filter((c) => callAgentNumber(c) === e.number);
        const answeredList = own.filter((c) => c.disposition === 'answered');
        const talk_seconds = answeredList.reduce((s, c) => s + c.billsec, 0);
        return {
          extension: e.number, name: e.name,
          answered: answeredList.length,
          missed_ring: own.filter((c) => c.disposition === 'no_answer').length,
          talk_seconds, avg_talk_seconds: answeredList.length ? Math.round(talk_seconds / answeredList.length) : null,
          login_seconds: Math.max(talk_seconds, own.length * 30), pause_seconds: 0,
        };
      });
      return { items };
    },

    async reportsHourly(params: ReportRangeParams): Promise<{ items: ReportsHourlyRow[] }> {
      await delay(150);
      requireManage('pbx.manage');
      validateReportRange(params);
      const list = callsInRange(params).filter((c) => !params.queue_id || assignedQueueId(c) === params.queue_id);
      const buckets: ReportsHourlyRow[] = Array.from({ length: 24 }, (_, hour) => ({ hour, inbound: 0, answered: 0, missed: 0 }));
      list.forEach((c) => {
        const bucket = buckets[new Date(c.started_at).getUTCHours()]!;
        if (c.direction === 'in') bucket.inbound += 1;
        if (c.disposition === 'answered') bucket.answered += 1;
        if (c.disposition === 'no_answer') bucket.missed += 1;
      });
      return { items: buckets };
    },

    async reportsDaily(params: ReportRangeParams): Promise<{ items: ReportsDailyRow[] }> {
      await delay(150);
      requireManage('pbx.manage');
      validateReportRange(params);
      const list = callsInRange(params).filter((c) => !params.queue_id || assignedQueueId(c) === params.queue_id);
      const byDate = new Map<string, ReportsDailyRow>();
      list.forEach((c) => {
        const date = c.started_at.slice(0, 10);
        const row = byDate.get(date) ?? { date, total: 0, answered: 0, missed: 0 };
        row.total += 1;
        if (c.disposition === 'answered') row.answered += 1;
        if (c.disposition === 'no_answer') row.missed += 1;
        byDate.set(date, row);
      });
      return { items: Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date)) };
    },

    // ─────────────────────── M2c §1 — xavfsizlik sozlamalari ───────────────────────

    async securitySettings(): Promise<SecuritySettings> {
      await delay(150);
      return securitySettings;
    },

    async updateSecuritySettings(payload: UpdateSecuritySettingsPayload): Promise<Mutated<SecuritySettings>> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== securitySettings.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      validateSecuritySettingsPayload(payload);
      const concurrentChanged = payload.toll_fraud?.max_concurrent_outbound !== undefined
        && payload.toll_fraud.max_concurrent_outbound !== securitySettings.toll_fraud.max_concurrent_outbound;
      securitySettings = {
        sip_guard: { ...securitySettings.sip_guard, ...payload.sip_guard },
        toll_fraud: { ...securitySettings.toll_fraud, ...payload.toll_fraud },
        // M10 B2 — ikki bosqichli kirish siyosati ('off'|'admins'|'all').
        require_2fa: payload.require_2fa ?? securitySettings.require_2fa,
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'security_settings', null, 'Xavfsizlik sozlamalari', {});
      const applied = apply(concurrentChanged ? 'Toll-fraud chegarasi oʻzgartirildi — dialplan qayta kompilyatsiya qilindi.' : 'Xavfsizlik sozlamalari tahrirlandi.');
      return { item: securitySettings, apply: applied };
    },

    // ─────────────────────── M2c §2 — SIP hujum himoyasi (S33) ───────────────────────

    async securityBans(): Promise<{ items: IpBan[] }> {
      await delay();
      return { items: ipBans };
    },

    async createSecurityBan(payload: CreateBanPayload): Promise<Mutated<IpBan>> {
      await delay();
      requireManage('system.manage');
      const ip = payload.ip.trim();
      if (!isValidIPv4(ip)) err(422, 'bad_ip', 'IP manzil notoʻgʻri.', { field: 'ip' });
      if (isTrustedIp(ip, securitySettings.sip_guard.trusted_nets)) err(409, 'trusted_ip', 'Bu IP ishonchli tarmoqda — bloklab boʻlmaydi.', { field: 'ip' });
      if (ipBans.some((b) => b.ip === ip)) err(409, 'already_banned', 'Bu IP allaqachon bloklangan.', { field: 'ip' });
      const banS = payload.ban_s ?? securitySettings.sip_guard.ban_s;
      const now = new Date();
      const item: IpBan = {
        id: randomId('ban'), ip, reason: 'manual', failures: 0, note: payload.note?.trim() || null,
        created_at: now.toISOString(),
        expires_at: banS === 0 ? null : new Date(now.getTime() + banS * 1000).toISOString(),
        created_by: currentUser?.login ?? null,
      };
      ipBans = [item, ...ipBans];
      bansPeriodCount += 1;
      securityEvents = [{ id: randomId('sev'), at: now.toISOString(), kind: 'ip_banned', ip, extension: null, details: { reason: 'manual' } }, ...securityEvents];
      auditAdd('create', 'ip_ban', item.id, ip, { ip: [null, ip] });
      const applied = apply(`IP ${ip} bloklandi.`);
      return { item, apply: applied };
    },

    async deleteSecurityBan(id: string): Promise<{ apply: ApplyResult }> {
      await delay();
      requireManage('system.manage');
      const cur = ipBans.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Ban topilmadi.');
      ipBans = ipBans.filter((b) => b.id !== id);
      securityEvents = [{ id: randomId('sev'), at: new Date().toISOString(), kind: 'ip_unbanned', ip: cur.ip, extension: null, details: null }, ...securityEvents];
      auditAdd('delete', 'ip_ban', id, cur.ip, { ip: [cur.ip, null] });
      const applied = apply(`IP ${cur.ip} blokdan chiqarildi.`);
      return { apply: applied };
    },

    async securityStats({ hours = 24 }: SecurityStatsParams): Promise<SecurityStats> {
      await delay(200);
      const hoursList = seedSecurityStatsHours(hours);
      const now = Date.now();
      const activeBans = ipBans.filter((b) => !b.expires_at || Date.parse(b.expires_at) > now);
      const topByIp = new Map<string, SecurityStatsTopIp>(seedSecurityTopIps().map((t) => [t.ip, t]));
      activeBans.forEach((b) => {
        const existing = topByIp.get(b.ip);
        topByIp.set(b.ip, { ip: b.ip, failures: Math.max(b.failures, existing?.failures ?? 0), last_at: b.created_at, banned: true });
      });
      const top_ips = [...topByIp.values()].sort((a, b) => b.failures - a.failures).slice(0, 10);
      return {
        hours: hoursList,
        top_ips,
        totals: {
          failures: hoursList.reduce((s, h) => s + h.failures, 0),
          blocked: hoursList.reduce((s, h) => s + h.blocked, 0),
          bans_active: activeBans.length,
          bans_period: bansPeriodCount,
        },
      };
    },

    async securityEvents({ limit = 100, kind }: ListSecurityEventsParams): Promise<{ items: SecurityEvent[] }> {
      await delay();
      const filtered = kind ? securityEvents.filter((e) => e.kind === kind) : securityEvents;
      return { items: filtered.slice(0, limit) };
    },

    // ─────────────────────── M2c §3 — toll-fraud ───────────────────────

    async tollBlocks(): Promise<{ items: TollBlock[] }> {
      await delay();
      const items: TollBlock[] = extensions
        .filter((e) => e.toll_blocked_at)
        .map((e) => ({ extension_id: e.id, number: e.number, name: e.name, blocked_at: e.toll_blocked_at!, reason: e.toll_block_reason! }));
      return { items };
    },

    async unblockToll(extensionId: string): Promise<{ item: { extension_id: string; number: string } }> {
      await delay();
      requireManage('system.manage');
      const ext = extensions.find((e) => e.id === extensionId);
      if (!ext) err(404, 'not_found', 'Ichki raqam topilmadi.');
      if (!ext.toll_blocked_at) err(409, 'not_blocked', 'Bu ichki raqam bloklanmagan.');
      extensions = extensions.map((e) => (e.id === extensionId ? { ...e, toll_blocked_at: null, toll_block_reason: null } : e));
      securityEvents = [{ id: randomId('sev'), at: new Date().toISOString(), kind: 'toll_unblocked', ip: null, extension: ext.number, details: null }, ...securityEvents];
      auditAdd('update', 'extension', extensionId, ext.number, { toll_blocked_at: [ext.toll_blocked_at, null] });
      return { item: { extension_id: ext.id, number: ext.number } };
    },

    // ─────────────────────── M2c §4 — ogohlantirishlar (Telegram) ───────────────────────

    async alertSettings(): Promise<AlertSettings> {
      await delay(150);
      return { ...alertSettingsCore, has_telegram_token: !!notifySecrets.telegram_token };
    },

    async updateAlertSettings(payload: UpdateAlertSettingsPayload): Promise<AlertSettings> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== alertSettingsCore.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.chat_ids) {
        if (payload.chat_ids.length > 10) err(422, 'bad_chat_id', 'Koʻpi bilan 10 ta chat ID.', { field: 'chat_ids' });
        payload.chat_ids.forEach((id) => { if (!ALERT_CHAT_ID_RE.test(id)) err(422, 'bad_chat_id', `Chat ID notoʻgʻri: ${id}`, { field: 'chat_ids' }); });
      }
      if (payload.dedup_s !== undefined && (payload.dedup_s < 0 || payload.dedup_s > 86400)) err(422, 'bad_value', 'Qiymat 0–86400 oraligʻida boʻlishi kerak.', { field: 'dedup_s' });
      alertSettingsCore = {
        ...alertSettingsCore,
        chat_ids: payload.chat_ids ?? alertSettingsCore.chat_ids,
        dedup_s: payload.dedup_s ?? alertSettingsCore.dedup_s,
        events: payload.events ? { ...alertSettingsCore.events, ...payload.events } : alertSettingsCore.events,
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'alert_settings', null, 'Ogohlantirish sozlamalari', {});
      return { ...alertSettingsCore, has_telegram_token: !!notifySecrets.telegram_token };
    },

    async testAlert(): Promise<TestAlertResult> {
      await delay(400);
      requireManage('system.manage');
      if (!notifySecrets.telegram_token) err(422, 'no_token', 'Telegram bot tokeni sozlanmagan.');
      if (alertSettingsCore.chat_ids.length === 0) err(422, 'no_chat', 'Hech qanday chat ID qoʻshilmagan.');
      if (alertSettingsCore.chat_ids.includes('0')) err(502, 'notify_failed', 'Xabar yetkazilmadi.', { details: { reason: 'telegram_chat_not_found' } });
      const now = new Date().toISOString();
      alertLog = [{ id: randomId('al'), at: now, kind: 'test', key: null, text: 'Sinov xabari — Innova PBX', status: 'sent', error: null, sent_at: now }, ...alertLog];
      return { sent: alertSettingsCore.chat_ids.length };
    },

    async alertLog({ limit = 50, kind }: ListAlertLogParams): Promise<{ items: AlertLogEntry[] }> {
      await delay();
      const filtered = kind ? alertLog.filter((a) => a.kind === kind) : alertLog;
      return { items: filtered.slice(0, limit) };
    },

    // ─────────────────────── M3b §1 — qo'ngiroq yozuvlari ───────────────────────

    async fetchRecordingAudio(id: string): Promise<Blob> {
      await delay(150);
      const call = calls.find((c) => c.recordings.some((r) => r.id === id));
      const rec = call?.recordings.find((r) => r.id === id);
      if (!call || !rec) err(404, 'not_found', 'Yozuv topilmadi.');
      if (currentUser?.role === 'operator') {
        const own = currentUser.extension?.number;
        if (!own || (call.src !== own && call.dst !== own)) err(403, 'forbidden', 'Bu yozuvni eshitish uchun ruxsatingiz yoʻq.');
      }
      return toneWav(rec.duration_s * 1000);
    },

    async deleteRecording(id: string): Promise<void> {
      await delay();
      requireManage('system.manage');
      const call = calls.find((c) => c.recordings.some((r) => r.id === id));
      if (!call) err(404, 'not_found', 'Yozuv topilmadi.');
      call.recordings = call.recordings.filter((r) => r.id !== id);
      auditAdd('delete', 'recording', id, call.uniqueid, {});
    },

    // ─────────────────────── M3b §4 — API kalitlari ───────────────────────

    async listApiKeys(): Promise<{ items: ApiKey[] }> {
      await delay();
      requireManage('system.manage');
      return { items: apiKeys };
    },

    async createApiKey(payload: CreateApiKeyPayload): Promise<CreatedApiKey> {
      await delay();
      requireManage('system.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nom kiritilishi shart.', { field: 'name' });
      if (!payload.scopes || payload.scopes.length === 0) err(422, 'bad_scopes', 'Kamida bitta ruxsat tanlang.', { field: 'scopes' });
      const invalid = payload.scopes.find((s) => !(API_KEY_SCOPES as readonly string[]).includes(s));
      if (invalid) err(422, 'bad_scopes', `Notanish ruxsat: ${invalid}`, { field: 'scopes' });
      const prefix = randomSecret().slice(0, 8).toLowerCase();
      const secret = randomSecret() + randomSecret();
      const item: ApiKey = {
        id: randomId('ak'), name, prefix, scopes: payload.scopes,
        created_at: new Date().toISOString(), last_used_at: null,
        expires_at: payload.expires_at ?? null, revoked_at: null,
      };
      apiKeys = [item, ...apiKeys];
      auditAdd('create', 'api_key', item.id, name, {});
      return { item, key: `ipk_${prefix}_${secret}` };
    },

    async revokeApiKey(id: string): Promise<void> {
      await delay();
      requireManage('system.manage');
      const cur = apiKeys.find((k) => k.id === id);
      if (!cur) err(404, 'not_found', 'API kalit topilmadi.');
      apiKeys = apiKeys.map((k) => (k.id === id ? { ...k, revoked_at: new Date().toISOString() } : k));
      auditAdd('delete', 'api_key', id, cur.name, {});
    },

    // ─────────────────────── M3b §3 — vebhuklar ───────────────────────

    async listWebhooks(): Promise<{ items: Webhook[] }> {
      await delay();
      requireManage('system.manage');
      return { items: webhooks };
    },

    async createWebhook(payload: CreateWebhookPayload): Promise<CreatedWebhook> {
      await delay();
      requireManage('system.manage');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nom kiritilishi shart.', { field: 'name' });
      if (isForbiddenWebhookUrl(payload.url)) err(422, 'url_forbidden', 'Bu manzilga vebhuk yuborish taqiqlangan (loopback/metadata/tizim xosti).', { field: 'url' });
      if (!payload.events || payload.events.length === 0) err(422, 'bad_events', 'Kamida bitta hodisa tanlang.', { field: 'events' });
      const invalid = payload.events.find((e) => !(WEBHOOK_EVENTS as readonly string[]).includes(e));
      if (invalid) err(422, 'bad_events', `Notanish hodisa: ${invalid}`, { field: 'events' });
      const now = new Date().toISOString();
      const secret = randomSecret() + randomSecret();
      const item: Webhook = {
        id: randomId('wh'), name, url: payload.url, events: payload.events,
        include_internal: payload.include_internal ?? false, enabled: payload.enabled ?? true,
        has_secret: true, disabled_reason: null, created_at: now, updated_at: now,
      };
      webhooks = [item, ...webhooks];
      webhookDeliveries.set(item.id, []);
      auditAdd('create', 'webhook', item.id, name, {});
      return { item, secret };
    },

    async updateWebhook(id: string, payload: UpdateWebhookPayload): Promise<Mutated<Webhook>> {
      await delay();
      requireManage('system.manage');
      const cur = webhooks.find((w) => w.id === id);
      if (!cur) err(404, 'not_found', 'Vebhuk topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      if (payload.url !== undefined && isForbiddenWebhookUrl(payload.url)) err(422, 'url_forbidden', 'Bu manzilga vebhuk yuborish taqiqlangan.', { field: 'url' });
      if (payload.events !== undefined && payload.events.length === 0) err(422, 'bad_events', 'Kamida bitta hodisa tanlang.', { field: 'events' });
      const item: Webhook = {
        ...cur,
        name: payload.name ?? cur.name,
        url: payload.url ?? cur.url,
        events: payload.events ?? cur.events,
        include_internal: payload.include_internal ?? cur.include_internal,
        enabled: payload.enabled ?? cur.enabled,
        disabled_reason: payload.enabled === true ? null : cur.disabled_reason,
        updated_at: new Date().toISOString(),
      };
      webhooks = webhooks.map((w) => (w.id === id ? item : w));
      auditAdd('update', 'webhook', id, item.name, {});
      return { item, apply: { status: 'realtime', revision: null, message: null } };
    },

    async deleteWebhook(id: string): Promise<void> {
      await delay();
      requireManage('system.manage');
      const cur = webhooks.find((w) => w.id === id);
      if (!cur) err(404, 'not_found', 'Vebhuk topilmadi.');
      webhooks = webhooks.filter((w) => w.id !== id);
      webhookDeliveries.delete(id);
      auditAdd('delete', 'webhook', id, cur.name, {});
    },

    async rotateWebhookSecret(id: string): Promise<RotatedWebhookSecret> {
      await delay();
      requireManage('system.manage');
      const cur = webhooks.find((w) => w.id === id);
      if (!cur) err(404, 'not_found', 'Vebhuk topilmadi.');
      auditAdd('update', 'webhook', id, cur.name, {});
      return { secret: randomSecret() + randomSecret() };
    },

    async testWebhook(id: string): Promise<TestWebhookResult> {
      await delay(300);
      requireManage('system.manage');
      const cur = webhooks.find((w) => w.id === id);
      if (!cur) err(404, 'not_found', 'Vebhuk topilmadi.');
      const list = webhookDeliveries.get(id) ?? [];
      const delivery: WebhookDelivery = {
        id: randomId('dl'), event_type: 'test.ping', status: 'success', http_status: 200,
        attempts: 1, next_retry_at: null, last_error: null, created_at: new Date().toISOString(),
      };
      webhookDeliveries.set(id, [delivery, ...list]);
      return { queued: true };
    },

    async webhookDeliveries(id: string, { status, limit = 200 }: ListDeliveriesParams): Promise<{ items: WebhookDelivery[] }> {
      await delay();
      requireManage('system.manage');
      if (!webhooks.some((w) => w.id === id)) err(404, 'not_found', 'Vebhuk topilmadi.');
      const list = webhookDeliveries.get(id) ?? [];
      const filtered = status ? list.filter((d) => d.status === status) : list;
      return { items: filtered.slice(0, limit) };
    },

    async replayDelivery(id: string): Promise<void> {
      await delay(300);
      requireManage('system.manage');
      for (const [whId, list] of webhookDeliveries) {
        const found = list.find((d) => d.id === id);
        if (found) {
          webhookDeliveries.set(whId, list.map((d) => (d.id === id ? { ...d, status: 'success', http_status: 200, attempts: d.attempts + 1, next_retry_at: null, last_error: null } : d)));
          return;
        }
      }
      err(404, 'not_found', 'Yetkazish yozuvi topilmadi.');
    },

    // ─────────────────────── M3b §5 — CRM (Bitrix24 / amoCRM) ───────────────────────

    async bitrix24Config(): Promise<BitrixConfigResult> {
      await delay();
      requireManage('system.manage');
      return bitrixConfig;
    },

    async updateBitrix24Config(payload: UpdateBitrixPayload): Promise<BitrixConfigResult> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== bitrixConfig.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.webhook_url !== undefined && !/^https:\/\/.+\/rest\/.+\/.+\/?$/.test(payload.webhook_url)) {
        err(422, 'bad_webhook_url', 'Bitrix24 kiruvchi vebhuk manzili notoʻgʻri (https://portal/rest/user/code/).', { field: 'webhook_url' });
      }
      const hasWebhook = payload.webhook_url !== undefined ? true : bitrixConfig.config.has_webhook_url;
      const tokenSet = payload.application_token !== undefined ? true : bitrixConfig.config.application_token_set;
      bitrixConfig = {
        ...bitrixConfig,
        enabled: payload.enabled,
        config: {
          ...bitrixConfig.config,
          has_webhook_url: hasWebhook,
          create_lead: payload.create_lead,
          popup_max_delay_s: payload.popup_max_delay_s,
          default_user_id: payload.default_user_id,
          application_token_set: tokenSet,
        },
        status: payload.enabled && hasWebhook ? { ...bitrixConfig.status, state: 'ok', last_ok_at: new Date().toISOString(), last_error: null } : { ...bitrixConfig.status, state: 'disabled' },
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'crm_bitrix24', null, 'Bitrix24', {});
      return bitrixConfig;
    },

    async amoCrmConfig(): Promise<AmoConfigResult> {
      await delay();
      requireManage('system.manage');
      return amoConfig;
    },

    async updateAmoCrmConfig(payload: UpdateAmoPayload): Promise<AmoConfigResult> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== amoConfig.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.base_url && !/^https:\/\/[a-z0-9-]+\.amocrm\.ru\/?$/i.test(payload.base_url) && !/^https:\/\/[a-z0-9-]+\.kommo\.com\/?$/i.test(payload.base_url)) {
        err(422, 'bad_base_url', 'Manzil notoʻgʻri (https://<kompaniya>.amocrm.ru).', { field: 'base_url' });
      }
      const tokenSet = payload.token !== undefined ? true : amoConfig.config.token_set;
      amoConfig = {
        ...amoConfig,
        enabled: payload.enabled,
        config: { base_url: payload.base_url, token_set: tokenSet, unsorted_for_unknown: payload.unsorted_for_unknown, default_user_id: payload.default_user_id },
        status: payload.enabled && tokenSet ? { ...amoConfig.status, state: 'ok', last_ok_at: new Date().toISOString(), last_error: null } : { ...amoConfig.status, state: 'disabled' },
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'crm_amocrm', null, 'amoCRM', {});
      return amoConfig;
    },

    async testCrm(provider: CrmProvider): Promise<CrmTestResult> {
      await delay(400);
      requireManage('system.manage');
      if (provider === 'bitrix24') {
        if (!bitrixConfig.config.has_webhook_url) err(422, 'not_configured', 'Avval ulanish maʼlumotlarini saqlang.');
        bitrixConfig = { ...bitrixConfig, status: { ...bitrixConfig.status, state: 'ok', last_ok_at: new Date().toISOString(), last_error: null } };
      } else {
        if (!amoConfig.config.token_set) err(422, 'not_configured', 'Avval ulanish maʼlumotlarini saqlang.');
        amoConfig = { ...amoConfig, status: { ...amoConfig.status, state: 'ok', last_ok_at: new Date().toISOString(), last_error: null } };
      }
      return { ok: true, message: 'Ulanish muvaffaqiyatli — foydalanuvchilar yuklandi.', users_loaded: 1 };
    },

    async updateCrmUserMap(provider: CrmProvider, payload: UpdateCrmUserMapPayload): Promise<{ items: CrmUserMapEntry[] }> {
      await delay();
      requireManage('system.manage');
      const next: CrmUserMapEntry[] = payload.entries.map((e) => ({ extension: e.extension, crm_user_id: e.crm_user_id, crm_user_name: e.crm_user_id ? `CRM foydalanuvchi ${e.crm_user_id}` : null, source: 'manual' as const }));
      if (provider === 'bitrix24') bitrixConfig = { ...bitrixConfig, user_map: next };
      else amoConfig = { ...amoConfig, user_map: next };
      auditAdd('update', `crm_${provider}_user_map`, null, provider, {});
      return { items: next };
    },

    // 1C — tayyor namunalar

    async listOneCSamples(): Promise<{ items: OneCSample[] }> {
      await delay();
      requireManage('system.manage');
      return { items: oneCSamples };
    },

    async fetchOneCSample(name: string): Promise<Blob> {
      await delay(150);
      requireManage('system.manage');
      const sample = oneCSamples.find((s) => s.name === name);
      if (!sample) err(404, 'not_found', 'Namuna topilmadi.');
      return new Blob([`-- Innova PBX 1C namunasi: ${sample.title}\n-- (${sample.name})\n`], { type: 'text/plain' });
    },

    // ─────────────────────── M3b §6 — sozlamalar ───────────────────────

    async integrationsSettings(): Promise<IntegrationsSettings> {
      await delay();
      requireManage('system.manage');
      return integrationsSettingsCore;
    },

    async updateIntegrationsSettings(payload: UpdateIntegrationsSettingsPayload): Promise<IntegrationsSettings> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== integrationsSettingsCore.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.recording_link_ttl_s !== undefined && (payload.recording_link_ttl_s < 60 || payload.recording_link_ttl_s > 30 * 24 * 3600)) {
        err(422, 'bad_value', 'Qiymat 60 soniyadan 30 kungacha boʻlishi kerak.', { field: 'recording_link_ttl_s' });
      }
      integrationsSettingsCore = {
        public_base_url: payload.public_base_url !== undefined ? payload.public_base_url : integrationsSettingsCore.public_base_url,
        recording_link_ttl_s: payload.recording_link_ttl_s ?? integrationsSettingsCore.recording_link_ttl_s,
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'integrations_settings', null, 'Integratsiyalar sozlamalari', {});
      return integrationsSettingsCore;
    },

    async recordingSettings(): Promise<RecordingSettings> {
      await delay();
      requireManage('system.manage');
      return recordingSettingsCore;
    },

    async updateRecordingSettings(payload: UpdateRecordingSettingsPayload): Promise<RecordingSettings> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== recordingSettingsCore.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.retention_days !== undefined && (payload.retention_days < 1 || payload.retention_days > 3650)) {
        err(422, 'bad_value', 'Qiymat 1–3650 kun oraligʻida boʻlishi kerak.', { field: 'retention_days' });
      }
      recordingSettingsCore = {
        retention_days: payload.retention_days ?? recordingSettingsCore.retention_days,
        external_only: payload.external_only ?? recordingSettingsCore.external_only,
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'recording_settings', null, 'Yozib olish sozlamalari', {});
      return recordingSettingsCore;
    },

    // ─────────────────────── M4a — qarang ../../replica/m4a-contract.md (S35 «Qurilmalar») ───────────────────────

    async listDevices(params: ListDevicesParams): Promise<{ items: Device[] }> {
      await delay();
      requireManage('system.manage');
      let items = devices;
      if (params.extension_id) items = items.filter((d) => d.extension?.id === params.extension_id);
      if (params.vendor) items = items.filter((d) => d.vendor === params.vendor);
      if (params.q) {
        const q = params.q.toLowerCase();
        items = items.filter((d) => d.mac.includes(q) || d.model.toLowerCase().includes(q) || (d.label ?? '').toLowerCase().includes(q) || (d.extension?.number ?? '').includes(q));
      }
      return { items };
    },

    async createDevice(payload: CreateDevicePayload): Promise<{ item: Device }> {
      await delay();
      requireManage('system.manage');
      const mac = normalizeMac(payload.mac);
      if (devices.some((d) => d.mac === mac)) err(409, 'mac_taken', 'Bu MAC manzilli apparat allaqachon roʻyxatda bor.', { field: 'mac' });
      if (!DEVICE_VENDORS.includes(payload.vendor)) err(422, 'bad_value', 'Nomaʼlum ishlab chiqaruvchi.', { field: 'vendor' });
      if (!deviceModels.some((m) => m.vendor === payload.vendor && m.model === payload.model)) {
        err(422, 'bad_value', 'Nomaʼlum model.', { field: 'model' });
      }
      assertExtensionCanHaveDevice(payload.extension_id);
      const keys = payload.keys ?? [];
      validateDeviceKeys(keys);
      const now = new Date().toISOString();
      const item: Device = {
        id: randomId('dv'), mac, vendor: payload.vendor, model: payload.model, label: payload.label ?? null,
        extension: deviceExtensionRef(payload.extension_id), enabled: true, status: 'never',
        provisioned_at: null, last_seen_at: null, last_ip: null, firmware: null, registered: false,
        keys_count: keys.length, updated_at: now,
      };
      devices = [...devices, item];
      deviceKeysByDevice.set(item.id, keys);
      auditAdd('create', 'device', item.id, item.label ?? item.mac, {});
      return { item };
    },

    async updateDevice(id: string, payload: UpdateDevicePayload): Promise<{ item: Device }> {
      await delay();
      requireManage('system.manage');
      const cur = devices.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Apparat topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu apparat boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.extension_id !== undefined && payload.extension_id !== cur.extension?.id) {
        assertExtensionCanHaveDevice(payload.extension_id, id);
      }
      const now = new Date().toISOString();
      const item: Device = {
        ...cur,
        label: payload.label !== undefined ? payload.label : cur.label,
        extension: payload.extension_id !== undefined ? deviceExtensionRef(payload.extension_id) : cur.extension,
        enabled: payload.enabled ?? cur.enabled,
        updated_at: now,
      };
      devices = devices.map((d) => (d.id === id ? item : d));
      auditAdd('update', 'device', id, item.label ?? item.mac, {});
      return { item };
    },

    async deleteDevice(id: string) {
      await delay();
      requireManage('system.manage');
      const cur = devices.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Apparat topilmadi.');
      devices = devices.filter((d) => d.id !== id);
      deviceKeysByDevice.delete(id);
      auditAdd('delete', 'device', id, cur.label ?? cur.mac, {});
    },

    /** Shartnomada yoʻq, lekin BLF tahrirlovchisi joriy tugmalarni koʻrsatishi uchun kerak — `keys_count` yetarli emas. */
    async deviceKeys(id: string): Promise<{ items: DeviceKey[] }> {
      await delay();
      requireManage('system.manage');
      if (!devices.some((d) => d.id === id)) err(404, 'not_found', 'Apparat topilmadi.');
      return { items: deviceKeysByDevice.get(id) ?? [] };
    },

    async updateDeviceKeys(id: string, payload: UpdateDeviceKeysPayload): Promise<{ item: Device }> {
      await delay();
      requireManage('system.manage');
      const cur = devices.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Apparat topilmadi.');
      const limit = deviceModelLimit(cur.vendor, cur.model);
      if (limit !== null && payload.keys.length > limit) {
        err(422, 'bad_value', `Bu model koʻpi bilan ${limit} ta tugmani qoʻllab-quvvatlaydi.`, { field: 'keys' });
      }
      validateDeviceKeys(payload.keys);
      deviceKeysByDevice.set(id, payload.keys);
      const item: Device = { ...cur, keys_count: payload.keys.length, updated_at: new Date().toISOString() };
      devices = devices.map((d) => (d.id === id ? item : d));
      auditAdd('update', 'device', id, item.label ?? item.mac, {});
      return { item };
    },

    async resyncDevice(id: string): Promise<ResyncDeviceResult> {
      await delay();
      requireManage('system.manage');
      const cur = devices.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Apparat topilmadi.');
      if (!cur.registered) err(409, 'not_registered', 'Apparat hozircha roʻyxatdan oʻtmagan — qayta sozlab boʻlmaydi.');
      devices = devices.map((d) => (d.id === id ? { ...d, status: 'provisioned' as const } : d));
      auditAdd('update', 'device', id, cur.label ?? cur.mac, {});
      return { ok: true };
    },

    async deviceConfig(id: string): Promise<DeviceConfigResult> {
      await delay();
      requireManage('system.manage');
      const cur = devices.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Apparat topilmadi.');
      return renderDeviceConfig(cur);
    },

    async discoveredDevices(): Promise<{ items: DiscoveredDevice[] }> {
      await delay();
      requireManage('system.manage');
      return { items: discoveredDevices };
    },

    async assignDiscoveredDevice(mac: string, payload: AssignDiscoveredDevicePayload): Promise<{ item: Device }> {
      await delay();
      requireManage('system.manage');
      const found = discoveredDevices.find((d) => d.mac === mac);
      if (!found) err(404, 'not_found', 'Topilgan apparat roʻyxatda yoʻq.');
      assertExtensionCanHaveDevice(payload.extension_id);
      const vendor = found.vendor ?? 'yealink';
      const model = payload.model ?? found.model ?? '';
      if (!deviceModels.some((m) => m.vendor === vendor && m.model === model)) {
        err(422, 'bad_value', 'Nomaʼlum model — modelni tanlang.', { field: 'model' });
      }
      const now = new Date().toISOString();
      const item: Device = {
        id: randomId('dv'), mac: found.mac, vendor, model, label: payload.label ?? null,
        extension: deviceExtensionRef(payload.extension_id), enabled: true, status: 'provisioned',
        provisioned_at: now, last_seen_at: found.last_seen_at, last_ip: found.ip, firmware: found.firmware,
        registered: false, keys_count: 0, updated_at: now,
      };
      devices = [...devices, item];
      deviceKeysByDevice.set(item.id, []);
      discoveredDevices = discoveredDevices.filter((d) => d.mac !== mac);
      auditAdd('create', 'device', item.id, item.label ?? item.mac, {});
      return { item };
    },

    async deleteDiscoveredDevice(mac: string) {
      await delay();
      requireManage('system.manage');
      if (!discoveredDevices.some((d) => d.mac === mac)) err(404, 'not_found', 'Topilgan apparat roʻyxatda yoʻq.');
      discoveredDevices = discoveredDevices.filter((d) => d.mac !== mac);
    },

    async deviceModels(): Promise<{ items: DeviceModel[] }> {
      await delay();
      requireManage('system.manage');
      return { items: deviceModels };
    },

    async provisionRequests(params: ListProvisionRequestsParams): Promise<{ items: ProvisionRequest[] }> {
      await delay();
      requireManage('system.manage');
      let items = provisionRequests;
      if (params.mac) items = items.filter((r) => r.mac === params.mac);
      if (params.ip) items = items.filter((r) => r.ip === params.ip);
      const limit = params.limit ?? 200;
      return { items: items.slice(0, limit) };
    },

    async provisioningSettings(): Promise<ProvisioningSettings> {
      await delay();
      requireManage('system.manage');
      return provisioningSettingsCore;
    },

    async updateProvisioningSettings(payload: UpdateProvisioningSettingsPayload): Promise<ProvisioningSettings> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== provisioningSettingsCore.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.allowed_networks && !payload.allowed_networks.every((n) => isValidCidr(n))) {
        err(422, 'bad_value', 'Ruxsat etilgan tarmoqlar roʻyxatida notoʻgʻri CIDR bor.', { field: 'allowed_networks' });
      }
      if (payload.sip_server_host != null && !isValidHost(payload.sip_server_host)) {
        err(422, 'bad_value', 'SIP server manzili notoʻgʻri.', { field: 'sip_server_host' });
      }
      if (payload.extra) {
        for (const [vendor, text] of Object.entries(payload.extra)) {
          if (!text) continue;
          const lineRe = vendor === 'grandstream' ? /^P\d+\s*=.*$/ : /^[\w.]+\s*=.*$/;
          const bad = text.split('\n').some((line: string) => line.trim() && !lineRe.test(line.trim()));
          if (bad) err(422, 'bad_value', `${vendor} qoʻshimcha konfiguratsiya qatorlari notoʻgʻri formatda.`, { field: 'extra' });
        }
      }
      if (payload.admin_password) auditAdd('update', 'provisioning_settings', null, 'Provizioning sozlamalari', { admin_password: ['***', '***'] });
      provisioningSettingsCore = {
        ...provisioningSettingsCore,
        allowed_networks: payload.allowed_networks ?? provisioningSettingsCore.allowed_networks,
        language: payload.language ?? provisioningSettingsCore.language,
        timezone: payload.timezone ?? provisioningSettingsCore.timezone,
        ntp_server: payload.ntp_server ?? provisioningSettingsCore.ntp_server,
        sip_transport: payload.sip_transport ?? provisioningSettingsCore.sip_transport,
        sip_server_host: payload.sip_server_host !== undefined ? payload.sip_server_host : provisioningSettingsCore.sip_server_host,
        extra: { ...provisioningSettingsCore.extra, ...payload.extra },
        has_admin_password: payload.admin_password ? true : provisioningSettingsCore.has_admin_password,
        updated_at: new Date().toISOString(),
      };
      if (!payload.admin_password) auditAdd('update', 'provisioning_settings', null, 'Provizioning sozlamalari', {});
      return provisioningSettingsCore;
    },

    async rotateProvisioningToken(): Promise<RotateProvisioningTokenResult> {
      await delay();
      requireManage('system.manage');
      const newToken = randomSecret() + randomSecret();
      const url = provisioningSettingsCore.url.replace(/\/prov\/[^/]+\//, `/prov/${newToken}/`);
      provisioningSettingsCore = { ...provisioningSettingsCore, url, updated_at: new Date().toISOString() };
      auditAdd('update', 'provisioning_settings', null, 'Provizioning token almashtirildi', {});
      return { url, updated_at: provisioningSettingsCore.updated_at };
    },

    // ─────────────────────── M4b — qarang ../../replica/m4b-contract.md (S34 «Zaxira») ───────────────────────

    async listBackups(): Promise<{ items: Backup[] }> {
      await delay();
      requireManage('system.manage');
      return { items: backups };
    },

    async createBackup(payload: CreateBackupPayload): Promise<{ job: BackupJob }> {
      await delay();
      requireManage('system.manage');
      if (!backupPassphraseValue) err(409, 'passphrase_required', 'Avval zaxira parolini oʻrnating.');
      if ([...backupJobs.values()].some((j) => jobProgress(j) < 100)) err(409, 'job_running', 'Hozir boshqa zaxira/tiklash ishi ketmoqda.');
      if (!payload.components.length) err(422, 'bad_value', 'Kamida bitta qism tanlanishi kerak.', { field: 'components' });
      const jobId = randomId('job');
      const newId = randomId('bk');
      const startedAt = Date.now();
      const createdBy = currentUser ? { id: currentUser.id, login: currentUser.login } : null;
      backupJobs.set(jobId, {
        kind: 'backup', startedAt, totalMs: 2200, outcome: 'ok', finalized: false,
        steps: ['Maʼlumotlar bazasi dump qilinmoqda', 'Fayllar arxivlanmoqda', 'Shifrlanmoqda', 'Saqlash joylariga yuklanmoqda'],
        finalize: () => {
          const now = new Date().toISOString();
          const sizeBytes = payload.components.includes('recordings') ? 48_234_496 : 21_004_288;
          const fileName = backupFileName('innova-pbx1', now, newId);
          const copies: BackupCopy[] = [
            { target: 'local', status: 'ok', remote_path: `/var/lib/innova/backups/${fileName}`, size_bytes: sizeBytes, error: null, uploaded_at: now },
          ];
          if (backupSettingsCore.targets.s3.enabled) {
            copies.push({ target: 's3', status: 'ok', remote_path: `${backupSettingsCore.targets.s3.prefix}${fileName}`, size_bytes: sizeBytes, error: null, uploaded_at: now });
          }
          if (backupSettingsCore.targets.sftp.enabled) {
            copies.push({ target: 'sftp', status: 'ok', remote_path: `${backupSettingsCore.targets.sftp.folder}/${fileName}`, size_bytes: sizeBytes, error: null, uploaded_at: now });
          }
          const manifest: BackupManifest = {
            format: 'INNOVABK1', product_version: '1.4.0', alembic_revision: 'f3a9c1', created_at: now,
            source_host: 'pbx1.innova.local', components: payload.components,
            parts: payload.components.map((c) => ({ name: `${c}.part`, size: Math.round(sizeBytes / payload.components.length), sha256: randomSecret() })),
            db_key_fp: 'e1f2a3b4c5d6e7f8',
          };
          const item: Backup = {
            id: newId, kind: 'manual', status: copies.some((c) => c.status === 'failed') ? 'partial' : 'ok',
            components: payload.components, step: null, progress: 100, file_name: fileName, sha256: randomSecret(),
            manifest, size_bytes: sizeBytes, copies, created_by: createdBy, created_at: now,
          };
          backups = [item, ...backups];
          auditAdd('create', 'backup', item.id, item.file_name ?? item.id, {});
        },
      });
      return { job: { kind: 'backup', id: jobId } };
    },

    async backupDetail(id: string): Promise<{ item: Backup }> {
      await delay();
      requireManage('system.manage');
      const item = backups.find((b) => b.id === id);
      if (!item) err(404, 'not_found', 'Zaxira topilmadi.');
      return { item };
    },

    async deleteBackup(id: string) {
      await delay();
      requireManage('system.manage');
      const cur = backups.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Zaxira topilmadi.');
      backups = backups.filter((b) => b.id !== id);
      auditAdd('delete', 'backup', id, cur.file_name ?? id, {});
    },

    async downloadBackup(id: string): Promise<Blob> {
      await delay();
      requireManage('system.manage');
      const cur = backups.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Zaxira topilmadi.');
      if (!cur.copies.some((c) => c.target === 'local' && c.status === 'ok')) {
        err(409, 'no_local_copy', 'Lokal nusxa yoʻq — avval masofaviydan olib kelish kerak.');
      }
      return new Blob([`INNOVABK1-demo:${cur.file_name}`], { type: 'application/octet-stream' });
    },

    async fetchBackupCopy(id: string): Promise<{ item: Backup }> {
      await delay(600);
      requireManage('system.manage');
      const cur = backups.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Zaxira topilmadi.');
      const remote = cur.copies.find((c) => c.target !== 'local' && c.status === 'ok');
      if (!remote) err(409, 'no_local_copy', 'Hech qaysi masofaviy joyda muvaffaqiyatli nusxa topilmadi.');
      const now = new Date().toISOString();
      const item: Backup = {
        ...cur,
        copies: cur.copies.map((c) => (c.target === 'local'
          ? { target: 'local' as const, status: 'ok' as const, remote_path: `/var/lib/innova/backups/${cur.file_name}`, size_bytes: cur.size_bytes, error: null, uploaded_at: now }
          : c)),
      };
      backups = backups.map((b) => (b.id === id ? item : b));
      auditAdd('update', 'backup', id, cur.file_name ?? id, {});
      return { item };
    },

    async uploadBackup(file: File): Promise<{ item: Backup }> {
      await delay(500);
      requireManage('system.manage');
      const now = new Date().toISOString();
      const id = randomId('bk');
      uploadedFixtures.set(id, file.name.includes('corrupt') ? 'corrupt' : file.name.includes('newer') ? 'newer' : 'ok');
      const item: Backup = {
        id, kind: 'uploaded', status: 'ok', components: [], step: null, progress: 100, file_name: file.name,
        sha256: null, manifest: null, size_bytes: file.size,
        copies: [{ target: 'local', status: 'ok', remote_path: `/var/lib/innova/backups/${file.name}`, size_bytes: file.size, error: null, uploaded_at: now }],
        created_by: currentUser ? { id: currentUser.id, login: currentUser.login } : null, created_at: now,
      };
      backups = [item, ...backups];
      auditAdd('create', 'backup', item.id, item.file_name ?? item.id, {});
      return { item };
    },

    async inspectBackup(id: string, payload: InspectBackupPayload): Promise<InspectBackupResult> {
      await delay(500);
      requireManage('system.manage');
      const cur = backups.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Zaxira topilmadi.');
      const fixture = uploadedFixtures.get(id) ?? 'ok';
      if (fixture === 'corrupt') err(422, 'backup_corrupt', 'Zaxira fayli buzilgan — qism yetishmaydi yoki oʻzgartirilgan.');
      if (!backupPassphraseValue) err(409, 'passphrase_required', 'Avval zaxira parolini oʻrnating.');
      if (payload.passphrase !== undefined && payload.passphrase !== backupPassphraseValue) {
        err(422, 'bad_passphrase', 'Parol notoʻgʻri.', { field: 'passphrase' });
      }
      if (fixture === 'newer') err(422, 'backup_newer', 'Zaxira joriy versiyadan yangiroq — avval tizimni yangilang.');
      const manifest: BackupManifest = cur.manifest ?? {
        format: 'INNOVABK1', product_version: '1.4.0', alembic_revision: 'f3a9c1', created_at: cur.created_at,
        source_host: 'pbx1.innova.local', components: ['config', 'history', 'sounds', 'voicemail', 'certs'],
        parts: [{ name: 'db.dump', size: cur.size_bytes ?? 1024, sha256: randomSecret() }], db_key_fp: 'e1f2a3b4c5d6e7f8',
      };
      backups = backups.map((b) => (b.id === id ? { ...b, manifest, components: manifest.components, sha256: b.sha256 ?? randomSecret() } : b));
      const warnings = manifest.components.includes('recordings') ? [] : ['Ovoz yozuvlari zaxirada yoʻq.'];
      return { manifest, checks: { sha256: 'ok' }, compatible: true, warnings };
    },

    async restoreBackup(id: string, payload: RestoreBackupPayload): Promise<{ job: BackupJob }> {
      await delay();
      requireManage('system.manage');
      const cur = backups.find((b) => b.id === id);
      if (!cur) err(404, 'not_found', 'Zaxira topilmadi.');
      if (payload.confirm !== 'TIKLASH') err(422, 'confirm_required', 'Tasdiqlash uchun "TIKLASH" deb yozing.', { field: 'confirm' });
      if ([...backupJobs.values()].some((j) => jobProgress(j) < 100)) err(409, 'job_running', 'Hozir boshqa zaxira/tiklash ishi ketmoqda.');
      if (!payload.force && fakeActiveCallCount > 0) err(409, 'active_calls', `${fakeActiveCallCount} ta faol qoʻngʻiroq bor.`, { details: { count: fakeActiveCallCount } });
      if (backupPassphraseValue && payload.passphrase !== undefined && payload.passphrase !== backupPassphraseValue) {
        err(422, 'bad_passphrase', 'Parol notoʻgʻri.', { field: 'passphrase' });
      }
      const jobId = randomId('job');
      const preRestoreId = randomId('bk');
      const startedBy = currentUser ? { id: currentUser.id, login: currentUser.login } : null;
      const startedAtIso = new Date().toISOString();
      const preRestoreFileName = backupFileName('innova-pbx1-pre-restore', startedAtIso, preRestoreId);
      backups = [{
        id: preRestoreId, kind: 'pre_restore', status: 'ok', components: cur.components, step: null, progress: 100,
        file_name: preRestoreFileName, sha256: randomSecret(), manifest: cur.manifest, size_bytes: cur.size_bytes,
        copies: [{ target: 'local', status: 'ok', remote_path: `/var/lib/innova/backups/${preRestoreFileName}`, size_bytes: cur.size_bytes, error: null, uploaded_at: startedAtIso }],
        created_by: startedBy, created_at: startedAtIso,
      }, ...backups];
      restoreJobs = [{
        id: jobId, backup_id: id, source: cur.kind === 'uploaded' ? 'upload' : 'local', status: 'running', step: null,
        progress: 0, error: null, force: !!payload.force, pre_restore_backup_id: preRestoreId, started_by: startedBy,
        started_at: startedAtIso, finished_at: null,
      }, ...restoreJobs];
      backupJobs.set(jobId, {
        kind: 'restore', startedAt: Date.now(), totalMs: 2600, outcome: 'ok', finalized: false,
        steps: [
          'Texnik xizmat rejimiga oʻtilmoqda', 'Maʼlumotlar bazasi tiklanmoqda', 'Fayllar tiklanmoqda',
          'Konfiguratsiya qayta yaratilmoqda', 'Asterisk qayta yuklanmoqda',
        ],
        finalize: () => {
          restoreJobs = restoreJobs.map((rj) => (rj.id === jobId ? { ...rj, status: 'ok', progress: 100, finished_at: new Date().toISOString() } : rj));
          refreshTokens.clear();
          currentUser = null;
        },
      });
      auditAdd('restore', 'backup', id, cur.file_name ?? id, {});
      return { job: { kind: 'restore', id: jobId } };
    },

    /** Sirsiz holat soʻrovi — shartnoma: maintenance paytida ham, tiklashdan keyin sessiya bekor boʻlsa ham ochiq. */
    async backupJob(id: string): Promise<BackupJobState> {
      await delay();
      const job = backupJobs.get(id);
      if (!job) err(404, 'not_found', 'Ish topilmadi.');
      return readBackupJobState(job);
    },

    async listRestores(): Promise<{ items: RestoreJob[] }> {
      await delay();
      requireManage('system.manage');
      return { items: restoreJobs };
    },

    async backupSettings(): Promise<BackupSettings> {
      await delay();
      requireManage('system.manage');
      return backupSettingsCore;
    },

    async updateBackupSettings(payload: UpdateBackupSettingsPayload): Promise<BackupSettings> {
      await delay();
      requireManage('system.manage');
      if (payload.updated_at !== backupSettingsCore.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.schedule) {
        if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(payload.schedule.time)) err(422, 'bad_value', 'Vaqt notoʻgʻri formatda (SS:DD).', { field: 'schedule' });
        if (payload.schedule.weekday < 1 || payload.schedule.weekday > 7) err(422, 'bad_value', 'Hafta kuni notoʻgʻri.', { field: 'schedule' });
        if (!payload.schedule.components.length) err(422, 'bad_value', 'Kamida bitta qism tanlanishi kerak.', { field: 'schedule' });
      }
      const localTarget = validatedLocalTarget(payload.targets?.local, backupSettingsCore.targets.local);
      const s3Target = validatedS3Target(payload.targets?.s3, backupSettingsCore.targets.s3);
      const sftpTarget = validatedSftpTarget(payload.targets?.sftp, backupSettingsCore.targets.sftp, sftpTrustedHost);
      if (payload.targets?.sftp && payload.targets.sftp.host !== backupSettingsCore.targets.sftp.host) sftpTrustedHost = null;
      backupSettingsCore = {
        ...backupSettingsCore,
        schedule: payload.schedule ?? backupSettingsCore.schedule,
        targets: { local: localTarget, s3: s3Target, sftp: sftpTarget },
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'backup_settings', null, 'Zaxira sozlamalari', {});
      return backupSettingsCore;
    },

    async updateBackupPassphrase(payload: UpdateBackupPassphrasePayload): Promise<{ ok: true }> {
      await delay();
      requireManage('system.manage');
      if (payload.passphrase.length < 12) err(422, 'bad_value', 'Zaxira paroli kamida 12 belgidan iborat boʻlishi kerak.', { field: 'passphrase' });
      if (backupPassphraseValue && payload.current !== backupPassphraseValue) err(422, 'bad_passphrase', 'Joriy parol notoʻgʻri.', { field: 'current' });
      backupPassphraseValue = payload.passphrase;
      backupSettingsCore = { ...backupSettingsCore, has_passphrase: true, updated_at: new Date().toISOString() };
      auditAdd('update', 'backup_settings', null, 'Zaxira paroli oʻrnatildi', {});
      return { ok: true };
    },

    async testBackupTarget(payload: TestBackupTargetPayload): Promise<TestBackupTargetResult> {
      await delay(700);
      requireManage('system.manage');
      if (payload.target === 's3') {
        const s3 = backupSettingsCore.targets.s3;
        if (!s3.enabled) err(422, 'bad_value', 'S3 avval yoqilib saqlanishi kerak.', { field: 'target' });
        if (!s3.access_key || !s3.has_secret_key || !s3.bucket) return { ok: false, error: 'Kalit, parol yoki bucket toʻliq emas.' };
        return { ok: true };
      }
      const sftp = backupSettingsCore.targets.sftp;
      if (!sftp.enabled) err(422, 'bad_value', 'SFTP avval yoqilib saqlanishi kerak.', { field: 'target' });
      if (!sftp.host || !sftp.user || (!sftp.has_password && !sftp.has_key)) return { ok: false, error: 'Ulanish maʼlumotlari toʻliq emas.' };
      if (sftp.host_key_fp && sftpTrustedHost === sftp.host) return { ok: true };
      return { ok: true, host_key_fp: DEMO_SFTP_FINGERPRINT };
    },

    async trustSftpHostKey(payload: TrustSftpHostKeyPayload): Promise<{ ok: true }> {
      await delay();
      requireManage('system.manage');
      if (payload.host_key_fp !== DEMO_SFTP_FINGERPRINT) err(409, 'host_key_mismatch', 'Server barmoq izi oldingisidan farq qiladi.');
      sftpTrustedHost = backupSettingsCore.targets.sftp.host;
      backupSettingsCore = {
        ...backupSettingsCore,
        targets: { ...backupSettingsCore.targets, sftp: { ...backupSettingsCore.targets.sftp, host_key_fp: payload.host_key_fp } },
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'backup_settings', null, 'SFTP barmoq izi tasdiqlandi', {});
      return { ok: true };
    },

    // M5a — qarang ../../replica/m5a-contract.md (S36 «Ko'chirish»)
    async uploadMigrationBundle(file: File): Promise<{ item: MigrationJob }> {
      await delay(500);
      requireManage('system.manage');
      if (file.name.includes('invalid')) err(422, 'bundle_invalid', `Fayl formati tanilmadi yoki buzilgan: ${file.name}`);
      const job = newMigrationJob('upload', { file_name: file.name, size_bytes: file.size, host: null, freepbx_version: null, asterisk_version: null, created_at: null });
      migrationJobs.set(job.id, {
        job, phase: null, phaseStartedAt: 0, phaseTotalMs: 0, phaseSteps: [],
        plan: [], ignored: [], warnings: [],
        forceStale: file.name.includes('stale'), bundleDeleted: false, forceFail: file.name.includes('fail'),
      });
      auditAdd('create', 'migration_job', job.id, file.name, {});
      return { item: job };
    },

    async testMigrationSsh(payload: SshTestPayload): Promise<SshTestResult> {
      await delay(700);
      requireManage('system.manage');
      if (!payload.host || !payload.username || !(payload.password || payload.private_key)) {
        return { ok: false, host_key_fp: null, error: "Ulanish ma'lumotlari to'liq emas." };
      }
      return { ok: true, host_key_fp: SSH_HOST_KEY_FINGERPRINT };
    },

    async fetchMigrationSsh(payload: SshFetchPayload): Promise<{ item: MigrationJob }> {
      await delay(600);
      requireManage('system.manage');
      if (payload.host_key_fp !== SSH_HOST_KEY_FINGERPRINT) err(422, 'host_key_mismatch', 'Server barmoq izi oldingisidan farq qiladi.');
      const job = newMigrationJob('ssh', { file_name: null, size_bytes: null, host: payload.host, freepbx_version: null, asterisk_version: null, created_at: null });
      migrationJobs.set(job.id, {
        job, phase: null, phaseStartedAt: 0, phaseTotalMs: 0, phaseSteps: [],
        plan: [], ignored: [], warnings: [], forceStale: false, bundleDeleted: false, forceFail: false,
      });
      auditAdd('create', 'migration_job', job.id, payload.host, {});
      return { item: job };
    },

    async analyzeMigrationJob(id: string): Promise<{ item: MigrationJob }> {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      if (migrationJobBusy()) err(409, 'job_running', "Hozir boshqa zaxira/ko'chirish ishi ketmoqda.");
      // Qayta tahlil (`plan_stale` 409'idan keyin) eskirgan-reja belgisini tozalaydi; birinchi
      // tahlilda (status hali `uploaded`) bu belgiga tegilmaydi — aks holda u hech qachon qo'llashgacha
      // yetib bormaydi (qarang `uploadMigrationBundle`: fayl nomida "stale" bo'lsa shu yerda o'rnatiladi).
      if (rec.job.status === 'analyzed') rec.forceStale = false;
      rec.phase = 'analyze';
      rec.phaseStartedAt = Date.now();
      rec.phaseTotalMs = 2000;
      rec.phaseSteps = ANALYZE_STEPS;
      rec.job = { ...rec.job, status: 'analyzing', step: ANALYZE_STEPS[0]!, progress: 0 };
      return { item: snapshotMigrationJob(rec) };
    },

    async migrationJob(id: string): Promise<{ item: MigrationJob }> {
      await delay();
      requireManage('system.manage');
      return { item: snapshotMigrationJob(requireMigrationJob(id)) };
    },

    async listMigrationJobs(): Promise<{ items: MigrationJob[] }> {
      await delay();
      requireManage('system.manage');
      const items = [...migrationJobs.values()].map((rec) => snapshotMigrationJob(rec));
      items.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
      return { items };
    },

    async migrationPlan(id: string, params: ListMigrationPlanParams): Promise<{ items: MigrationPlanItem[]; total: number }> {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      snapshotMigrationJob(rec);
      const q = params.q?.trim().toLowerCase();
      const filtered = rec.plan.filter((item) => (
        (!params.kind || item.kind === params.kind)
        && (!params.action || item.action === params.action)
        && (!q || item.name.toLowerCase().includes(q) || item.number?.toLowerCase().includes(q) || item.source_ref.toLowerCase().includes(q))
      ));
      const pageSize = params.page_size ?? 50;
      const page = params.page ?? 1;
      const start = (page - 1) * pageSize;
      return { items: filtered.slice(start, start + pageSize), total: filtered.length };
    },

    async migrationIgnored(id: string): Promise<{ items: MigrationIgnoredItem[] }> {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      snapshotMigrationJob(rec);
      return { items: rec.ignored };
    },

    async migrationWarnings(id: string): Promise<{ items: MigrationWarning[] }> {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      snapshotMigrationJob(rec);
      return { items: rec.warnings };
    },

    async updateMigrationPlan(id: string, payload: PatchMigrationPlanPayload): Promise<{ item: MigrationJob }> {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      snapshotMigrationJob(rec);
      for (const patch of payload.items) {
        const current = rec.plan.find((p) => p.kind === patch.kind && p.source_ref === patch.source_ref);
        if (!current) err(404, 'not_found', 'Reja elementi topilmadi.');
        if (!migrationPatchAllowed(current.action, patch.action, current.replaceable)) {
          err(422, 'action_not_allowed', "Bu amal joriy holatdan ruxsat etilmagan.", { field: 'action' });
        }
        const nextAction: MigrationAction = patch.action === 'replace' ? 'create' : patch.action;
        const nextReason = patch.action === 'replace' ? 'replace_selected' : patch.action === 'skip' ? 'manual_skip' : null;
        rec.plan = rec.plan.map((p) => (p === current ? { ...p, action: nextAction, reason: nextReason } : p));
      }
      rec.job = { ...rec.job, summary: summarizePlan(rec.plan, rec.ignored.length, rec.warnings.length) };
      auditAdd('update', 'migration_job', id, "Reja o'zgartirildi", {});
      return { item: snapshotMigrationJob(rec) };
    },

    async applyMigrationJob(id: string, payload: ApplyMigrationPayload): Promise<{ item: MigrationJob }> {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      snapshotMigrationJob(rec);
      if (payload.confirm !== 'KOCHIRISH') err(422, 'confirm_required', '"KOCHIRISH" deb yozing.', { field: 'confirm' });
      if (rec.job.status === 'analyzing' || rec.job.status === 'applying') err(409, 'job_running', "Hozir boshqa zaxira/ko'chirish ishi ketmoqda.");
      if (rec.job.status !== 'analyzed') err(409, 'job_not_analyzed', "Avval tahlil qiling.");
      if (!backupPassphraseValue) err(409, 'passphrase_required', 'Avval zaxira parolini oʻrnating.');
      if (rec.forceStale) err(409, 'plan_stale', "Reja eskirgan — qayta tahlil qiling.");
      if (migrationJobBusy()) err(409, 'job_running', "Hozir boshqa zaxira/ko'chirish ishi ketmoqda.");
      rec.job = { ...rec.job, options: payload.options, pre_import_backup_id: createPreImportBackup() };
      rec.phase = 'apply';
      rec.phaseStartedAt = Date.now();
      rec.phaseTotalMs = 2400;
      rec.phaseSteps = APPLY_STEPS;
      rec.job = { ...rec.job, status: 'applying', step: APPLY_STEPS[0]!, progress: 0 };
      return { item: snapshotMigrationJob(rec) };
    },

    async deleteMigrationJob(id: string) {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      if (rec.phase) err(409, 'job_running', "Hozir boshqa zaxira/ko'chirish ishi ketmoqda.");
      rec.bundleDeleted = true;
      auditAdd('delete', 'migration_job', id, rec.job.source_meta?.file_name ?? id, {});
    },

    async migrationReport(id: string): Promise<Blob> {
      await delay();
      requireManage('system.manage');
      const rec = requireMigrationJob(id);
      const rows = ['kind,name,action,reason', ...rec.plan.map((p) => `${p.kind},${p.name},${p.action},${p.reason ?? ''}`)];
      return new Blob([rows.join('\n')], { type: 'text/csv' });
    },

    async migrationExportScript(): Promise<Blob> {
      await delay(300);
      requireManage('system.manage');
      return new Blob(['#!/usr/bin/env bash\n# innova-fpbx-export.sh — FreePBX serverda ishlatiladi (faqat o\'qish).\n'], { type: 'text/x-shellscript' });
    },

    // ─────────────────────── M5b — qarang ../../replica/m5b-contract.md ───────────────────────

    async followMe(target: FollowMeTarget): Promise<FollowMeInfo> {
      await delay();
      return followMeInfo(followMeOwner(target));
    },

    async updateFollowMe(target: FollowMeTarget, payload: UpdateFollowMePayload): Promise<FollowMeInfo> {
      await delay();
      const ext = followMeOwner(target);
      if (payload.updated_at && payload.updated_at !== ext.updated_at) err(409, 'stale', 'Ichki raqam boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      const { updated_at: _ignored, ...requested } = payload;
      const next = normalizeFollowMe(requested, {
        own: ext.number,
        extensionNumbers: new Set(extensions.map((e) => e.number)),
        outboundAllowed: extensionOutboundAllowed(ext.id) && !ext.toll_blocked_at,
      });
      const prev = followMeByExt.get(ext.id) ?? defaultFollowMe();
      followMeByExt.set(ext.id, next);
      if (sameFollowMe(prev, next)) return followMeInfo(ext);
      const item: Extension = { ...ext, updated_at: new Date().toISOString() };
      extensions = extensions.map((e) => (e.id === item.id ? item : e));
      auditAdd('update', 'extension', item.id, item.number, { follow_me: [prev.enabled, next.enabled] });
      return followMeInfo(item);
    },

    async createQrProvisioning(target: FollowMeTarget): Promise<QrProvisioning> {
      await delay();
      const ext = followMeOwner(target);
      if (ext.webrtc) err(409, 'extension_webrtc_only', 'Bu raqam faqat brauzer softfoni uchun.');
      const base = (integrationsSettingsCore.public_base_url ?? '').replace(/\/+$/, '');
      if (!base) err(409, 'public_host_not_configured', 'Tashqi manzil sozlanmagan.');
      const token = `${randomSecret()}${randomSecret()}${randomSecret()}${randomSecret()}`;
      return {
        url: `${base}/prov/qr/${token}/linphone.xml`,
        expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
        transport: provisioningSettingsCore.sip_transport,
      };
    },

    // ─────────────────────── M10 C A1 — Callback vidjet (qarang ../../replica/m10-onlinepbx-contract.md §A1) ───────────────────────

    async listCallbackWidgets(): Promise<{ items: CallbackWidget[] }> {
      await delay();
      return { items: callbackWidgets };
    },

    async createCallbackWidget(payload: CreateCallbackWidgetPayload): Promise<Mutated<CallbackWidget>> {
      await delay();
      requireManage('connect:edit');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const target = requireCallbackTarget(payload.target_id);
      const now = new Date().toISOString();
      const publicKey = `${randomSecret()}${randomSecret()}`;
      const item: CallbackWidget = {
        id: randomId('cbw'), name, public_key: publicKey, target,
        allowed_origins: payload.allowed_origins ?? [],
        time_group_id: payload.time_group_id ?? null, time_group_name: timeGroupNameOrNull(payload.time_group_id),
        offhours_mode: payload.offhours_mode ?? 'schedule',
        max_attempts: payload.max_attempts ?? 2, retry_interval_s: payload.retry_interval_s ?? 120,
        callerid_prefix: payload.callerid_prefix ?? null, allow_international: payload.allow_international ?? false,
        appearance: mergeAppearance(DEFAULT_WIDGET_APPEARANCE, payload.appearance),
        enabled: payload.enabled ?? true, embed_snippet: null, updated_at: now,
      };
      item.embed_snippet = widgetEmbedSnippet(publicKey);
      callbackWidgets = [...callbackWidgets, item];
      auditAdd('create', 'callback_widget', item.id, item.name, {});
      // Backend: `callback_widget.create` dialplan'ga ta'sir qiladi (`callback_widget_target_ids` snapshot'da) — apply().
      return { item, apply: apply(`Qayta chaqirish vidjeti: ${item.name}`) };
    },

    async updateCallbackWidget(id: string, payload: UpdateCallbackWidgetPayload): Promise<Mutated<CallbackWidget>> {
      await delay();
      requireManage('connect:edit');
      const cur = requireCallbackWidget(id);
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu vidjet boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const target = payload.target_id ? requireCallbackTarget(payload.target_id) : cur.target;
      const timeGroupId = payload.time_group_id !== undefined ? payload.time_group_id : cur.time_group_id;
      const item: CallbackWidget = {
        ...cur, name, target,
        allowed_origins: payload.allowed_origins ?? cur.allowed_origins,
        time_group_id: timeGroupId, time_group_name: timeGroupNameOrNull(timeGroupId),
        offhours_mode: payload.offhours_mode ?? cur.offhours_mode,
        max_attempts: payload.max_attempts ?? cur.max_attempts, retry_interval_s: payload.retry_interval_s ?? cur.retry_interval_s,
        callerid_prefix: payload.callerid_prefix !== undefined ? payload.callerid_prefix : cur.callerid_prefix,
        allow_international: payload.allow_international ?? cur.allow_international,
        appearance: mergeAppearance(cur.appearance, payload.appearance),
        enabled: payload.enabled ?? cur.enabled, updated_at: new Date().toISOString(),
      };
      callbackWidgets = callbackWidgets.map((w) => (w.id === id ? item : w));
      auditAdd('update', 'callback_widget', item.id, item.name, {});
      return { item, apply: apply(`Qayta chaqirish vidjeti: ${item.name}`) };
    },

    async deleteCallbackWidget(id: string): Promise<void> {
      await delay();
      requireManage('connect:edit');
      const cur = requireCallbackWidget(id);
      callbackWidgets = callbackWidgets.filter((w) => w.id !== id);
      callbackRequests = callbackRequests.filter((r) => r.widget_id !== id);
      auditAdd('delete', 'callback_widget', id, cur.name, {});
    },

    async rotateCallbackWidgetKey(id: string): Promise<Mutated<CallbackWidget>> {
      await delay();
      requireManage('connect:edit');
      const cur = requireCallbackWidget(id);
      const publicKey = `${randomSecret()}${randomSecret()}`;
      const item: CallbackWidget = { ...cur, public_key: publicKey, embed_snippet: widgetEmbedSnippet(publicKey), updated_at: new Date().toISOString() };
      callbackWidgets = callbackWidgets.map((w) => (w.id === id ? item : w));
      auditAdd('update', 'callback_widget', item.id, item.name, { key: ['***', '***'] });
      // Eski kalit bilan ulangan saytlar darhol 404 — dialplan'ga ta'sir qilmaydi, lekin backend bosib
      // qoladigan boshqa admin router'lar bilan bir xil javob shakli uchun apply() baribir chaqiriladi.
      return { item, apply: apply(`Vidjet kaliti yangilandi: ${item.name}`) };
    },

    async listCallbackRequests(params: ListCallbackRequestsParams): Promise<Paged<CallbackRequest>> {
      await delay();
      const { widget_id, status, page = 1, page_size = 50 } = params;
      const filtered = callbackRequests.filter((r) => {
        if (widget_id && r.widget_id !== widget_id) return false;
        if (status && r.status !== status) return false;
        return true;
      });
      const start = (page - 1) * page_size;
      return { items: filtered.slice(start, start + page_size), total: filtered.length };
    },

    // ─────────────────────── M10 C A2 — Javobsiz qoʻngʻiroq xabari (qarang §A2) ───────────────────────

    // Backend `list_missed_call_rules` — filtr/`total` YO'Q, `{items}` qaytadi.
    async listMissedCallRules(): Promise<{ items: MissedCallRule[] }> {
      await delay();
      return { items: missedCallRules };
    },

    async createMissedCallRule(payload: CreateMissedCallRulePayload): Promise<MissedCallRuleMutated> {
      await delay();
      requireManage('apps:edit');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      if ((payload.telegram_chat_ids ?? []).length === 0 && (payload.emails ?? []).length === 0) {
        err(422, 'bad_destination', 'Kamida bitta Telegram chat yoki e-mail kerak.', { field: 'telegram_chat_ids' });
      }
      const item: MissedCallRule = {
        id: randomId('mcr'), name, scope_kind: payload.scope_kind, scope_value: payload.scope_value ?? null,
        telegram_chat_ids: payload.telegram_chat_ids ?? [], emails: payload.emails ?? [],
        include_internal: payload.include_internal ?? false, enabled: payload.enabled ?? true, updated_at: new Date().toISOString(),
      };
      missedCallRules = [...missedCallRules, item];
      auditAdd('create', 'missed_call_rule', item.id, item.name, {});
      return { item };
    },

    async updateMissedCallRule(id: string, payload: UpdateMissedCallRulePayload): Promise<MissedCallRuleMutated> {
      await delay();
      requireManage('apps:edit');
      const cur = requireMissedCallRule(id);
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu qoida boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const telegramIds = payload.telegram_chat_ids ?? cur.telegram_chat_ids;
      const emails = payload.emails ?? cur.emails;
      if (telegramIds.length === 0 && emails.length === 0) err(422, 'bad_destination', 'Kamida bitta Telegram chat yoki e-mail kerak.', { field: 'telegram_chat_ids' });
      const item: MissedCallRule = {
        ...cur, name, scope_kind: payload.scope_kind ?? cur.scope_kind,
        scope_value: payload.scope_value !== undefined ? payload.scope_value : cur.scope_value,
        telegram_chat_ids: telegramIds, emails,
        include_internal: payload.include_internal ?? cur.include_internal, enabled: payload.enabled ?? cur.enabled,
        updated_at: new Date().toISOString(),
      };
      missedCallRules = missedCallRules.map((r) => (r.id === id ? item : r));
      auditAdd('update', 'missed_call_rule', item.id, item.name, {});
      return { item };
    },

    async deleteMissedCallRule(id: string): Promise<void> {
      await delay();
      requireManage('apps:edit');
      const cur = requireMissedCallRule(id);
      missedCallRules = missedCallRules.filter((r) => r.id !== id);
      auditAdd('delete', 'missed_call_rule', id, cur.name, {});
    },

    async testMissedCallRule(id: string): Promise<TestMissedCallRuleResult> {
      await delay(400);
      requireManage('apps:edit');
      const cur = requireMissedCallRule(id);
      if (!cur.enabled) return { ok: false, message: 'Qoida oʻchirilgan.' };
      if (cur.telegram_chat_ids.length === 0 && cur.emails.length === 0) return { ok: false, message: 'Yetkazib berish manzili yoʻq.' };
      return { ok: true, message: 'Sinov xabari yuborildi.' };
    },

    async listMissedCallNotices(params: ListMissedCallNoticesParams): Promise<Paged<MissedCallNotice>> {
      await delay();
      const { rule_id, page = 1, page_size = 50 } = params;
      const filtered = missedCallNotices.filter((n) => !rule_id || n.rule_id === rule_id);
      const start = (page - 1) * page_size;
      return { items: filtered.slice(start, start + page_size), total: filtered.length };
    },

    // ─────────────────────── M10 C A3 — Matndan nutq (TTS, qarang §A3) ───────────────────────

    async getTtsSettings(): Promise<TtsSettings> {
      await delay();
      return ttsSettingsCore;
    },

    async updateTtsSettings(payload: UpdateTtsSettingsPayload): Promise<TtsSettingsMutated> {
      await delay();
      requireManage('apps:edit');
      if (payload.updated_at !== ttsSettingsCore.updated_at) err(409, 'stale', 'Sozlamalar boshqa joyda oʻzgartirilgan. Sahifani yangilang.');
      if (payload.api_key !== undefined) ttsApiKey = payload.api_key === '' ? null : payload.api_key;
      ttsSettingsCore = {
        provider: payload.provider ?? ttsSettingsCore.provider,
        has_api_key: ttsApiKey !== null,
        folder_id: payload.folder_id !== undefined ? payload.folder_id : ttsSettingsCore.folder_id,
        voices: { ...ttsSettingsCore.voices, ...payload.voices },
        updated_at: new Date().toISOString(),
      };
      auditAdd('update', 'tts_settings', null, 'TTS sozlamalari', {});
      return { item: ttsSettingsCore };
    },

    async testTtsSettings(): Promise<TtsTestResult> {
      await delay(500);
      requireManage('apps:edit');
      if (ttsSettingsCore.provider === 'none') return { ok: false, message: 'Provayder tanlanmagan.' };
      if (!ttsSettingsCore.has_api_key) return { ok: false, message: 'API kalit kiritilmagan.' };
      return { ok: true, message: 'Ulanish muvaffaqiyatli.' };
    },

    async createTtsAudio(payload: CreateTtsAudioPayload): Promise<{ item: Audio }> {
      await delay(600);
      requireManage('apps:edit');
      if (ttsSettingsCore.provider === 'none') err(409, 'tts_not_configured', 'TTS provayderi sozlanmagan.');
      const text = payload.text.trim();
      if (!text || text.length > 2000) err(422, 'bad_text', 'Matn 1–2000 belgidan iborat boʻlishi kerak.', { field: 'text' });
      const duration_ms = Math.min(60_000, 1200 + text.length * 60);
      const item: Audio = {
        id: randomId('au'), name: payload.name.trim() || text.slice(0, 40), duration_ms, format: 'wav',
        created_at: new Date().toISOString(),
      };
      audioList = [...audioList, item];
      auditAdd('create', 'audio', item.id, item.name, {});
      return { item };
    },

    async previewTts(payload: TtsPreviewPayload): Promise<Blob> {
      await delay(400);
      if (ttsSettingsCore.provider === 'none') err(409, 'tts_not_configured', 'TTS provayderi sozlanmagan.');
      const text = payload.text.trim();
      if (!text || text.length > 500) err(422, 'bad_text', 'Matn 500 belgidan oshmasligi kerak.', { field: 'text' });
      return toneWav(Math.min(8000, 800 + text.length * 40));
    },

    // ─────────────────────── M10 C B1 — Sifat baholash (qarang §B1) ───────────────────────

    // Backend `list_checklists` — filtr/pagination YO'Q, barcha varaqalar `{items}` qaytadi.
    async listQaChecklists(): Promise<{ items: QaChecklist[] }> {
      await delay();
      return { items: [...qaChecklists].sort((a, b) => a.name.localeCompare(b.name)) };
    },

    // Backend `create_checklist` — flat `QaChecklistOut` qaytaradi (Mutated/apply YO'Q).
    async createQaChecklist(payload: CreateQaChecklistPayload): Promise<QaChecklist> {
      await delay();
      requireManage('reports:edit');
      const name = payload.name.trim();
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      if (qaChecklists.some((c) => c.name === name)) err(409, 'name_taken', 'Shu nomli varaqa allaqachon mavjud', { field: 'name' });
      const item: QaChecklist = {
        id: randomId('qac'), name, is_active: true,
        criteria: normalizeQaCriteria(payload.criteria), updated_at: new Date().toISOString(),
      };
      qaChecklists = [...qaChecklists, item];
      auditAdd('create', 'qa_checklist', item.id, item.name, {});
      return item;
    },

    // Backend `update_checklist` — flat `QaChecklistOut` qaytaradi (Mutated/apply YO'Q).
    async updateQaChecklist(id: string, payload: UpdateQaChecklistPayload): Promise<QaChecklist> {
      await delay();
      requireManage('reports:edit');
      const cur = requireQaChecklist(id);
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu chek-list boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const name = payload.name !== undefined ? payload.name.trim() : cur.name;
      if (!name) err(422, 'bad_name', 'Nomi kerak.', { field: 'name' });
      const item: QaChecklist = {
        ...cur, name, is_active: payload.is_active ?? cur.is_active,
        criteria: payload.criteria ? normalizeQaCriteria(payload.criteria) : cur.criteria,
        updated_at: new Date().toISOString(),
      };
      qaChecklists = qaChecklists.map((c) => (c.id === id ? item : c));
      auditAdd('update', 'qa_checklist', item.id, item.name, {});
      return item;
    },

    async deleteQaChecklist(id: string): Promise<void> {
      await delay();
      requireManage('reports:edit');
      const cur = requireQaChecklist(id);
      const inUse = qaEvaluations.filter((e) => e.checklist_id === id).length;
      if (inUse > 0) err(409, 'in_use', `«${cur.name}» hali ${inUse} baholashda ishlatilgan`, { details: { usages: inUse } });
      qaChecklists = qaChecklists.filter((c) => c.id !== id);
      auditAdd('delete', 'qa_checklist', id, cur.name, {});
    },

    // Backend `list_evaluations` — faqat `call_id` bo'yicha filtr, `size` (page_size EMAS).
    async listQaEvaluations(params: ListQaEvaluationsParams): Promise<Paged<QaEvaluation>> {
      await delay();
      const { call_id, page = 1, size = 50 } = params;
      const filtered = call_id ? qaEvaluations.filter((e) => e.call_id === call_id) : qaEvaluations;
      const sorted = [...filtered].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
      const start = (page - 1) * size;
      return { items: sorted.slice(start, start + size), total: sorted.length };
    },

    // Backend `create_evaluation` — flat `QaEvaluationOut` qaytaradi (Mutated/apply YO'Q, "status"/to'liqlik
    // tekshiruvi YO'Q — har qanday javoblar to'plami qabul qilinadi, ball formula bo'yicha hisoblanadi).
    async createQaEvaluation(payload: CreateQaEvaluationPayload): Promise<QaEvaluation> {
      await delay();
      requireManage('reports:edit');
      const checklist = requireQaChecklist(payload.checklist_id);
      const call = calls.find((c) => c.uniqueid === payload.call_id);
      if (payload.extension_id) {
        if (!extensions.some((e) => e.id === payload.extension_id)) err(404, 'not_found', 'Ichki raqam topilmadi', { field: 'extension_id' });
      }
      const criteriaLike: QaCriterionLike[] = checklist.criteria.map((c) => ({ id: c.id, kind: c.kind, weight: c.weight, critical: c.critical }));
      const score_pct = computeScorePct(criteriaLike, payload.answers);
      const extensionId = payload.extension_id ?? defaultExtensionIdForCall(call);
      const now = new Date().toISOString();
      const item: QaEvaluation = {
        id: randomId('qae'), call_id: payload.call_id, checklist_id: checklist.id, checklist_name: checklist.name,
        extension_id: extensionId, evaluator_id: currentUser?.id ?? null, evaluator_name: currentUser?.full_name ?? null,
        answers: payload.answers, score_pct, comment: payload.comment ?? null, created_at: now, updated_at: now,
      };
      qaEvaluations = [...qaEvaluations, item];
      auditAdd('create', 'qa_evaluation', item.id, item.checklist_name, {});
      return item;
    },

    // Backend `update_evaluation` — flat `QaEvaluationOut` qaytaradi, faqat `answers`/`comment` o'zgaradi.
    async updateQaEvaluation(id: string, payload: UpdateQaEvaluationPayload): Promise<QaEvaluation> {
      await delay();
      requireManage('reports:edit');
      const cur = requireQaEvaluation(id);
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu baho boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const answers = payload.answers ?? cur.answers;
      const checklist = requireQaChecklist(cur.checklist_id);
      const criteriaLike: QaCriterionLike[] = checklist.criteria.map((c) => ({ id: c.id, kind: c.kind, weight: c.weight, critical: c.critical }));
      const item: QaEvaluation = {
        ...cur, answers, score_pct: computeScorePct(criteriaLike, answers),
        comment: payload.comment !== undefined ? payload.comment : cur.comment,
        updated_at: new Date().toISOString(),
      };
      qaEvaluations = qaEvaluations.map((e) => (e.id === id ? item : e));
      auditAdd('update', 'qa_evaluation', item.id, item.checklist_name, {});
      return item;
    },

    async deleteQaEvaluation(id: string): Promise<void> {
      await delay();
      requireManage('reports:edit');
      const cur = requireQaEvaluation(id);
      qaEvaluations = qaEvaluations.filter((e) => e.id !== id);
      auditAdd('delete', 'qa_evaluation', id, cur.checklist_name, {});
    },

    // Backend `/qa/summary` — parametrsiz, tenant-keng, ichki raqam bo'yicha guruhlangan xulosa.
    async qaSummary(): Promise<QaSummary> {
      await delay();
      if (qaEvaluations.length === 0) return { count: 0, avg_score_pct: 0, by_extension: [] };
      const byExt = new Map<string | null, number[]>();
      for (const e of qaEvaluations) {
        const key = e.extension_id;
        byExt.set(key, [...(byExt.get(key) ?? []), e.score_pct]);
      }
      const by_extension = [...byExt.entries()]
        .map(([extId, scores]) => ({
          extension_id: extId,
          extension_number: extId ? extensions.find((e) => e.id === extId)?.number ?? null : null,
          count: scores.length,
          avg_score_pct: Math.round((scores.reduce((s, v) => s + v, 0) / scores.length) * 100) / 100,
        }))
        .sort((a, b) => (a.extension_number ?? '').localeCompare(b.extension_number ?? ''));
      const all = qaEvaluations.map((e) => e.score_pct);
      return { count: all.length, avg_score_pct: Math.round((all.reduce((s, v) => s + v, 0) / all.length) * 100) / 100, by_extension };
    },

    // Backend `GET /calls/{linkedid}/evaluations` — `{items, total}`, `evaluator_name` HAR DOIM null.
    async listCallEvaluations(linkedid: string): Promise<Paged<QaEvaluation>> {
      await delay();
      const items = qaEvaluations.filter((e) => e.call_id === linkedid)
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
        .map((e) => ({ ...e, evaluator_name: null }));
      return { items, total: items.length };
    },

    // Backend `GET /me/evaluations` — faqat o'z ichki raqamiga bog'langan baholar, `evaluator_name` null.
    async listMyEvaluations(params: { page?: number; size?: number }): Promise<Paged<QaEvaluation>> {
      await delay();
      const { page = 1, size = 50 } = params;
      const ownExtId = currentUser ? requireManagedUser(currentUser.id).extension?.id : undefined;
      const filtered = qaEvaluations.filter((e) => ownExtId && e.extension_id === ownExtId)
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
        .map((e) => ({ ...e, evaluator_name: null }));
      const start = (page - 1) * size;
      return { items: filtered.slice(start, start + size), total: filtered.length };
    },

    // ─────────────────────── M10 C B2 — Ikki bosqichli kirish (2FA, qarang §B2) ───────────────────────

    async setupTotp(): Promise<TotpSetup> {
      await delay();
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      const mu = requireManagedUser(currentUser.id);
      const secret = generateTotpSecret();
      totpPendingSecret.set(mu.id, secret);
      return { secret, otpauth_uri: otpauthUri(secret, 'innova', mu.username) };
    },

    async enableTotp({ code }: TotpEnablePayload): Promise<TotpEnableResult> {
      await delay();
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      const mu = requireManagedUser(currentUser.id);
      const secret = totpPendingSecret.get(mu.id);
      if (!secret) err(409, 'setup_required', 'Avval QR kod yarating.');
      const step = await verifyTotp(secret, code);
      if (step === null) err(401, 'bad_code', 'Kod notoʻgʻri.', { field: 'code' });
      const recoveryCodes = generateRecoveryCodes();
      totpByUser.set(mu.id, { secret, enabled: true, recoveryHashes: [...recoveryCodes], lastStep: step });
      totpPendingSecret.delete(mu.id);
      currentUser = toSessionUser(mu);
      auditAdd('update', 'user_2fa', mu.id, mu.full_name, {});
      return { recovery_codes: recoveryCodes };
    },

    async disableTotp({ code }: TotpDisablePayload): Promise<void> {
      await delay();
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      const mu = requireManagedUser(currentUser.id);
      if (require2fa(mu)) err(409, 'policy_required', 'Xavfsizlik siyosati 2FA ni talab qiladi — oʻchirib boʻlmaydi.');
      // Backend `TotpDisablePayload` faqat `code` qabul qiladi — parol so'ralmaydi (qarang schemas_2fa.py).
      const state = totpByUser.get(mu.id);
      if (!state || !(await verifyAnyTotpCode(state, code))) err(401, 'bad_code', 'Kod notoʻgʻri.', { field: 'code' });
      totpByUser.delete(mu.id);
      currentUser = toSessionUser(mu);
      auditAdd('update', 'user_2fa', mu.id, mu.full_name, {});
    },

    async regenerateTotpRecoveryCodes({ code }: TotpRecoveryCodesPayload): Promise<TotpRecoveryCodesResult> {
      await delay();
      if (!currentUser) err(401, 'unauthenticated', 'Tizimga kiring.');
      const mu = requireManagedUser(currentUser.id);
      const state = totpByUser.get(mu.id);
      if (!state) err(409, 'not_enabled', '2FA yoqilmagan.');
      if (!(await verifyAnyTotpCode(state, code))) err(401, 'bad_code', 'Kod notoʻgʻri.', { field: 'code' });
      const recoveryCodes = generateRecoveryCodes();
      state.recoveryHashes = [...recoveryCodes];
      auditAdd('update', 'user_2fa', mu.id, mu.full_name, {});
      return { recovery_codes: recoveryCodes };
    },

    async resetUserTotp(userId: string): Promise<void> {
      await delay();
      requireManage('system.manage');
      const mu = requireManagedUser(userId);
      totpByUser.delete(userId);
      totpPendingSecret.delete(userId);
      if (currentUser && currentUser.id === userId) currentUser = toSessionUser(mu);
      auditAdd('update', 'user_2fa', mu.id, mu.full_name, {});
    },

    // ─────────────────────── M12 A1 — Kun/Tun rejimi (*28N) ───────────────────────
    async listDayNight(): Promise<{ items: DayNight[] }> {
      await delay();
      return { items: dayNights };
    },

    async createDayNight(payload: CreateDayNightPayload): Promise<Mutated<DayNight>> {
      await delay();
      requireManage('routes.manage');
      checkDayNightCodeTaken(payload.code);
      const dayTarget = requireTarget(payload.day_target_id, 'day_target_id');
      const nightTarget = requireTarget(payload.night_target_id, 'night_target_id');
      const id = randomId('dn');
      const now = new Date().toISOString();
      if (payload.pin) dayNightPins.set(id, payload.pin);
      const item: DayNight = {
        id, name: payload.name, code: payload.code, mode: 'day',
        day_target: dayTarget, night_target: nightTarget, has_pin: !!payload.pin, updated_at: now,
      };
      dayNights = [...dayNights, item];
      return { item, apply: apply(`Kun/tun rejimi «${item.name}» qoʻshildi`, item.name) };
    },

    async updateDayNight(id: string, payload: UpdateDayNightPayload): Promise<Mutated<DayNight>> {
      await delay();
      requireManage('routes.manage');
      const cur = dayNights.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Kun/tun rejimi topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      if (payload.code !== undefined && payload.code !== cur.code) checkDayNightCodeTaken(payload.code, id);
      const dayTarget = payload.day_target_id !== undefined ? requireTarget(payload.day_target_id, 'day_target_id') : cur.day_target;
      const nightTarget = payload.night_target_id !== undefined ? requireTarget(payload.night_target_id, 'night_target_id') : cur.night_target;
      if (payload.pin_clear) dayNightPins.delete(id);
      else if (payload.pin !== undefined) { if (payload.pin) dayNightPins.set(id, payload.pin); else dayNightPins.delete(id); }
      const now = new Date().toISOString();
      const item: DayNight = {
        ...cur, name: payload.name ?? cur.name, code: payload.code ?? cur.code,
        day_target: dayTarget, night_target: nightTarget,
        has_pin: payload.pin_clear ? false : payload.pin !== undefined ? !!payload.pin : cur.has_pin,
        updated_at: now,
      };
      dayNights = dayNights.map((d) => (d.id === id ? item : d));
      return { item, apply: apply(`Kun/tun rejimi «${item.name}» tahrirlandi`, item.name) };
    },

    async toggleDayNight(id: string): Promise<Mutated<DayNight>> {
      await delay();
      requireManage('routes.manage');
      const cur = dayNights.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Kun/tun rejimi topilmadi.');
      const now = new Date().toISOString();
      const item: DayNight = { ...cur, mode: cur.mode === 'day' ? 'night' : 'day', updated_at: now };
      dayNights = dayNights.map((d) => (d.id === id ? item : d));
      return { item, apply: apply(`«${item.name}»: ${item.mode === 'night' ? 'tungi' : 'kunduzgi'} rejimga almashtirildi`) };
    },

    async deleteDayNight(id: string) {
      await delay();
      requireManage('routes.manage');
      const cur = dayNights.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'Kun/tun rejimi topilmadi.');
      const usages = usagesForTargetId(cur.id);
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      dayNights = dayNights.filter((d) => d.id !== id);
      dayNightPins.delete(id);
      apply(`Kun/tun rejimi «${cur.name}» oʻchirildi`);
    },

    // ─────────────────────── M12 A2 — DISA ───────────────────────
    async listDisa(): Promise<{ items: Disa[] }> {
      await delay();
      return { items: disas };
    },

    async createDisa(payload: CreateDisaPayload): Promise<Mutated<Disa>> {
      await delay();
      requireManage('pbx.manage');
      if (!payload.pin && !payload.allow_no_pin) err(422, 'pin_required', 'PIN boʻsh boʻlishi uchun allow_no_pin=true koʻrsatilishi shart.', { field: 'pin' });
      const id = randomId('disa');
      const now = new Date().toISOString();
      if (payload.pin) disaPins.set(id, payload.pin);
      const item: Disa = {
        id, name: payload.name, has_pin: !!payload.pin, allow_no_pin: payload.allow_no_pin ?? false,
        cid_override: payload.cid_override ?? null, digit_timeout: payload.digit_timeout ?? 5,
        response_timeout: payload.response_timeout ?? 10, max_attempts: payload.max_attempts ?? 3,
        enabled: payload.enabled ?? true, updated_at: now,
      };
      disas = [...disas, item];
      return { item, apply: apply(`DISA «${item.name}» qoʻshildi`, item.name) };
    },

    async updateDisa(id: string, payload: UpdateDisaPayload): Promise<Mutated<Disa>> {
      await delay();
      requireManage('pbx.manage');
      const cur = disas.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'DISA topilmadi.');
      if (payload.updated_at !== cur.updated_at) err(409, 'stale', 'Bu yozuv boshqa joyda oʻzgartirilgan. Sahifani yangilang.', { details: { current: cur } });
      const nextAllowNoPin = payload.allow_no_pin ?? cur.allow_no_pin;
      const willHavePin = payload.pin_clear ? false : payload.pin !== undefined ? !!payload.pin : cur.has_pin;
      if (!willHavePin && !nextAllowNoPin) err(422, 'pin_required', 'PIN boʻsh boʻlishi uchun allow_no_pin=true koʻrsatilishi shart.', { field: 'pin' });
      if (payload.pin_clear) disaPins.delete(id);
      else if (payload.pin !== undefined) { if (payload.pin) disaPins.set(id, payload.pin); else disaPins.delete(id); }
      const now = new Date().toISOString();
      const item: Disa = {
        ...cur, name: payload.name ?? cur.name, has_pin: willHavePin, allow_no_pin: nextAllowNoPin,
        cid_override: payload.cid_override !== undefined ? payload.cid_override : cur.cid_override,
        digit_timeout: payload.digit_timeout ?? cur.digit_timeout, response_timeout: payload.response_timeout ?? cur.response_timeout,
        max_attempts: payload.max_attempts ?? cur.max_attempts, enabled: payload.enabled ?? cur.enabled,
        updated_at: now,
      };
      disas = disas.map((d) => (d.id === id ? item : d));
      return { item, apply: apply(`DISA «${item.name}» tahrirlandi`, item.name) };
    },

    async deleteDisa(id: string) {
      await delay();
      requireManage('pbx.manage');
      const cur = disas.find((d) => d.id === id);
      if (!cur) err(404, 'not_found', 'DISA topilmadi.');
      const usages = usagesForTargetId(cur.id);
      if (usages.length > 0) err(409, 'in_use', `«${cur.name}» hali ishlatilmoqda.`, { details: { usages } });
      disas = disas.filter((d) => d.id !== id);
      disaPins.delete(id);
      apply(`DISA «${cur.name}» oʻchirildi`);
    },

    // ─────────────────────── M6 — qarang ../../replica/m6-contract.md ───────────────────────
    ...delayed(campaigns.api),
  };
}

export const fakeClient = createFakeClient();
