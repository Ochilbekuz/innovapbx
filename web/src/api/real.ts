import type { ApiClient, Created, Mutated } from './client';
import { request, requestBlob, requestMultipart } from './http';
import type {
  AuditEntry, AuthResult, Audio, BlacklistEntry, Call, Conference, ConfigRevision, CreateBlacklistPayload,
  CreateConferencePayload, CreateExtensionPayload, CreateHolidayPayload,
  CreateInboundRoutePayload, CreateIvrPayload, CreateMohClassPayload, CreateOutboundRoutePayload, CreateQueuePayload,
  CreateRingGroupPayload, CreateTimeConditionPayload, CreateTimeGroupPayload, CreateTrunkPayload,
  CreateVoicemailBoxPayload, DashboardResult, FeatureCode,
  Extension, FlowResult, Holiday, ImportUzHolidaysPayload, ImportUzHolidaysResult, InboundRoute, Ivr, ListAuditParams,
  ListBlacklistParams,
  ListCallsParams, ListExtensionsParams, ListTargetsParams, ListVoicemailBoxesParams, MohClass, NotifySettings,
  NotifyTestPayload, NotifyTestResult, NumbersFreeParams, OutboundOrderPayload,
  OutboundRoute, OutboundSimulateParams, OutboundSimulateResult, OverrideTimeConditionPayload, Paged, Parking, Queue,
  RestartAsteriskResult, RestoreRevisionResult, RevisionDetail, RevisionDiff, RevisionDiffAgainst, RingGroup, RotateSecretResult,
  SelfSignedTlsPayload, SetupPayload, SipSettings, SipTls, SystemHealth, Target, TimeCondition,
  TimeGroup, Trunk, TrunkTestResult, UpdateConferencePayload, UpdateExtensionPayload, UpdateFeatureCodePayload,
  UpdateHolidayPayload, UpdateInboundRoutePayload,
  UpdateIvrPayload, UpdateMePayload, UpdateMohClassPayload, UpdateNotifySettingsPayload,
  UpdateOutboundRoutePayload, UpdateQueuePayload, UpdateRingGroupPayload, UpdateSipSettingsPayload,
  UpdateTimeConditionPayload, UpdateTimeGroupPayload, UpdateTrunkPayload, UpdateVoicemailBoxPayload, Usage, User,
  VoicemailBox, VoicemailMessage,
  // M2b — qarang ../../replica/m2b-contract.md
  ChangePasswordPayload, CreateUserPayload, LiveSnapshot, LiveSpyPayload, LiveSpyResult, ManagedUser, MeOverview,
  PatchMeExtensionPayload, QueueMember, QueueMemberAction, QueueMemberActionPayload, ReportRangeParams, SoftphoneInfo,
  ReportsAgentRow, ReportsDailyRow, ReportsHourlyRow, ReportsQueueRow, ReportsSummary, UpdateQueueMemberPayload,
  UpdateUserPayload,
  // M2c — qarang ../../replica/m2c-contract.md
  AlertLogEntry, AlertSettings, CreateBanPayload, IpBan, ListAlertLogParams, ListSecurityEventsParams,
  SecurityEvent, SecuritySettings, SecurityStats, SecurityStatsParams, TestAlertResult, TollBlock,
  UpdateAlertSettingsPayload, UpdateSecuritySettingsPayload,
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
  Backup, BackupJob, BackupJobState, BackupSettings, CreateBackupPayload, InspectBackupPayload, InspectBackupResult,
  RestoreBackupPayload, RestoreJob, TestBackupTargetPayload, TestBackupTargetResult, TrustSftpHostKeyPayload,
  UpdateBackupPassphrasePayload, UpdateBackupSettingsPayload,
  // M5a — qarang ../../replica/m5a-contract.md
  ApplyMigrationPayload, ListMigrationPlanParams, MigrationIgnoredItem, MigrationJob, MigrationPlanItem,
  MigrationWarning, PatchMigrationPlanPayload, SshFetchPayload, SshTestPayload, SshTestResult,
  // M5b — qarang ../../replica/m5b-contract.md
  FollowMeInfo, FollowMeTarget, QrProvisioning, UpdateFollowMePayload,
  // M6 — qarang ../../replica/m6-contract.md
  Campaign, CampaignAction, CampaignContact, CreateCampaignPayload, ImportCampaignContactsPayload,
  ImportCampaignContactsResult, ListCampaignContactsParams, UpdateCampaignPayload,
  // M7 — qarang ../../replica/m7-roles-contract.md
  CreateRolePayload, RoleOut, UpdateRolePayload,
  // Tizim holati (status) — pbx-klon vazifa (2026-11-02)
  CleanupIn, CleanupResult, SystemStatus,
  // M8 — qarang ../../replica/m8-network-contract.md
  NetworkConfigIn, NetworkStateOut, NetworkValidateResult,
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  AddPinsPayload, Announcement, CidSource, CidSourceTestResult, Contact, CreateAnnouncementPayload,
  CreateCidSourcePayload, CreateContactPayload, CreateMiscApplicationPayload, CreateMiscDestinationPayload,
  CreatePageGroupPayload, CreatePinSetPayload, ImportExtensionsParams, ImportExtensionsResult,
  ImportPhonebookParams, ImportPhonebookResult, ListPhonebookParams, MiscApplication, MiscDestination, PageGroup,
  ParkingCall, ParkingSettings, PinSet, PinSetPin, UpdateAnnouncementPayload, UpdateCidSourcePayload,
  UpdateContactPayload, UpdateMiscApplicationPayload, UpdateMiscDestinationPayload, UpdatePageGroupPayload,
  UpdateParkingSettingsPayload, UpdatePinSetPayload,
} from './types';
import type { ApplyResult } from './types';

function qs(params: Record<string, string | number | undefined>): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : '';
}

/** `ListCallsParams` → query-string. Bitta joyda — `listCalls` va `exportCallsCsv` ikkisi ham shu yerdan foydalanadi. */
function callsQs(params: ListCallsParams): string {
  return qs({
    from: params.from, to: params.to, q: params.q, direction: params.direction, page: params.page, size: params.size,
    src: params.src, src_mode: params.src_mode, src_not: params.src_not ? 'true' : undefined,
    dst: params.dst, dst_mode: params.dst_mode, dst_not: params.dst_not ? 'true' : undefined,
    did: params.did, did_mode: params.did_mode, did_not: params.did_not ? 'true' : undefined,
    name: params.name, ext: params.ext, trunk: params.trunk, account: params.account,
    disposition: params.disposition, min_duration: params.min_duration, max_duration: params.max_duration,
    recording: params.recording,
  });
}

/** Haqiqiy backend (`../api`) — HTTP orqali. Shartnoma: `../../replica/m0-contract.md`. */
/** M5b: admin — `/extensions/{id}`, operator (o'z raqami) — `/me`. */
const ownerPath = (target: FollowMeTarget) => (target ? `/extensions/${encodeURIComponent(target)}` : '/me');

export const realClient: ApiClient = {
  setupState: () => request('/setup/state', { auth: false }),
  setup: (payload: SetupPayload) => request<AuthResult>('/setup', { method: 'POST', body: payload, auth: false }),
  login: (login: string, password: string) => request<AuthResult>('/auth/login', { method: 'POST', body: { login, password }, auth: false }),
  refresh: (refreshToken: string) => request('/auth/refresh', { method: 'POST', body: { refresh: refreshToken }, auth: false }),
  logout: (refreshToken: string) => request('/auth/logout', { method: 'POST', body: { refresh: refreshToken } }),
  me: () => request<User>('/auth/me'),
  updateMe: (payload: UpdateMePayload) => request<User>('/auth/me', { method: 'PATCH', body: payload }),

  listExtensions: (params: ListExtensionsParams) => request<Paged<Extension>>(`/extensions${qs(params)}`),
  createExtension: (payload: CreateExtensionPayload) => request<Created<Extension>>('/extensions', { method: 'POST', body: payload }),
  updateExtension: (id: string, payload: UpdateExtensionPayload) => request<Mutated<Extension>>(`/extensions/${id}`, { method: 'PATCH', body: payload }),
  rotateExtensionSecret: (id: string) => request<RotateSecretResult>(`/extensions/${id}/rotate-secret`, { method: 'POST' }),
  setExtensionSecret: (id: string, password: string) =>
    request<RotateSecretResult>(`/extensions/${id}/secret`, { method: 'PUT', body: { password } }),
  deleteExtension: (id: string) => request<void>(`/extensions/${id}`, { method: 'DELETE' }),

  listTrunks: () => request('/trunks'),
  createTrunk: (payload: CreateTrunkPayload) => request<Mutated<Trunk>>('/trunks', { method: 'POST', body: payload }),
  updateTrunk: (id: string, payload: UpdateTrunkPayload) => request<Mutated<Trunk>>(`/trunks/${id}`, { method: 'PATCH', body: payload }),
  deleteTrunk: (id: string) => request<void>(`/trunks/${id}`, { method: 'DELETE' }),
  testTrunk: (id: string) => request<TrunkTestResult>(`/trunks/${id}/test`, { method: 'POST' }),

  listInboundRoutes: () => request('/inbound-routes'),
  createInboundRoute: (payload: CreateInboundRoutePayload) => request<Mutated<InboundRoute>>('/inbound-routes', { method: 'POST', body: payload }),
  updateInboundRoute: (id: string, payload: UpdateInboundRoutePayload) => request<Mutated<InboundRoute>>(`/inbound-routes/${id}`, { method: 'PATCH', body: payload }),
  deleteInboundRoute: (id: string) => request<void>(`/inbound-routes/${id}`, { method: 'DELETE' }),
  listTargets: (params: ListTargetsParams) => request<{ items: Target[] }>(`/targets${qs(params)}`),
  targetUsages: (id: string) => request<{ items: Usage[] }>(`/targets/${id}/usages`),
  flow: (inboundRouteId: string) => request<FlowResult>(`/flow/${inboundRouteId}`),
  numbersFree: (params: NumbersFreeParams) => request<{ items: string[] }>(`/numbers/free${qs(params)}`),

  listCalls: (params: ListCallsParams) => request<Paged<Call>>(`/calls${callsQs(params)}`),
  exportCallsCsv: (params: ListCallsParams) => requestBlob(`/calls/export.csv${callsQs(params)}`),

  systemHealth: () => request<SystemHealth>('/system/health'),
  configRevisions: (limit = 20) => request<{ items: ConfigRevision[] }>(`/config/revisions${qs({ limit })}`),

  listTimeGroups: () => request('/time-groups'),
  createTimeGroup: (payload: CreateTimeGroupPayload) => request<Mutated<TimeGroup>>('/time-groups', { method: 'POST', body: payload }),
  updateTimeGroup: (id: string, payload: UpdateTimeGroupPayload) => request<Mutated<TimeGroup>>(`/time-groups/${id}`, { method: 'PATCH', body: payload }),
  deleteTimeGroup: (id: string) => request<void>(`/time-groups/${id}`, { method: 'DELETE' }),

  listHolidays: () => request('/holidays'),
  createHoliday: (payload: CreateHolidayPayload) => request<Mutated<Holiday>>('/holidays', { method: 'POST', body: payload }),
  updateHoliday: (id: string, payload: UpdateHolidayPayload) => request<Mutated<Holiday>>(`/holidays/${id}`, { method: 'PATCH', body: payload }),
  deleteHoliday: (id: string) => request<void>(`/holidays/${id}`, { method: 'DELETE' }),
  importUzHolidays: (payload: ImportUzHolidaysPayload) => request<ImportUzHolidaysResult>('/holidays/import-uz', { method: 'POST', body: payload }),

  listTimeConditions: () => request('/time-conditions'),
  createTimeCondition: (payload: CreateTimeConditionPayload) => request<Mutated<TimeCondition>>('/time-conditions', { method: 'POST', body: payload }),
  updateTimeCondition: (id: string, payload: UpdateTimeConditionPayload) => request<Mutated<TimeCondition>>(`/time-conditions/${id}`, { method: 'PATCH', body: payload }),
  deleteTimeCondition: (id: string) => request<void>(`/time-conditions/${id}`, { method: 'DELETE' }),
  overrideTimeCondition: (id: string, payload: OverrideTimeConditionPayload) => request<Mutated<TimeCondition>>(`/time-conditions/${id}/override`, { method: 'POST', body: payload }),

  listIvrs: () => request('/ivrs'),
  createIvr: (payload: CreateIvrPayload) => request<Mutated<Ivr>>('/ivrs', { method: 'POST', body: payload }),
  updateIvr: (id: string, payload: UpdateIvrPayload) => request<Mutated<Ivr>>(`/ivrs/${id}`, { method: 'PATCH', body: payload }),
  deleteIvr: (id: string) => request<void>(`/ivrs/${id}`, { method: 'DELETE' }),

  listRingGroups: () => request('/ring-groups'),
  createRingGroup: (payload: CreateRingGroupPayload) => request<Mutated<RingGroup>>('/ring-groups', { method: 'POST', body: payload }),
  updateRingGroup: (id: string, payload: UpdateRingGroupPayload) => request<Mutated<RingGroup>>(`/ring-groups/${id}`, { method: 'PATCH', body: payload }),
  deleteRingGroup: (id: string) => request<void>(`/ring-groups/${id}`, { method: 'DELETE' }),

  listQueues: () => request('/queues'),
  createQueue: (payload: CreateQueuePayload) => request<Mutated<Queue>>('/queues', { method: 'POST', body: payload }),
  updateQueue: (id: string, payload: UpdateQueuePayload) => request<Mutated<Queue>>(`/queues/${id}`, { method: 'PATCH', body: payload }),
  deleteQueue: (id: string) => request<void>(`/queues/${id}`, { method: 'DELETE' }),

  listAudio: () => request('/audio'),
  uploadAudio: (file: File, name: string) => {
    const form = new FormData();
    form.set('file', file);
    form.set('name', name);
    return requestMultipart<{ item: Audio }>('/audio', form);
  },
  deleteAudio: (id: string) => request<void>(`/audio/${id}`, { method: 'DELETE' }),
  fetchAudio: (id: string) => requestBlob(`/audio/${id}/stream`),

  listOutboundRoutes: () => request('/outbound-routes'),
  createOutboundRoute: (payload: CreateOutboundRoutePayload) => request<Mutated<OutboundRoute>>('/outbound-routes', { method: 'POST', body: payload }),
  updateOutboundRoute: (id: string, payload: UpdateOutboundRoutePayload) => request<Mutated<OutboundRoute>>(`/outbound-routes/${id}`, { method: 'PATCH', body: payload }),
  deleteOutboundRoute: (id: string) => request<void>(`/outbound-routes/${id}`, { method: 'DELETE' }),
  reorderOutboundRoutes: (payload: OutboundOrderPayload) => request<{ items: OutboundRoute[] }>('/outbound-routes/order', { method: 'PUT', body: payload }),
  simulateOutboundRoute: (params: OutboundSimulateParams) => request<OutboundSimulateResult>('/outbound-routes/simulate', { method: 'POST', body: params }),

  sipSettings: () => request<SipSettings>('/settings/sip'),
  updateSipSettings: (payload: UpdateSipSettingsPayload) => request<Mutated<SipSettings>>('/settings/sip', { method: 'PATCH', body: payload }),
  restartAsterisk: (force = false) => request<RestartAsteriskResult>(`/settings/sip/restart${qs({ force: force ? 'true' : undefined })}`, { method: 'POST' }),

  dashboard: () => request<DashboardResult>('/dashboard'),

  listAudit: (params: ListAuditParams) => request<Paged<AuditEntry>>(`/audit${qs(params)}`),

  revisionDetail: (id: string) => request<RevisionDetail>(`/config/revisions/${id}`),
  revisionDiff: (id: string, against: RevisionDiffAgainst) => request<RevisionDiff>(`/config/revisions/${id}/diff${qs({ against })}`),
  restoreRevision: (id: string) => request<RestoreRevisionResult>(`/config/revisions/${id}/restore`, { method: 'POST' }),

  listMohClasses: () => request('/moh-classes'),
  createMohClass: (payload: CreateMohClassPayload) => request<Mutated<MohClass>>('/moh-classes', { method: 'POST', body: payload }),
  updateMohClass: (id: string, payload: UpdateMohClassPayload) => request<Mutated<MohClass>>(`/moh-classes/${id}`, { method: 'PATCH', body: payload }),
  deleteMohClass: (id: string) => request<void>(`/moh-classes/${id}`, { method: 'DELETE' }),

  listVoicemailBoxes: (params: ListVoicemailBoxesParams) => request<{ items: VoicemailBox[] }>(`/voicemail-boxes${qs(params)}`),
  createVoicemailBox: (payload: CreateVoicemailBoxPayload) => request<Mutated<VoicemailBox>>('/voicemail-boxes', { method: 'POST', body: payload }),
  updateVoicemailBox: (id: string, payload: UpdateVoicemailBoxPayload) => request<Mutated<VoicemailBox>>(`/voicemail-boxes/${id}`, { method: 'PATCH', body: payload }),
  deleteVoicemailBox: (id: string) => request<void>(`/voicemail-boxes/${id}`, { method: 'DELETE' }),
  listVoicemailMessages: (boxId: string) => request<{ items: VoicemailMessage[] }>(`/voicemail-boxes/${boxId}/messages`),
  fetchVoicemailMessageAudio: (boxId: string, msg: string) => requestBlob(`/voicemail-boxes/${boxId}/messages/${msg}/audio`),
  markVoicemailMessageHeard: (boxId: string, msg: string) => request<void>(`/voicemail-boxes/${boxId}/messages/${msg}/heard`, { method: 'POST' }),
  deleteVoicemailMessage: (boxId: string, msg: string) => request<void>(`/voicemail-boxes/${boxId}/messages/${msg}`, { method: 'DELETE' }),

  notifySettings: () => request<NotifySettings>('/settings/notify'),
  updateNotifySettings: (payload: UpdateNotifySettingsPayload) => request<NotifySettings>('/settings/notify', { method: 'PATCH', body: payload }),
  testNotify: (payload: NotifyTestPayload) => request<NotifyTestResult>('/settings/notify/test', { method: 'POST', body: payload }),

  sipTls: () => request<SipTls>('/settings/sip/tls'),
  uploadSipTlsCertificate: (cert: File, key: File, chain?: File) => {
    const form = new FormData();
    form.set('cert', cert);
    form.set('key', key);
    if (chain) form.set('chain', chain);
    return requestMultipart<SipTls>('/settings/sip/tls/certificate', form);
  },
  createSelfSignedSipTls: (payload: SelfSignedTlsPayload) => request<SipTls>('/settings/sip/tls/self-signed', { method: 'POST', body: payload }),

  // M2a — qarang ../../replica/m2a-contract.md
  listFeatureCodes: () => request<{ items: FeatureCode[] }>('/feature-codes'),
  updateFeatureCode: (feature: string, payload: UpdateFeatureCodePayload) => request<Mutated<FeatureCode>>(`/feature-codes/${feature}`, { method: 'PATCH', body: payload }),
  resetFeatureCode: (feature: string) => request<Mutated<FeatureCode>>(`/feature-codes/${feature}/reset`, { method: 'POST' }),

  listConferences: () => request<{ items: Conference[] }>('/conferences'),
  createConference: (payload: CreateConferencePayload) => request<Mutated<Conference>>('/conferences', { method: 'POST', body: payload }),
  updateConference: (id: string, payload: UpdateConferencePayload) => request<Mutated<Conference>>(`/conferences/${id}`, { method: 'PATCH', body: payload }),
  deleteConference: (id: string) => request<void>(`/conferences/${id}`, { method: 'DELETE' }),

  listBlacklist: (params: ListBlacklistParams) => request<{ items: BlacklistEntry[] }>(`/blacklist${qs(params)}`),
  createBlacklistEntry: (payload: CreateBlacklistPayload) => request<{ item: BlacklistEntry }>('/blacklist', { method: 'POST', body: payload }),
  deleteBlacklistEntry: (number: string) => request<void>(`/blacklist/${encodeURIComponent(number)}`, { method: 'DELETE' }),

  parking: () => request<Parking>('/parking'),

  // M2b §1 — navbat a'zosi real holati
  updateQueueMember: (queueId: string, extensionId: string, payload: UpdateQueueMemberPayload) =>
    request<{ item: QueueMember }>(`/queues/${queueId}/members/${extensionId}`, { method: 'PATCH', body: payload }),
  queueMemberAction: (queueId: string, extensionId: string, action: QueueMemberAction, payload?: QueueMemberActionPayload) =>
    request<{ item: QueueMember }>(`/queues/${queueId}/members/${extensionId}/${action}`, { method: 'POST', body: payload ?? {} }),

  // M2b §2 — jonli monitoring (S29)
  live: () => request<LiveSnapshot>('/live'),
  liveSpy: (payload: LiveSpyPayload) => request<LiveSpyResult>('/live/spy', { method: 'POST', body: payload }),

  // M2b §3 — foydalanuvchilar (S31)
  listUsers: () => request<{ items: ManagedUser[] }>('/users'),
  createUser: (payload: CreateUserPayload) => request<{ item: ManagedUser }>('/users', { method: 'POST', body: payload }),
  updateUser: (id: string, payload: UpdateUserPayload) => request<{ item: ManagedUser }>(`/users/${id}`, { method: 'PATCH', body: payload }),
  deleteUser: (id: string) => request<void>(`/users/${id}`, { method: 'DELETE' }),
  changePassword: (payload: ChangePasswordPayload) => request<{ access: string; refresh: string }>('/auth/change-password', { method: 'POST', body: payload }),

  // M7 — rollar muharriri (qarang ../../replica/m7-roles-contract.md §2)
  listRoles: () => request<{ items: RoleOut[] }>('/roles'),
  createRole: (payload: CreateRolePayload) => request<{ item: RoleOut }>('/roles', { method: 'POST', body: payload }),
  updateRole: (id: string, payload: UpdateRolePayload) => request<{ item: RoleOut }>(`/roles/${id}`, { method: 'PATCH', body: payload }),
  deleteRole: (id: string) => request<void>(`/roles/${id}`, { method: 'DELETE' }),

  // M2b §4 — mening kabinetim (S30)
  meOverview: () => request<MeOverview>('/me/overview'),
  patchMeExtension: (payload: PatchMeExtensionPayload) => request<{ item: MeOverview['extension'] }>('/me/extension', { method: 'PATCH', body: payload }),
  // `Cache-Control: no-store` serverda qo'yiladi — bu yerda qo'shimcha ish yo'q.
  meSoftphone: () => request<SoftphoneInfo>('/me/softphone'),
  meSoftphoneStatus: () => request<void>('/me/softphone/status'),
  meQueueAction: (queueId: string, action: QueueMemberAction, payload?: QueueMemberActionPayload) =>
    request<{ item: MeOverview['queues'][number] }>(`/me/queues/${queueId}/${action}`, { method: 'POST', body: payload ?? {} }),
  meCalls: (params: ListCallsParams) => request<Paged<Call>>(`/me/calls${callsQs(params)}`),
  meVoicemailMessages: () => request<{ items: VoicemailMessage[] }>('/me/voicemail'),
  meVoicemailAudio: (msg: string) => requestBlob(`/me/voicemail/${msg}/audio`),
  meVoicemailHeard: (msg: string) => request<void>(`/me/voicemail/${msg}/heard`, { method: 'POST' }),
  meVoicemailDelete: (msg: string) => request<void>(`/me/voicemail/${msg}`, { method: 'DELETE' }),

  // M2b §5 — analitika (S13)
  reportsSummary: (params: ReportRangeParams) => request<ReportsSummary>(`/reports/summary${qs(params)}`),
  reportsQueues: (params: ReportRangeParams) => request<{ items: ReportsQueueRow[] }>(`/reports/queues${qs(params)}`),
  reportsAgents: (params: ReportRangeParams) => request<{ items: ReportsAgentRow[] }>(`/reports/agents${qs(params)}`),
  reportsHourly: (params: ReportRangeParams) => request<{ items: ReportsHourlyRow[] }>(`/reports/hourly${qs(params)}`),
  reportsDaily: (params: ReportRangeParams) => request<{ items: ReportsDailyRow[] }>(`/reports/daily${qs(params)}`),

  // M2c §1 — xavfsizlik sozlamalari
  securitySettings: () => request<SecuritySettings>('/security/settings'),
  updateSecuritySettings: (payload: UpdateSecuritySettingsPayload) => request<Mutated<SecuritySettings>>('/security/settings', { method: 'PATCH', body: payload }),

  // M2c §2 — SIP hujum himoyasi (S33)
  securityBans: () => request<{ items: IpBan[] }>('/security/bans'),
  createSecurityBan: (payload: CreateBanPayload) => request<Mutated<IpBan>>('/security/bans', { method: 'POST', body: payload }),
  deleteSecurityBan: (id: string) => request<{ apply: ApplyResult }>(`/security/bans/${id}`, { method: 'DELETE' }),
  securityStats: (params: SecurityStatsParams) => request<SecurityStats>(`/security/stats${qs(params)}`),
  securityEvents: (params: ListSecurityEventsParams) => request<{ items: SecurityEvent[] }>(`/security/events${qs(params)}`),

  // M2c §3 — toll-fraud
  tollBlocks: () => request<{ items: TollBlock[] }>('/security/toll-blocks'),
  unblockToll: (extensionId: string) => request<{ item: { extension_id: string; number: string } }>(`/security/toll-blocks/${extensionId}/unblock`, { method: 'POST' }),

  // M2c §4 — ogohlantirishlar (Telegram)
  alertSettings: () => request<AlertSettings>('/settings/alerts'),
  updateAlertSettings: (payload: UpdateAlertSettingsPayload) => request<AlertSettings>('/settings/alerts', { method: 'PATCH', body: payload }),
  testAlert: () => request<TestAlertResult>('/settings/alerts/test', { method: 'POST' }),
  alertLog: (params: ListAlertLogParams) => request<{ items: AlertLogEntry[] }>(`/alerts${qs(params)}`),

  // M3b §1 — qo'ngiroq yozuvlari
  fetchRecordingAudio: (id: string) => requestBlob(`/recordings/${id}/audio`),
  deleteRecording: (id: string) => request<void>(`/recordings/${id}`, { method: 'DELETE' }),

  // M3b §4 — API kalitlari
  listApiKeys: () => request<{ items: ApiKey[] }>('/integrations/api-keys'),
  createApiKey: (payload: CreateApiKeyPayload) => request<CreatedApiKey>('/integrations/api-keys', { method: 'POST', body: payload }),
  revokeApiKey: (id: string) => request<void>(`/integrations/api-keys/${id}`, { method: 'DELETE' }),

  // M3b §3 — vebhuklar
  listWebhooks: () => request<{ items: Webhook[] }>('/integrations/webhooks'),
  createWebhook: (payload: CreateWebhookPayload) => request<CreatedWebhook>('/integrations/webhooks', { method: 'POST', body: payload }),
  updateWebhook: (id: string, payload: UpdateWebhookPayload) => request<Mutated<Webhook>>(`/integrations/webhooks/${id}`, { method: 'PATCH', body: payload }),
  deleteWebhook: (id: string) => request<void>(`/integrations/webhooks/${id}`, { method: 'DELETE' }),
  rotateWebhookSecret: (id: string) => request<RotatedWebhookSecret>(`/integrations/webhooks/${id}/rotate-secret`, { method: 'POST' }),
  testWebhook: (id: string) => request<TestWebhookResult>(`/integrations/webhooks/${id}/test`, { method: 'POST' }),
  webhookDeliveries: (id: string, params: ListDeliveriesParams) => request<{ items: WebhookDelivery[] }>(`/integrations/webhooks/${id}/deliveries${qs(params)}`),
  replayDelivery: (id: string) => request<void>(`/integrations/deliveries/${id}/replay`, { method: 'POST' }),

  // M3b §5 — CRM (Bitrix24 / amoCRM)
  bitrix24Config: () => request<BitrixConfigResult>('/integrations/crm/bitrix24'),
  updateBitrix24Config: (payload: UpdateBitrixPayload) => request<BitrixConfigResult>('/integrations/crm/bitrix24', { method: 'PUT', body: payload }),
  amoCrmConfig: () => request<AmoConfigResult>('/integrations/crm/amocrm'),
  updateAmoCrmConfig: (payload: UpdateAmoPayload) => request<AmoConfigResult>('/integrations/crm/amocrm', { method: 'PUT', body: payload }),
  testCrm: (provider: CrmProvider) => request<CrmTestResult>(`/integrations/crm/${provider}/test`, { method: 'POST' }),
  updateCrmUserMap: (provider: CrmProvider, payload: UpdateCrmUserMapPayload) => request<{ items: CrmUserMapEntry[] }>(`/integrations/crm/${provider}/user-map`, { method: 'PUT', body: payload }),

  // 1C — tayyor namunalar (../../replica/m3b-contract.md §5 — "1C")
  listOneCSamples: () => request<{ items: OneCSample[] }>('/integrations/1c/samples'),
  fetchOneCSample: (name: string) => requestBlob(`/integrations/1c/samples/${encodeURIComponent(name)}`),

  // M3b §6 — sozlamalar
  integrationsSettings: () => request<IntegrationsSettings>('/settings/integrations'),
  updateIntegrationsSettings: (payload: UpdateIntegrationsSettingsPayload) => request<IntegrationsSettings>('/settings/integrations', { method: 'PATCH', body: payload }),
  recordingSettings: () => request<RecordingSettings>('/settings/recording'),
  updateRecordingSettings: (payload: UpdateRecordingSettingsPayload) => request<RecordingSettings>('/settings/recording', { method: 'PATCH', body: payload }),

  // M4a — qarang ../../replica/m4a-contract.md (S35 «Qurilmalar»)
  listDevices: (params: ListDevicesParams) => request<{ items: Device[] }>(`/devices${qs(params)}`),
  createDevice: (payload: CreateDevicePayload) => request<{ item: Device }>('/devices', { method: 'POST', body: payload }),
  updateDevice: (id: string, payload: UpdateDevicePayload) => request<{ item: Device }>(`/devices/${id}`, { method: 'PATCH', body: payload }),
  deleteDevice: (id: string) => request<void>(`/devices/${id}`, { method: 'DELETE' }),
  deviceKeys: (id: string) => request<{ items: DeviceKey[] }>(`/devices/${id}/keys`),
  updateDeviceKeys: (id: string, payload: UpdateDeviceKeysPayload) => request<{ item: Device }>(`/devices/${id}/keys`, { method: 'PUT', body: payload }),
  resyncDevice: (id: string) => request<ResyncDeviceResult>(`/devices/${id}/resync`, { method: 'POST' }),
  deviceConfig: (id: string) => request<DeviceConfigResult>(`/devices/${id}/config`),
  discoveredDevices: () => request<{ items: DiscoveredDevice[] }>('/devices/discovered'),
  assignDiscoveredDevice: (mac: string, payload: AssignDiscoveredDevicePayload) =>
    request<{ item: Device }>(`/devices/discovered/${mac}/assign`, { method: 'POST', body: payload }),
  deleteDiscoveredDevice: (mac: string) => request<void>(`/devices/discovered/${mac}`, { method: 'DELETE' }),
  deviceModels: () => request<{ items: DeviceModel[] }>('/devices/models'),
  provisionRequests: (params: ListProvisionRequestsParams) => request<{ items: ProvisionRequest[] }>(`/devices/requests${qs(params)}`),
  provisioningSettings: () => request<ProvisioningSettings>('/settings/provisioning'),
  updateProvisioningSettings: (payload: UpdateProvisioningSettingsPayload) => request<ProvisioningSettings>('/settings/provisioning', { method: 'PATCH', body: payload }),
  rotateProvisioningToken: () => request<RotateProvisioningTokenResult>('/settings/provisioning/rotate-token', { method: 'POST' }),

  // M4b — qarang ../../replica/m4b-contract.md (S34 «Zaxira»)
  listBackups: () => request<{ items: Backup[] }>('/backups'),
  createBackup: (payload: CreateBackupPayload) => request<{ job: BackupJob }>('/backups', { method: 'POST', body: payload }),
  backupDetail: (id: string) => request<{ item: Backup }>(`/backups/${id}`),
  deleteBackup: (id: string) => request<void>(`/backups/${id}`, { method: 'DELETE' }),
  downloadBackup: (id: string) => requestBlob(`/backups/${id}/download`),
  fetchBackupCopy: (id: string) => request<{ item: Backup }>(`/backups/${id}/fetch`, { method: 'POST' }),
  uploadBackup: (file: File) => {
    const form = new FormData();
    form.set('file', file);
    return requestMultipart<{ item: Backup }>('/backups/upload', form);
  },
  inspectBackup: (id: string, payload: InspectBackupPayload) => request<InspectBackupResult>(`/backups/${id}/inspect`, { method: 'POST', body: payload }),
  restoreBackup: (id: string, payload: RestoreBackupPayload) => request<{ job: BackupJob }>(`/backups/${id}/restore`, { method: 'POST', body: payload }),
  backupJob: (id: string) => request<BackupJobState>(`/backups/jobs/${id}`),
  listRestores: () => request<{ items: RestoreJob[] }>('/backups/restores'),
  backupSettings: () => request<BackupSettings>('/settings/backup'),
  updateBackupSettings: (payload: UpdateBackupSettingsPayload) => request<BackupSettings>('/settings/backup', { method: 'PUT', body: payload }),
  updateBackupPassphrase: (payload: UpdateBackupPassphrasePayload) => request<{ ok: true }>('/settings/backup/passphrase', { method: 'PUT', body: payload }),
  testBackupTarget: (payload: TestBackupTargetPayload) => request<TestBackupTargetResult>(`/settings/backup/targets/${payload.target}/test`, { method: 'POST' }),
  trustSftpHostKey: (payload: TrustSftpHostKeyPayload) => request<{ ok: true }>('/settings/backup/targets/sftp/trust', { method: 'POST', body: payload }),

  // M5a — qarang ../../replica/m5a-contract.md (S36 «Ko'chirish»)
  uploadMigrationBundle: (file: File) => {
    const form = new FormData();
    form.set('file', file);
    return requestMultipart<{ item: MigrationJob }>('/migration/freepbx/upload', form);
  },
  testMigrationSsh: (payload: SshTestPayload) => request<SshTestResult>('/migration/freepbx/ssh/test', { method: 'POST', body: payload }),
  fetchMigrationSsh: (payload: SshFetchPayload) => request<{ item: MigrationJob }>('/migration/freepbx/ssh/fetch', { method: 'POST', body: payload }),
  analyzeMigrationJob: (id: string) => request<{ item: MigrationJob }>(`/migration/freepbx/jobs/${id}/analyze`, { method: 'POST' }),
  migrationJob: (id: string) => request<{ item: MigrationJob }>(`/migration/freepbx/jobs/${id}`),
  listMigrationJobs: () => request<{ items: MigrationJob[] }>('/migration/freepbx/jobs'),
  migrationPlan: (id: string, params: ListMigrationPlanParams) =>
    request<{ items: MigrationPlanItem[]; total: number }>(`/migration/freepbx/jobs/${id}/plan${qs(params)}`),
  migrationIgnored: (id: string) => request<{ items: MigrationIgnoredItem[] }>(`/migration/freepbx/jobs/${id}/ignored`),
  migrationWarnings: (id: string) => request<{ items: MigrationWarning[] }>(`/migration/freepbx/jobs/${id}/warnings`),
  updateMigrationPlan: (id: string, payload: PatchMigrationPlanPayload) =>
    request<{ item: MigrationJob }>(`/migration/freepbx/jobs/${id}/plan`, { method: 'PATCH', body: payload }),
  applyMigrationJob: (id: string, payload: ApplyMigrationPayload) =>
    request<{ item: MigrationJob }>(`/migration/freepbx/jobs/${id}/apply`, { method: 'POST', body: payload }),
  deleteMigrationJob: (id: string) => request<void>(`/migration/freepbx/jobs/${id}`, { method: 'DELETE' }),
  migrationReport: (id: string) => requestBlob(`/migration/freepbx/jobs/${id}/report`),
  migrationExportScript: () => requestBlob('/migration/freepbx/export-script'),

  // M5b — qarang ../../replica/m5b-contract.md
  followMe: (target: FollowMeTarget) => request<FollowMeInfo>(`${ownerPath(target)}/follow-me`),
  updateFollowMe: (target: FollowMeTarget, payload: UpdateFollowMePayload) =>
    request<FollowMeInfo>(`${ownerPath(target)}/follow-me`, { method: 'PUT', body: payload }),
  createQrProvisioning: (target: FollowMeTarget) => request<QrProvisioning>(`${ownerPath(target)}/qr-provisioning`, { method: 'POST' }),

  // M6 — qarang ../../replica/m6-contract.md
  listCampaigns: () => request<{ items: Campaign[] }>('/campaigns'),
  getCampaign: (id: string) => request<{ item: Campaign }>(`/campaigns/${id}`),
  createCampaign: (payload: CreateCampaignPayload) => request<{ item: Campaign }>('/campaigns', { method: 'POST', body: payload }),
  updateCampaign: (id: string, payload: UpdateCampaignPayload) =>
    request<{ item: Campaign }>(`/campaigns/${id}`, { method: 'PATCH', body: payload }),
  deleteCampaign: (id: string) => request<void>(`/campaigns/${id}`, { method: 'DELETE' }),
  campaignAction: (id: string, action: CampaignAction) => request<{ item: Campaign }>(`/campaigns/${id}/${action}`, { method: 'POST' }),
  importCampaignContacts: (id: string, payload: ImportCampaignContactsPayload) =>
    request<ImportCampaignContactsResult>(`/campaigns/${id}/contacts/import`, { method: 'POST', body: payload }),
  listCampaignContacts: (id: string, params: ListCampaignContactsParams) =>
    request<{ items: CampaignContact[]; total: number }>(`/campaigns/${id}/contacts${qs(params)}`),
  exportCampaignCsv: (id: string) => requestBlob(`/campaigns/${id}/export.csv`),

  // Tizim holati (status) — pbx-klon vazifa (2026-11-02)
  systemStatus: () => request<SystemStatus>('/system/status'),
  previewCleanup: (payload: CleanupIn) => request<CleanupResult>('/system/cleanup/preview', { method: 'POST', body: payload }),
  cleanup: (payload: CleanupIn) => request<CleanupResult>('/system/cleanup', { method: 'POST', body: payload }),

  // M8 — qarang ../../replica/m8-network-contract.md
  networkState: () => request<NetworkStateOut>('/network/state'),
  validateNetwork: (payload: NetworkConfigIn) => request<NetworkValidateResult>('/network/validate', { method: 'POST', body: payload }),
  applyNetwork: (payload: NetworkConfigIn) => request<NetworkStateOut>('/network/apply', { method: 'POST', body: payload }),
  confirmNetwork: (pendingId: string) => request<NetworkStateOut>('/network/confirm', { method: 'POST', body: { pending_id: pendingId } }),
  rollbackNetwork: (pendingId: string) => request<NetworkStateOut>('/network/rollback', { method: 'POST', body: { pending_id: pendingId } }),

  // M9 A1 — qarang ../../replica/m9-freepbx-gaps-contract.md §A1 («E'lon»)
  listAnnouncements: () => request<Paged<Announcement>>('/announcements'),
  createAnnouncement: (payload: CreateAnnouncementPayload) => request<Mutated<Announcement>>('/announcements', { method: 'POST', body: payload }),
  updateAnnouncement: (id: string, payload: UpdateAnnouncementPayload) => request<Mutated<Announcement>>(`/announcements/${id}`, { method: 'PATCH', body: payload }),
  deleteAnnouncement: (id: string) => request<void>(`/announcements/${id}`, { method: 'DELETE' }),

  // M9 A2 — qarang §A2 («Boshqa manzillar» / «Maxsus kodlar»)
  listMiscDestinations: () => request<Paged<MiscDestination>>('/misc-destinations'),
  createMiscDestination: (payload: CreateMiscDestinationPayload) => request<Mutated<MiscDestination>>('/misc-destinations', { method: 'POST', body: payload }),
  updateMiscDestination: (id: string, payload: UpdateMiscDestinationPayload) => request<Mutated<MiscDestination>>(`/misc-destinations/${id}`, { method: 'PATCH', body: payload }),
  deleteMiscDestination: (id: string) => request<void>(`/misc-destinations/${id}`, { method: 'DELETE' }),
  listMiscApplications: () => request<Paged<MiscApplication>>('/misc-applications'),
  createMiscApplication: (payload: CreateMiscApplicationPayload) => request<Mutated<MiscApplication>>('/misc-applications', { method: 'POST', body: payload }),
  updateMiscApplication: (id: string, payload: UpdateMiscApplicationPayload) => request<Mutated<MiscApplication>>(`/misc-applications/${id}`, { method: 'PATCH', body: payload }),
  deleteMiscApplication: (id: string) => request<void>(`/misc-applications/${id}`, { method: 'DELETE' }),

  // M9 A3 — qarang §A3 («Parkovka»)
  parkingSettings: () => request<ParkingSettings>('/parking/settings'),
  updateParkingSettings: (payload: UpdateParkingSettingsPayload) => request<Mutated<ParkingSettings>>('/parking/settings', { method: 'PUT', body: payload }),
  parkedCalls: () => request<Paged<ParkingCall>>('/parking/calls'),

  // M9 A4 — qarang §A4 («Paging / Intercom»)
  listPageGroups: () => request<Paged<PageGroup>>('/page-groups'),
  createPageGroup: (payload: CreatePageGroupPayload) => request<Mutated<PageGroup>>('/page-groups', { method: 'POST', body: payload }),
  updatePageGroup: (id: string, payload: UpdatePageGroupPayload) => request<Mutated<PageGroup>>(`/page-groups/${id}`, { method: 'PATCH', body: payload }),
  deletePageGroup: (id: string) => request<void>(`/page-groups/${id}`, { method: 'DELETE' }),

  // M9 B1 — qarang §B1 («PIN to'plamlari»)
  listPinSets: () => request<Paged<PinSet>>('/pin-sets'),
  createPinSet: (payload: CreatePinSetPayload) => request<Mutated<PinSet>>('/pin-sets', { method: 'POST', body: payload }),
  updatePinSet: (id: string, payload: UpdatePinSetPayload) => request<Mutated<PinSet>>(`/pin-sets/${id}`, { method: 'PATCH', body: payload }),
  deletePinSet: (id: string) => request<void>(`/pin-sets/${id}`, { method: 'DELETE' }),
  listPinSetPins: (id: string) => request<{ items: PinSetPin[] }>(`/pin-sets/${id}/pins`),
  addPinSetPins: (id: string, payload: AddPinsPayload) => request<{ items: PinSetPin[] }>(`/pin-sets/${id}/pins`, { method: 'POST', body: payload }),
  deletePinSetPin: (id: string, pinId: string) => request<void>(`/pin-sets/${id}/pins/${pinId}`, { method: 'DELETE' }),

  // M9 B2 — qarang §B2 («Telefon kitobi» + CID Lookup)
  listPhonebook: (params: ListPhonebookParams) => request<Paged<Contact>>(`/phonebook${qs(params)}`),
  createContact: (payload: CreateContactPayload) => request<Mutated<Contact>>('/phonebook', { method: 'POST', body: payload }),
  updateContact: (id: string, payload: UpdateContactPayload) => request<Mutated<Contact>>(`/phonebook/${id}`, { method: 'PATCH', body: payload }),
  deleteContact: (id: string) => request<void>(`/phonebook/${id}`, { method: 'DELETE' }),
  exportPhonebookCsv: () => requestBlob('/phonebook/export.csv'),
  importPhonebookCsv: (params: ImportPhonebookParams) => {
    const form = new FormData();
    form.append('file', params.file);
    form.append('dry_run', String(params.dry_run));
    return requestMultipart<ImportPhonebookResult>('/phonebook/import', form);
  },
  listCidSources: () => request<Paged<CidSource>>('/cid-sources'),
  createCidSource: (payload: CreateCidSourcePayload) => request<Mutated<CidSource>>('/cid-sources', { method: 'POST', body: payload }),
  updateCidSource: (id: string, payload: UpdateCidSourcePayload) => request<Mutated<CidSource>>(`/cid-sources/${id}`, { method: 'PATCH', body: payload }),
  deleteCidSource: (id: string) => request<void>(`/cid-sources/${id}`, { method: 'DELETE' }),
  testCidSource: (id: string, number: string) => request<CidSourceTestResult>(`/cid-sources/${id}/test`, { method: 'POST', body: { number } }),

  // M9 B4 — qarang §B4 (ichki raqamlar CSV import/eksport)
  exportExtensionsCsv: () => requestBlob('/extensions/export.csv'),
  importExtensionsCsv: (params: ImportExtensionsParams) => {
    const form = new FormData();
    form.append('file', params.file);
    form.append('dry_run', String(params.dry_run));
    return requestMultipart<ImportExtensionsResult>('/extensions/import', form);
  },
};
