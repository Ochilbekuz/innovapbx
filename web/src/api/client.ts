import type {
  AuditEntry, AuthResult, Audio, BlacklistEntry, Call, Conference, ConfigRevision, CreateBlacklistPayload,
  CreateConferencePayload, CreateExtensionPayload, CreateHolidayPayload,
  CreateInboundRoutePayload, CreateIvrPayload, CreateMohClassPayload, CreateOutboundRoutePayload, CreateQueuePayload,
  CreateRingGroupPayload, CreateTimeConditionPayload, CreateTimeGroupPayload, CreateTrunkPayload,
  CreateVoicemailBoxPayload, DashboardResult, FeatureCode,
  Extension, FlowResult, Holiday, ImportUzHolidaysPayload, ImportUzHolidaysResult, InboundRoute, Ivr, ListAuditParams,
  ListBlacklistParams,
  ListCallsParams, ListExtensionsParams, ListTargetsParams, ListVoicemailBoxesParams, MohClass, NetworkConfigIn,
  NetworkStateOut, NetworkValidateResult, NotifySettings,
  NotifyTestPayload, NotifyTestResult, NumbersFreeParams, OutboundOrderPayload,
  OutboundRoute, OutboundSimulateParams, OutboundSimulateResult, OverrideTimeConditionPayload, Paged, Parking, Queue,
  QueueMember,
  RestartAsteriskResult, RestoreRevisionResult, RevisionDetail, RevisionDiff, RevisionDiffAgainst, RingGroup, RotateSecretResult,
  SelfSignedTlsPayload, SetupPayload, SipCredentials, SipSettings, SipTls, SystemHealth, Target, TimeCondition,
  TimeGroup, Trunk, TrunkTestResult, UpdateConferencePayload, UpdateExtensionPayload, UpdateFeatureCodePayload,
  UpdateHolidayPayload, UpdateInboundRoutePayload,
  UpdateIvrPayload, UpdateMePayload, UpdateMohClassPayload, UpdateNotifySettingsPayload,
  UpdateOutboundRoutePayload, UpdateQueuePayload, UpdateRingGroupPayload, UpdateSipSettingsPayload,
  UpdateTimeConditionPayload, UpdateTimeGroupPayload, UpdateTrunkPayload, UpdateVoicemailBoxPayload, Usage, User,
  VoicemailBox, VoicemailMessage,
  // M2b — qarang ../../replica/m2b-contract.md
  ChangePasswordPayload, CreateUserPayload, LiveSnapshot, LiveSpyPayload, LiveSpyResult, ManagedUser, MeOverview,
  PatchMeExtensionPayload, QueueMemberAction, QueueMemberActionPayload, ReportRangeParams, ReportsAgentRow,
  SoftphoneInfo,
  ReportsDailyRow, ReportsHourlyRow, ReportsQueueRow, ReportsSummary, UpdateQueueMemberPayload, UpdateUserPayload,
  // M2c — qarang ../../replica/m2c-contract.md
  AlertLogEntry, AlertSettings, CreateBanPayload, IpBan, ListAlertLogParams, ListSecurityEventsParams,
  SecurityEvent, SecuritySettings, SecurityStats, SecurityStatsParams, TestAlertResult, TollBlock,
  UpdateAlertSettingsPayload, UpdateSecuritySettingsPayload,
  // M3b — qarang ../../replica/m3b-contract.md
  AmoConfigResult, ApiKey, BitrixConfigResult, CreateApiKeyPayload, CreateWebhookPayload, CreatedApiKey,
  CreatedWebhook, CrmProvider, CrmTestResult, CrmUserMapEntry, IntegrationsSettings, ListDeliveriesParams, OneCSample,
  RecordingSettings, RotatedWebhookSecret, TestWebhookResult, UpdateAmoPayload, UpdateBitrixPayload,
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
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  Announcement, CreateAnnouncementPayload, UpdateAnnouncementPayload,
  MiscDestination, CreateMiscDestinationPayload, UpdateMiscDestinationPayload,
  MiscApplication, CreateMiscApplicationPayload, UpdateMiscApplicationPayload,
  ParkingSettings, UpdateParkingSettingsPayload, ParkingCall,
  PageGroup, CreatePageGroupPayload, UpdatePageGroupPayload,
  PinSet, CreatePinSetPayload, UpdatePinSetPayload, PinSetPin, AddPinsPayload,
  Contact, CreateContactPayload, UpdateContactPayload, ListPhonebookParams, ImportPhonebookResult, ImportPhonebookParams,
  CidSource, CreateCidSourcePayload, UpdateCidSourcePayload, CidSourceTestResult,
  ImportExtensionsResult, ImportExtensionsParams,
  // M10 C — qarang ../../replica/m10-onlinepbx-contract.md (Bo'lak C)
  CallbackWidget, CreateCallbackWidgetPayload, UpdateCallbackWidgetPayload,
  CallbackRequest, ListCallbackRequestsParams,
  MissedCallRule, CreateMissedCallRulePayload, UpdateMissedCallRulePayload, MissedCallRuleMutated, TestMissedCallRuleResult,
  MissedCallNotice, ListMissedCallNoticesParams,
  TtsSettings, TtsSettingsMutated, UpdateTtsSettingsPayload, TtsTestResult, CreateTtsAudioPayload, TtsPreviewPayload,
  QaChecklist, CreateQaChecklistPayload, UpdateQaChecklistPayload,
  QaEvaluation, CreateQaEvaluationPayload, UpdateQaEvaluationPayload, ListQaEvaluationsParams,
  QaSummary,
  TotpSetup, TotpEnablePayload, TotpEnableResult, TotpDisablePayload, TotpRecoveryCodesPayload,
  TotpRecoveryCodesResult, LoginTotpPayload,
  // M11 — qarang ../../replica/m11-update-contract.md
  StartSystemUpdatePayload, SystemUpdateLog, SystemUpdateOut,
  // M12 B1/B2/B3 — qarang ../../replica/m12-contract.md
  TimeConfigIn, TimeStateOut, PowerActionIn, PowerActionOut, PowerStatusOut,
  FirewallConfigIn, FirewallStateOut, FirewallValidateOut,
  // M12 A1/A2 — qarang ../../replica/m12-contract.md §A1/§A2
  DayNight, CreateDayNightPayload, UpdateDayNightPayload, Disa, CreateDisaPayload, UpdateDisaPayload,
} from './types';
import type { ApplyResult } from './types';

export type Mutated<T> = { item: T; apply: ApplyResult };
export type Created<T> = { item: T; sip: SipCredentials; apply: ApplyResult };

/**
 * Backend bilan shartnoma (../../replica/m0-contract.md). `real` (fetch) va `fake` (xotira)
 * ikkisi ham shu interfeysni amalga oshiradi — ekran kodi `VITE_API` ga qaramay bir xil qoladi.
 */
export interface ApiClient {
  setupState(): Promise<{ needed: boolean }>;
  setup(payload: SetupPayload): Promise<AuthResult>;
  login(login: string, password: string): Promise<AuthResult>;
  refresh(refreshToken: string): Promise<{ access: string; refresh: string }>;
  logout(refreshToken: string): Promise<void>;
  me(): Promise<User>;
  updateMe(payload: UpdateMePayload): Promise<User>;

  listExtensions(params: ListExtensionsParams): Promise<Paged<Extension>>;
  createExtension(payload: CreateExtensionPayload): Promise<Created<Extension>>;
  updateExtension(id: string, payload: UpdateExtensionPayload): Promise<Mutated<Extension>>;
  rotateExtensionSecret(id: string): Promise<RotateSecretResult>;
  /** Admin o'z paroli bilan — siyosatga mos bo'lmasa 422 `weak_password` (field `password`). */
  setExtensionSecret(id: string, password: string): Promise<RotateSecretResult>;
  deleteExtension(id: string): Promise<void>;

  listTrunks(): Promise<{ items: Trunk[] }>;
  createTrunk(payload: CreateTrunkPayload): Promise<Mutated<Trunk>>;
  updateTrunk(id: string, payload: UpdateTrunkPayload): Promise<Mutated<Trunk>>;
  deleteTrunk(id: string): Promise<void>;
  testTrunk(id: string): Promise<TrunkTestResult>;

  listInboundRoutes(): Promise<{ items: InboundRoute[] }>;
  createInboundRoute(payload: CreateInboundRoutePayload): Promise<Mutated<InboundRoute>>;
  updateInboundRoute(id: string, payload: UpdateInboundRoutePayload): Promise<Mutated<InboundRoute>>;
  deleteInboundRoute(id: string): Promise<void>;
  listTargets(params: ListTargetsParams): Promise<{ items: Target[] }>;
  targetUsages(id: string): Promise<{ items: Usage[] }>;
  flow(inboundRouteId: string): Promise<FlowResult>;
  numbersFree(params: NumbersFreeParams): Promise<{ items: string[] }>;

  listCalls(params: ListCallsParams): Promise<Paged<Call>>;
  /** CDR kengaytirilgan qidiruv — xuddi `listCalls` bilan bir xil parametrlar, CSV fayl qaytaradi. */
  exportCallsCsv(params: ListCallsParams): Promise<Blob>;

  systemHealth(): Promise<SystemHealth>;
  configRevisions(limit?: number): Promise<{ items: ConfigRevision[] }>;

  // M1a — ../../replica/m1a-contract.md
  listTimeGroups(): Promise<{ items: TimeGroup[] }>;
  createTimeGroup(payload: CreateTimeGroupPayload): Promise<Mutated<TimeGroup>>;
  updateTimeGroup(id: string, payload: UpdateTimeGroupPayload): Promise<Mutated<TimeGroup>>;
  deleteTimeGroup(id: string): Promise<void>;

  listHolidays(): Promise<{ items: Holiday[] }>;
  createHoliday(payload: CreateHolidayPayload): Promise<Mutated<Holiday>>;
  updateHoliday(id: string, payload: UpdateHolidayPayload): Promise<Mutated<Holiday>>;
  deleteHoliday(id: string): Promise<void>;
  importUzHolidays(payload: ImportUzHolidaysPayload): Promise<ImportUzHolidaysResult>;

  listTimeConditions(): Promise<{ items: TimeCondition[] }>;
  createTimeCondition(payload: CreateTimeConditionPayload): Promise<Mutated<TimeCondition>>;
  updateTimeCondition(id: string, payload: UpdateTimeConditionPayload): Promise<Mutated<TimeCondition>>;
  deleteTimeCondition(id: string): Promise<void>;
  overrideTimeCondition(id: string, payload: OverrideTimeConditionPayload): Promise<Mutated<TimeCondition>>;

  listIvrs(): Promise<{ items: Ivr[] }>;
  createIvr(payload: CreateIvrPayload): Promise<Mutated<Ivr>>;
  updateIvr(id: string, payload: UpdateIvrPayload): Promise<Mutated<Ivr>>;
  deleteIvr(id: string): Promise<void>;

  listRingGroups(): Promise<{ items: RingGroup[] }>;
  createRingGroup(payload: CreateRingGroupPayload): Promise<Mutated<RingGroup>>;
  updateRingGroup(id: string, payload: UpdateRingGroupPayload): Promise<Mutated<RingGroup>>;
  deleteRingGroup(id: string): Promise<void>;

  listQueues(): Promise<{ items: Queue[] }>;
  createQueue(payload: CreateQueuePayload): Promise<Mutated<Queue>>;
  updateQueue(id: string, payload: UpdateQueuePayload): Promise<Mutated<Queue>>;
  deleteQueue(id: string): Promise<void>;

  listAudio(): Promise<{ items: Audio[] }>;
  uploadAudio(file: File, name: string): Promise<{ item: Audio }>;
  deleteAudio(id: string): Promise<void>;
  /** Audio fayli (8 kHz WAV) — token bilan; player Blob'dan `blob:` manzil yasaydi. */
  fetchAudio(id: string): Promise<Blob>;

  // M1b — ../../replica/m1b-contract.md
  listOutboundRoutes(): Promise<{ items: OutboundRoute[] }>;
  createOutboundRoute(payload: CreateOutboundRoutePayload): Promise<Mutated<OutboundRoute>>;
  updateOutboundRoute(id: string, payload: UpdateOutboundRoutePayload): Promise<Mutated<OutboundRoute>>;
  deleteOutboundRoute(id: string): Promise<void>;
  reorderOutboundRoutes(payload: OutboundOrderPayload): Promise<{ items: OutboundRoute[] }>;
  simulateOutboundRoute(params: OutboundSimulateParams): Promise<OutboundSimulateResult>;

  sipSettings(): Promise<SipSettings>;
  updateSipSettings(payload: UpdateSipSettingsPayload): Promise<Mutated<SipSettings>>;
  restartAsterisk(force?: boolean): Promise<RestartAsteriskResult>;

  dashboard(): Promise<DashboardResult>;

  listAudit(params: ListAuditParams): Promise<Paged<AuditEntry>>;

  revisionDetail(id: string): Promise<RevisionDetail>;
  revisionDiff(id: string, against: RevisionDiffAgainst): Promise<RevisionDiff>;
  restoreRevision(id: string): Promise<RestoreRevisionResult>;

  listMohClasses(): Promise<{ items: MohClass[] }>;
  createMohClass(payload: CreateMohClassPayload): Promise<Mutated<MohClass>>;
  updateMohClass(id: string, payload: UpdateMohClassPayload): Promise<Mutated<MohClass>>;
  deleteMohClass(id: string): Promise<void>;

  // M1c — ../../replica/m1c-contract.md
  listVoicemailBoxes(params: ListVoicemailBoxesParams): Promise<{ items: VoicemailBox[] }>;
  createVoicemailBox(payload: CreateVoicemailBoxPayload): Promise<Mutated<VoicemailBox>>;
  updateVoicemailBox(id: string, payload: UpdateVoicemailBoxPayload): Promise<Mutated<VoicemailBox>>;
  deleteVoicemailBox(id: string): Promise<void>;
  listVoicemailMessages(boxId: string): Promise<{ items: VoicemailMessage[] }>;
  fetchVoicemailMessageAudio(boxId: string, msg: string): Promise<Blob>;
  markVoicemailMessageHeard(boxId: string, msg: string): Promise<void>;
  deleteVoicemailMessage(boxId: string, msg: string): Promise<void>;

  notifySettings(): Promise<NotifySettings>;
  updateNotifySettings(payload: UpdateNotifySettingsPayload): Promise<NotifySettings>;
  testNotify(payload: NotifyTestPayload): Promise<NotifyTestResult>;

  sipTls(): Promise<SipTls>;
  uploadSipTlsCertificate(cert: File, key: File, chain?: File): Promise<SipTls>;
  createSelfSignedSipTls(payload: SelfSignedTlsPayload): Promise<SipTls>;

  // M2a — qarang ../../replica/m2a-contract.md
  listFeatureCodes(): Promise<{ items: FeatureCode[] }>;
  updateFeatureCode(feature: string, payload: UpdateFeatureCodePayload): Promise<Mutated<FeatureCode>>;
  resetFeatureCode(feature: string): Promise<Mutated<FeatureCode>>;

  listConferences(): Promise<{ items: Conference[] }>;
  createConference(payload: CreateConferencePayload): Promise<Mutated<Conference>>;
  updateConference(id: string, payload: UpdateConferencePayload): Promise<Mutated<Conference>>;
  deleteConference(id: string): Promise<void>;

  listBlacklist(params: ListBlacklistParams): Promise<{ items: BlacklistEntry[] }>;
  createBlacklistEntry(payload: CreateBlacklistPayload): Promise<{ item: BlacklistEntry }>;
  deleteBlacklistEntry(number: string): Promise<void>;

  parking(): Promise<Parking>;

  // M2b §1 — navbat a'zosi real holati (../../replica/m2b-contract.md §1)
  updateQueueMember(queueId: string, extensionId: string, payload: UpdateQueueMemberPayload): Promise<{ item: QueueMember }>;
  queueMemberAction(queueId: string, extensionId: string, action: QueueMemberAction, payload?: QueueMemberActionPayload): Promise<{ item: QueueMember }>;

  // M2b §2 — jonli monitoring (S29)
  live(): Promise<LiveSnapshot>;
  liveSpy(payload: LiveSpyPayload): Promise<LiveSpyResult>;

  // M2b §3 — foydalanuvchilar (S31)
  listUsers(): Promise<{ items: ManagedUser[] }>;
  createUser(payload: CreateUserPayload): Promise<{ item: ManagedUser }>;
  updateUser(id: string, payload: UpdateUserPayload): Promise<{ item: ManagedUser }>;
  deleteUser(id: string): Promise<void>;
  /** Barcha eski sessiyalar bekor qilinadi; joriy sessiya uchun yangi juftlik qaytadi. */
  changePassword(payload: ChangePasswordPayload): Promise<{ access: string; refresh: string }>;

  // M7 — rollar muharriri (qarang ../../replica/m7-roles-contract.md §2)
  listRoles(): Promise<{ items: RoleOut[] }>;
  createRole(payload: CreateRolePayload): Promise<{ item: RoleOut }>;
  updateRole(id: string, payload: UpdateRolePayload): Promise<{ item: RoleOut }>;
  deleteRole(id: string): Promise<void>;

  // M2b §4 — mening kabinetim (S30)
  meOverview(): Promise<MeOverview>;
  patchMeExtension(payload: PatchMeExtensionPayload): Promise<{ item: MeOverview['extension'] }>;
  meQueueAction(queueId: string, action: QueueMemberAction, payload?: QueueMemberActionPayload): Promise<{ item: MeOverview['queues'][number] }>;
  /** M3a §2 — brauzer softfoni uchun ticket + SIP maʼlumotlari. Har chaqiruv yangi ticket beradi. */
  meSoftphone(): Promise<SoftphoneInfo>;
  /** M3a §5.8 — yengil holat tekshiruvi (parol/ticketsiz, auditsiz): 204 yoki 404/409 xuddi `meSoftphone`dek. */
  meSoftphoneStatus(): Promise<void>;
  meCalls(params: ListCallsParams): Promise<Paged<Call>>;
  meVoicemailMessages(): Promise<{ items: VoicemailMessage[] }>;
  meVoicemailAudio(msg: string): Promise<Blob>;
  meVoicemailHeard(msg: string): Promise<void>;
  meVoicemailDelete(msg: string): Promise<void>;

  // M2b §5 — analitika (S13)
  reportsSummary(params: ReportRangeParams): Promise<ReportsSummary>;
  reportsQueues(params: ReportRangeParams): Promise<{ items: ReportsQueueRow[] }>;
  reportsAgents(params: ReportRangeParams): Promise<{ items: ReportsAgentRow[] }>;
  reportsHourly(params: ReportRangeParams): Promise<{ items: ReportsHourlyRow[] }>;
  reportsDaily(params: ReportRangeParams): Promise<{ items: ReportsDailyRow[] }>;

  // M2c §1 — xavfsizlik sozlamalari (../../replica/m2c-contract.md §1)
  securitySettings(): Promise<SecuritySettings>;
  updateSecuritySettings(payload: UpdateSecuritySettingsPayload): Promise<Mutated<SecuritySettings>>;

  // M2c §2 — SIP hujum himoyasi (S33)
  securityBans(): Promise<{ items: IpBan[] }>;
  createSecurityBan(payload: CreateBanPayload): Promise<Mutated<IpBan>>;
  deleteSecurityBan(id: string): Promise<{ apply: ApplyResult }>;
  securityStats(params: SecurityStatsParams): Promise<SecurityStats>;
  securityEvents(params: ListSecurityEventsParams): Promise<{ items: SecurityEvent[] }>;

  // M2c §3 — toll-fraud
  tollBlocks(): Promise<{ items: TollBlock[] }>;
  unblockToll(extensionId: string): Promise<{ item: { extension_id: string; number: string } }>;

  // M2c §4 — ogohlantirishlar (Telegram)
  alertSettings(): Promise<AlertSettings>;
  updateAlertSettings(payload: UpdateAlertSettingsPayload): Promise<AlertSettings>;
  testAlert(): Promise<TestAlertResult>;
  alertLog(params: ListAlertLogParams): Promise<{ items: AlertLogEntry[] }>;

  // M3b §1 — qo'ngiroq yozuvlari (../../replica/m3b-contract.md §1)
  /** Yozuv audiosi (WAV) — token bilan; player Blob'dan `blob:` manzil yasaydi (M1a saboqi). */
  fetchRecordingAudio(id: string): Promise<Blob>;
  deleteRecording(id: string): Promise<void>;

  // M3b §4 — API kalitlari va ochiq API
  listApiKeys(): Promise<{ items: ApiKey[] }>;
  createApiKey(payload: CreateApiKeyPayload): Promise<CreatedApiKey>;
  revokeApiKey(id: string): Promise<void>;

  // M3b §3 — vebhuklar
  listWebhooks(): Promise<{ items: Webhook[] }>;
  createWebhook(payload: CreateWebhookPayload): Promise<CreatedWebhook>;
  updateWebhook(id: string, payload: UpdateWebhookPayload): Promise<Mutated<Webhook>>;
  deleteWebhook(id: string): Promise<void>;
  rotateWebhookSecret(id: string): Promise<RotatedWebhookSecret>;
  testWebhook(id: string): Promise<TestWebhookResult>;
  webhookDeliveries(id: string, params: ListDeliveriesParams): Promise<{ items: WebhookDelivery[] }>;
  replayDelivery(id: string): Promise<void>;

  // M3b §5 — CRM (Bitrix24 / amoCRM)
  bitrix24Config(): Promise<BitrixConfigResult>;
  updateBitrix24Config(payload: UpdateBitrixPayload): Promise<BitrixConfigResult>;
  amoCrmConfig(): Promise<AmoConfigResult>;
  updateAmoCrmConfig(payload: UpdateAmoPayload): Promise<AmoConfigResult>;
  testCrm(provider: CrmProvider): Promise<CrmTestResult>;
  updateCrmUserMap(provider: CrmProvider, payload: UpdateCrmUserMapPayload): Promise<{ items: CrmUserMapEntry[] }>;

  // 1C — tayyor namunalar
  listOneCSamples(): Promise<{ items: OneCSample[] }>;
  fetchOneCSample(name: string): Promise<Blob>;

  // M3b §6 — sozlamalar
  integrationsSettings(): Promise<IntegrationsSettings>;
  updateIntegrationsSettings(payload: UpdateIntegrationsSettingsPayload): Promise<IntegrationsSettings>;
  recordingSettings(): Promise<RecordingSettings>;
  updateRecordingSettings(payload: UpdateRecordingSettingsPayload): Promise<RecordingSettings>;

  // M4a — qarang ../../replica/m4a-contract.md (S35 «Qurilmalar»)
  listDevices(params: ListDevicesParams): Promise<{ items: Device[] }>;
  createDevice(payload: CreateDevicePayload): Promise<{ item: Device }>;
  updateDevice(id: string, payload: UpdateDevicePayload): Promise<{ item: Device }>;
  deleteDevice(id: string): Promise<void>;
  /** Shartnomada yo'q, lekin BLF tahrirlovchisi joriy tugmalarni ko'rsatishi uchun kerak — `keys_count` yetarli emas. */
  deviceKeys(id: string): Promise<{ items: DeviceKey[] }>;
  updateDeviceKeys(id: string, payload: UpdateDeviceKeysPayload): Promise<{ item: Device }>;
  resyncDevice(id: string): Promise<ResyncDeviceResult>;
  deviceConfig(id: string): Promise<DeviceConfigResult>;
  discoveredDevices(): Promise<{ items: DiscoveredDevice[] }>;
  assignDiscoveredDevice(mac: string, payload: AssignDiscoveredDevicePayload): Promise<{ item: Device }>;
  deleteDiscoveredDevice(mac: string): Promise<void>;
  deviceModels(): Promise<{ items: DeviceModel[] }>;
  provisionRequests(params: ListProvisionRequestsParams): Promise<{ items: ProvisionRequest[] }>;
  provisioningSettings(): Promise<ProvisioningSettings>;
  updateProvisioningSettings(payload: UpdateProvisioningSettingsPayload): Promise<ProvisioningSettings>;
  rotateProvisioningToken(): Promise<RotateProvisioningTokenResult>;

  // M4b — qarang ../../replica/m4b-contract.md (S34 «Zaxira»)
  listBackups(): Promise<{ items: Backup[] }>;
  createBackup(payload: CreateBackupPayload): Promise<{ job: BackupJob }>;
  backupDetail(id: string): Promise<{ item: Backup }>;
  deleteBackup(id: string): Promise<void>;
  downloadBackup(id: string): Promise<Blob>;
  fetchBackupCopy(id: string): Promise<{ item: Backup }>;
  uploadBackup(file: File): Promise<{ item: Backup }>;
  inspectBackup(id: string, payload: InspectBackupPayload): Promise<InspectBackupResult>;
  restoreBackup(id: string, payload: RestoreBackupPayload): Promise<{ job: BackupJob }>;
  backupJob(id: string): Promise<BackupJobState>;
  listRestores(): Promise<{ items: RestoreJob[] }>;
  backupSettings(): Promise<BackupSettings>;
  updateBackupSettings(payload: UpdateBackupSettingsPayload): Promise<BackupSettings>;
  updateBackupPassphrase(payload: UpdateBackupPassphrasePayload): Promise<{ ok: true }>;
  testBackupTarget(payload: TestBackupTargetPayload): Promise<TestBackupTargetResult>;
  trustSftpHostKey(payload: TrustSftpHostKeyPayload): Promise<{ ok: true }>;

  // M5a — qarang ../../replica/m5a-contract.md (S36 «Ko'chirish»)
  uploadMigrationBundle(file: File): Promise<{ item: MigrationJob }>;
  testMigrationSsh(payload: SshTestPayload): Promise<SshTestResult>;
  fetchMigrationSsh(payload: SshFetchPayload): Promise<{ item: MigrationJob }>;
  analyzeMigrationJob(id: string): Promise<{ item: MigrationJob }>;
  migrationJob(id: string): Promise<{ item: MigrationJob }>;
  listMigrationJobs(): Promise<{ items: MigrationJob[] }>;
  migrationPlan(id: string, params: ListMigrationPlanParams): Promise<{ items: MigrationPlanItem[]; total: number }>;
  migrationIgnored(id: string): Promise<{ items: MigrationIgnoredItem[] }>;
  migrationWarnings(id: string): Promise<{ items: MigrationWarning[] }>;
  updateMigrationPlan(id: string, payload: PatchMigrationPlanPayload): Promise<{ item: MigrationJob }>;
  applyMigrationJob(id: string, payload: ApplyMigrationPayload): Promise<{ item: MigrationJob }>;
  deleteMigrationJob(id: string): Promise<void>;
  migrationReport(id: string): Promise<Blob>;
  migrationExportScript(): Promise<Blob>;

  // M5b — qarang ../../replica/m5b-contract.md (`null` — operatorning o'z raqami)
  followMe(target: FollowMeTarget): Promise<FollowMeInfo>;
  updateFollowMe(target: FollowMeTarget, payload: UpdateFollowMePayload): Promise<FollowMeInfo>;
  createQrProvisioning(target: FollowMeTarget): Promise<QrProvisioning>;

  // M6 — qarang ../../replica/m6-contract.md (S18 «Kampaniyalar»)
  listCampaigns(): Promise<{ items: Campaign[] }>;
  getCampaign(id: string): Promise<{ item: Campaign }>;
  createCampaign(payload: CreateCampaignPayload): Promise<{ item: Campaign }>;
  updateCampaign(id: string, payload: UpdateCampaignPayload): Promise<{ item: Campaign }>;
  deleteCampaign(id: string): Promise<void>;
  campaignAction(id: string, action: CampaignAction): Promise<{ item: Campaign }>;
  importCampaignContacts(id: string, payload: ImportCampaignContactsPayload): Promise<ImportCampaignContactsResult>;
  listCampaignContacts(id: string, params: ListCampaignContactsParams): Promise<{ items: CampaignContact[]; total: number }>;
  exportCampaignCsv(id: string): Promise<Blob>;

  // Tizim holati (status) — pbx-klon vazifa (2026-11-02), qarang S36 «Tizim holati»
  systemStatus(): Promise<SystemStatus>;
  previewCleanup(payload: CleanupIn): Promise<CleanupResult>;
  cleanup(payload: CleanupIn): Promise<CleanupResult>;

  // M8 — qarang ../../replica/m8-network-contract.md, S38 «Tarmoq»
  networkState(): Promise<NetworkStateOut>;
  validateNetwork(payload: NetworkConfigIn): Promise<NetworkValidateResult>;
  applyNetwork(payload: NetworkConfigIn): Promise<NetworkStateOut>;
  confirmNetwork(pendingId: string): Promise<NetworkStateOut>;
  rollbackNetwork(pendingId: string): Promise<NetworkStateOut>;

  // M11 — qarang ../../replica/m11-update-contract.md §4, S45 «Yangilanish»
  systemUpdate(): Promise<SystemUpdateOut>;
  checkSystemUpdate(): Promise<SystemUpdateOut>;
  startSystemUpdate(payload: StartSystemUpdatePayload): Promise<SystemUpdateOut>;
  systemUpdateLog(offset: number): Promise<SystemUpdateLog>;

  // M12 B1 — qarang ../../replica/m12-contract.md §B1, «Sozlamalar → Sana va vaqt»
  systemTime(): Promise<TimeStateOut>;
  applyTime(payload: TimeConfigIn): Promise<TimeStateOut>;

  // M12 B2 — qarang §B2, «Tizim holati» qayta yuklash/o'chirish
  systemPower(): Promise<PowerStatusOut>;
  executePower(payload: PowerActionIn): Promise<PowerActionOut>;

  // M12 B3 — qarang §B3, «Sozlamalar → Firewall»
  firewallState(): Promise<FirewallStateOut>;
  validateFirewall(payload: FirewallConfigIn): Promise<FirewallValidateOut>;
  applyFirewall(payload: FirewallConfigIn): Promise<FirewallStateOut>;
  confirmFirewall(pendingId: string): Promise<FirewallStateOut>;
  rollbackFirewall(pendingId: string): Promise<FirewallStateOut>;

  // M9 A1 — qarang ../../replica/m9-freepbx-gaps-contract.md §A1 («E'lon»)
  listAnnouncements(): Promise<Paged<Announcement>>;
  createAnnouncement(payload: CreateAnnouncementPayload): Promise<Mutated<Announcement>>;
  updateAnnouncement(id: string, payload: UpdateAnnouncementPayload): Promise<Mutated<Announcement>>;
  deleteAnnouncement(id: string): Promise<void>;

  // M9 A2 — qarang §A2 («Boshqa manzillar» / «Maxsus kodlar»)
  listMiscDestinations(): Promise<Paged<MiscDestination>>;
  createMiscDestination(payload: CreateMiscDestinationPayload): Promise<Mutated<MiscDestination>>;
  updateMiscDestination(id: string, payload: UpdateMiscDestinationPayload): Promise<Mutated<MiscDestination>>;
  deleteMiscDestination(id: string): Promise<void>;
  listMiscApplications(): Promise<Paged<MiscApplication>>;
  createMiscApplication(payload: CreateMiscApplicationPayload): Promise<Mutated<MiscApplication>>;
  updateMiscApplication(id: string, payload: UpdateMiscApplicationPayload): Promise<Mutated<MiscApplication>>;
  deleteMiscApplication(id: string): Promise<void>;

  // M9 A3 — qarang §A3 («Parkovka»)
  parkingSettings(): Promise<ParkingSettings>;
  updateParkingSettings(payload: UpdateParkingSettingsPayload): Promise<Mutated<ParkingSettings>>;
  parkedCalls(): Promise<Paged<ParkingCall>>;

  // M9 A4 — qarang §A4 («Paging / Intercom»)
  listPageGroups(): Promise<Paged<PageGroup>>;
  createPageGroup(payload: CreatePageGroupPayload): Promise<Mutated<PageGroup>>;
  updatePageGroup(id: string, payload: UpdatePageGroupPayload): Promise<Mutated<PageGroup>>;
  deletePageGroup(id: string): Promise<void>;

  // M9 B1 — qarang §B1 («PIN to'plamlari»)
  listPinSets(): Promise<Paged<PinSet>>;
  createPinSet(payload: CreatePinSetPayload): Promise<Mutated<PinSet>>;
  updatePinSet(id: string, payload: UpdatePinSetPayload): Promise<Mutated<PinSet>>;
  deletePinSet(id: string): Promise<void>;
  listPinSetPins(id: string): Promise<{ items: PinSetPin[] }>;
  addPinSetPins(id: string, payload: AddPinsPayload): Promise<{ items: PinSetPin[] }>;
  deletePinSetPin(id: string, pinId: string): Promise<void>;

  // M9 B2 — qarang §B2 («Telefon kitobi» + CID Lookup)
  listPhonebook(params: ListPhonebookParams): Promise<Paged<Contact>>;
  createContact(payload: CreateContactPayload): Promise<Mutated<Contact>>;
  updateContact(id: string, payload: UpdateContactPayload): Promise<Mutated<Contact>>;
  deleteContact(id: string): Promise<void>;
  exportPhonebookCsv(): Promise<Blob>;
  importPhonebookCsv(params: ImportPhonebookParams): Promise<ImportPhonebookResult>;
  listCidSources(): Promise<Paged<CidSource>>;
  createCidSource(payload: CreateCidSourcePayload): Promise<Mutated<CidSource>>;
  updateCidSource(id: string, payload: UpdateCidSourcePayload): Promise<Mutated<CidSource>>;
  deleteCidSource(id: string): Promise<void>;
  testCidSource(id: string, number: string): Promise<CidSourceTestResult>;

  // M9 B4 — qarang §B4 (ichki raqamlar CSV import/eksport)
  exportExtensionsCsv(): Promise<Blob>;
  importExtensionsCsv(params: ImportExtensionsParams): Promise<ImportExtensionsResult>;

  // M10 C A1 — Callback vidjet
  // Backend `list_callback_widgets` — filtr/pagination/`total` YO'Q, `{items}` qaytadi.
  listCallbackWidgets(): Promise<{ items: CallbackWidget[] }>;
  createCallbackWidget(payload: CreateCallbackWidgetPayload): Promise<Mutated<CallbackWidget>>;
  updateCallbackWidget(id: string, payload: UpdateCallbackWidgetPayload): Promise<Mutated<CallbackWidget>>;
  deleteCallbackWidget(id: string): Promise<void>;
  // Backend `RotateWidgetKeyResult` — `{item, apply}` (`item`ning yolg'iz o'zi EMAS).
  rotateCallbackWidgetKey(id: string): Promise<Mutated<CallbackWidget>>;
  listCallbackRequests(params: ListCallbackRequestsParams): Promise<Paged<CallbackRequest>>;

  // M10 C A2 — Javobsiz qoʻngʻiroq xabari (backend `list_missed_call_rules` — filtr/`total` YO'Q)
  listMissedCallRules(): Promise<{ items: MissedCallRule[] }>;
  createMissedCallRule(payload: CreateMissedCallRulePayload): Promise<MissedCallRuleMutated>;
  updateMissedCallRule(id: string, payload: UpdateMissedCallRulePayload): Promise<MissedCallRuleMutated>;
  deleteMissedCallRule(id: string): Promise<void>;
  testMissedCallRule(id: string): Promise<TestMissedCallRuleResult>;
  listMissedCallNotices(params: ListMissedCallNoticesParams): Promise<Paged<MissedCallNotice>>;

  // M10 C A3 — TTS (Yandex SpeechKit)
  getTtsSettings(): Promise<TtsSettings>;
  // Backend `PATCH /settings/tts` -> `TtsSettingsMutated{item}` (apply YO'Q — dialplanga ta'sir qilmaydi).
  updateTtsSettings(payload: UpdateTtsSettingsPayload): Promise<TtsSettingsMutated>;
  testTtsSettings(): Promise<TtsTestResult>;
  // Backend `POST /audio/tts` -> `AudioCreated{item}` (uploadAudio bilan BIR XIL qolip).
  createTtsAudio(payload: CreateTtsAudioPayload): Promise<{ item: Audio }>;
  previewTts(payload: TtsPreviewPayload): Promise<Blob>;

  // M10 C B1 — Sifat baholash (varaqa/baholash CRUD flat — Mutated/apply YO'Q, dialplanga ta'sir qilmaydi)
  listQaChecklists(): Promise<{ items: QaChecklist[] }>;
  createQaChecklist(payload: CreateQaChecklistPayload): Promise<QaChecklist>;
  updateQaChecklist(id: string, payload: UpdateQaChecklistPayload): Promise<QaChecklist>;
  deleteQaChecklist(id: string): Promise<void>;
  listQaEvaluations(params: ListQaEvaluationsParams): Promise<Paged<QaEvaluation>>;
  createQaEvaluation(payload: CreateQaEvaluationPayload): Promise<QaEvaluation>;
  updateQaEvaluation(id: string, payload: UpdateQaEvaluationPayload): Promise<QaEvaluation>;
  deleteQaEvaluation(id: string): Promise<void>;
  qaSummary(): Promise<QaSummary>;
  listCallEvaluations(linkedid: string): Promise<Paged<QaEvaluation>>;
  listMyEvaluations(params: { page?: number; size?: number }): Promise<Paged<QaEvaluation>>;

  // M10 C B2 — 2FA (TOTP)
  loginTotp(payload: LoginTotpPayload): Promise<AuthResult>;
  setupTotp(): Promise<TotpSetup>;
  enableTotp(payload: TotpEnablePayload): Promise<TotpEnableResult>;
  disableTotp(payload: TotpDisablePayload): Promise<void>;
  regenerateTotpRecoveryCodes(payload: TotpRecoveryCodesPayload): Promise<TotpRecoveryCodesResult>;
  resetUserTotp(userId: string): Promise<void>;

  // M12 A1 — qarang ../../replica/m12-contract.md §A1 («Kun/Tun rejimi», *28N)
  listDayNight(): Promise<{ items: DayNight[] }>;
  createDayNight(payload: CreateDayNightPayload): Promise<Mutated<DayNight>>;
  updateDayNight(id: string, payload: UpdateDayNightPayload): Promise<Mutated<DayNight>>;
  deleteDayNight(id: string): Promise<void>;
  toggleDayNight(id: string): Promise<Mutated<DayNight>>;

  // M12 A2 — qarang §A2 («DISA»)
  listDisa(): Promise<{ items: Disa[] }>;
  createDisa(payload: CreateDisaPayload): Promise<Mutated<Disa>>;
  updateDisa(id: string, payload: UpdateDisaPayload): Promise<Mutated<Disa>>;
  deleteDisa(id: string): Promise<void>;
}

export const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
