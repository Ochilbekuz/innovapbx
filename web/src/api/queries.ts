// TanStack Query ilgaklari — ekranlar faqat shu yerdan foydalanadi, `apiClient`ga bevosita murojaat qilmaydi.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './index';
import type {
  CreateBlacklistPayload, CreateConferencePayload,
  CreateExtensionPayload, CreateHolidayPayload, CreateInboundRoutePayload, CreateIvrPayload, CreateMohClassPayload,
  CreateOutboundRoutePayload, CreateQueuePayload, CreateRingGroupPayload, CreateTimeConditionPayload,
  CreateTimeGroupPayload, CreateTrunkPayload, CreateVoicemailBoxPayload, ImportUzHolidaysPayload, ListAuditParams,
  ListBlacklistParams,
  ListCallsParams, ListExtensionsParams, ListTargetsParams, ListVoicemailBoxesParams, NotifyTestPayload,
  NumbersFreeParams, OutboundOrderPayload, OutboundSimulateParams,
  OverrideTimeConditionPayload, RevisionDiffAgainst, SelfSignedTlsPayload, UpdateConferencePayload,
  UpdateExtensionPayload, UpdateFeatureCodePayload,
  UpdateHolidayPayload, UpdateInboundRoutePayload, UpdateIvrPayload, UpdateMohClassPayload, UpdateNotifySettingsPayload,
  UpdateOutboundRoutePayload, UpdateQueuePayload,
  UpdateRingGroupPayload, UpdateSipSettingsPayload, UpdateTimeConditionPayload, UpdateTimeGroupPayload,
  UpdateTrunkPayload, UpdateVoicemailBoxPayload,
  // M2b — qarang ../../replica/m2b-contract.md
  ChangePasswordPayload, CreateUserPayload, LiveSpyPayload, PatchMeExtensionPayload, QueueMemberAction,
  QueueMemberActionPayload, ReportRangeParams, UpdateQueueMemberPayload, UpdateUserPayload,
  // M7 — qarang ../../replica/m7-roles-contract.md
  CreateRolePayload, UpdateRolePayload,
  // M2c — qarang ../../replica/m2c-contract.md
  CreateBanPayload, ListAlertLogParams, ListSecurityEventsParams, SecurityStatsParams,
  UpdateAlertSettingsPayload, UpdateSecuritySettingsPayload,
  // M3b — qarang ../../replica/m3b-contract.md
  CreateApiKeyPayload, CreateWebhookPayload, CrmProvider, ListDeliveriesParams, UpdateAmoPayload,
  UpdateBitrixPayload, UpdateCrmUserMapPayload, UpdateIntegrationsSettingsPayload, UpdateRecordingSettingsPayload,
  UpdateWebhookPayload,
  // M4a — qarang ../../replica/m4a-contract.md
  AssignDiscoveredDevicePayload, CreateDevicePayload, ListDevicesParams, ListProvisionRequestsParams,
  UpdateDeviceKeysPayload, UpdateDevicePayload, UpdateProvisioningSettingsPayload,
  // M4b — qarang ../../replica/m4b-contract.md
  CreateBackupPayload, InspectBackupPayload, RestoreBackupPayload, TestBackupTargetPayload,
  TrustSftpHostKeyPayload, UpdateBackupPassphrasePayload, UpdateBackupSettingsPayload,
  // M5a — qarang ../../replica/m5a-contract.md
  ApplyMigrationPayload, ListMigrationPlanParams, PatchMigrationPlanPayload, SshFetchPayload, SshTestPayload,
  // M5b — qarang ../../replica/m5b-contract.md
  FollowMeTarget, UpdateFollowMePayload,
  // M6 — qarang ../../replica/m6-contract.md
  CampaignAction, CreateCampaignPayload, ImportCampaignContactsPayload, ListCampaignContactsParams, UpdateCampaignPayload,
  // Tizim holati (status) — pbx-klon vazifa (2026-11-02)
  CleanupIn,
  // M8 — qarang ../../replica/m8-network-contract.md
  NetworkConfigIn,
  PingIn,
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  AddPinsPayload, CreateAnnouncementPayload, CreateCidSourcePayload, CreateContactPayload,
  CreateMiscApplicationPayload, CreateMiscDestinationPayload, CreatePageGroupPayload, CreatePinSetPayload,
  ImportExtensionsParams, ImportPhonebookParams, ListPhonebookParams, UpdateAnnouncementPayload,
  UpdateCidSourcePayload, UpdateContactPayload, UpdateMiscApplicationPayload, UpdateMiscDestinationPayload,
  UpdatePageGroupPayload, UpdateParkingSettingsPayload, UpdatePinSetPayload,
  // M10 C — qarang ../../replica/m10-onlinepbx-contract.md (Bo'lak C)
  CreateCallbackWidgetPayload, CreateMissedCallRulePayload, CreateQaChecklistPayload, CreateQaEvaluationPayload,
  ListCallbackRequestsParams, ListMissedCallNoticesParams, ListQaEvaluationsParams,
  TotpDisablePayload, TotpEnablePayload, TotpRecoveryCodesPayload,
  UpdateCallbackWidgetPayload, UpdateMissedCallRulePayload, UpdateQaChecklistPayload, UpdateQaEvaluationPayload,
  UpdateTtsSettingsPayload,
  // M11 — qarang ../../replica/m11-update-contract.md
  StartSystemUpdatePayload, SystemUpdateOut,
  // M12 A1/A2 — qarang ../../replica/m12-contract.md §A1/§A2.
  CreateDayNightPayload, CreateDisaPayload, UpdateDayNightPayload, UpdateDisaPayload,
  // M12 B1/B2/B3 — qarang ../../replica/m12-contract.md §B1/§B2/§B3
  FirewallConfigIn, PowerActionIn, TimeConfigIn,
  AccessSshApplyIn, AccessWebApplyIn,
} from './types';
import { updateStatePollMs } from '@/domain/update';

export const qk = {
  setupState: ['setup-state'] as const,
  health: ['system-health'] as const,
  revisions: ['config-revisions'] as const,
  extensions: (p: ListExtensionsParams) => ['extensions', p] as const,
  trunks: ['trunks'] as const,
  routes: ['inbound-routes'] as const,
  targets: (p: ListTargetsParams) => ['targets', p] as const,
  targetUsages: (id: string) => ['target-usages', id] as const,
  flow: (id: string) => ['flow', id] as const,
  numbersFree: (p: NumbersFreeParams) => ['numbers-free', p] as const,
  calls: (p: ListCallsParams) => ['calls', p] as const,
  timeGroups: ['time-groups'] as const,
  holidays: ['holidays'] as const,
  timeConditions: ['time-conditions'] as const,
  ivrs: ['ivrs'] as const,
  ringGroups: ['ring-groups'] as const,
  queues: ['queues'] as const,
  audio: ['audio'] as const,
  outboundRoutes: ['outbound-routes'] as const,
  sipSettings: ['sip-settings'] as const,
  dashboard: ['dashboard'] as const,
  audit: (p: ListAuditParams) => ['audit', p] as const,
  revisionDetail: (id: string) => ['revision-detail', id] as const,
  revisionDiff: (id: string, against: RevisionDiffAgainst) => ['revision-diff', id, against] as const,
  mohClasses: ['moh-classes'] as const,
  voicemailBoxes: (p: ListVoicemailBoxesParams) => ['voicemail-boxes', p] as const,
  voicemailMessages: (boxId: string) => ['voicemail-messages', boxId] as const,
  notifySettings: ['notify-settings'] as const,
  sipTls: ['sip-tls'] as const,
  // M2a — qarang ../../replica/m2a-contract.md
  featureCodes: ['feature-codes'] as const,
  conferences: ['conferences'] as const,
  blacklist: (p: ListBlacklistParams) => ['blacklist', p] as const,
  parking: ['parking'] as const,
  // M2b — qarang ../../replica/m2b-contract.md
  live: ['live'] as const,
  users: ['users'] as const,
  // M7 — qarang ../../replica/m7-roles-contract.md
  roles: ['roles'] as const,
  meOverview: ['me-overview'] as const,
  meCalls: (p: ListCallsParams) => ['me-calls', p] as const,
  meVoicemail: ['me-voicemail'] as const,
  reportsSummary: (p: ReportRangeParams) => ['reports-summary', p] as const,
  reportsQueues: (p: ReportRangeParams) => ['reports-queues', p] as const,
  reportsAgents: (p: ReportRangeParams) => ['reports-agents', p] as const,
  reportsHourly: (p: ReportRangeParams) => ['reports-hourly', p] as const,
  reportsDaily: (p: ReportRangeParams) => ['reports-daily', p] as const,
  // M2c — qarang ../../replica/m2c-contract.md
  securitySettings: ['security-settings'] as const,
  securityBans: ['security-bans'] as const,
  securityStats: (p: SecurityStatsParams) => ['security-stats', p] as const,
  securityEvents: (p: ListSecurityEventsParams) => ['security-events', p] as const,
  tollBlocks: ['toll-blocks'] as const,
  alertSettings: ['alert-settings'] as const,
  alertLog: (p: ListAlertLogParams) => ['alert-log', p] as const,
  // M3b — qarang ../../replica/m3b-contract.md
  apiKeys: ['api-keys'] as const,
  webhooks: ['webhooks'] as const,
  webhookDeliveries: (id: string, p: ListDeliveriesParams) => ['webhook-deliveries', id, p] as const,
  bitrix24Config: ['crm-bitrix24'] as const,
  amoCrmConfig: ['crm-amocrm'] as const,
  crmUsers: (provider: CrmProvider) => ['crm-users', provider] as const,
  bitrix24License: ['crm-bitrix24-license'] as const,
  oneCSamples: ['1c-samples'] as const,
  integrationsSettings: ['integrations-settings'] as const,
  recordingSettings: ['recording-settings'] as const,
  // M4a — qarang ../../replica/m4a-contract.md
  devices: (p: ListDevicesParams) => ['devices', p] as const,
  discoveredDevices: ['discovered-devices'] as const,
  deviceKeys: (id: string) => ['device-keys', id] as const,
  deviceConfig: (id: string) => ['device-config', id] as const,
  deviceModels: ['device-models'] as const,
  provisionRequests: (p: ListProvisionRequestsParams) => ['provision-requests', p] as const,
  provisioningSettings: ['provisioning-settings'] as const,
  // M4b — qarang ../../replica/m4b-contract.md
  backups: ['backups'] as const,
  backupJob: (id: string) => ['backup-job', id] as const,
  restoreJobs: ['restore-jobs'] as const,
  backupSettings: ['backup-settings'] as const,
  // M5a — qarang ../../replica/m5a-contract.md
  migrationJobs: ['migration-jobs'] as const,
  // M5b — qarang ../../replica/m5b-contract.md
  followMe: (target: FollowMeTarget) => ['follow-me', target ?? 'me'] as const,
  migrationJob: (id: string) => ['migration-job', id] as const,
  migrationPlan: (id: string, p: ListMigrationPlanParams) => ['migration-plan', id, p] as const,
  migrationIgnored: (id: string) => ['migration-ignored', id] as const,
  migrationWarnings: (id: string) => ['migration-warnings', id] as const,
  // M6 — qarang ../../replica/m6-contract.md
  campaigns: ['campaigns'] as const,
  campaignContacts: (id: string, p: ListCampaignContactsParams) => ['campaigns', id, 'contacts', p] as const,
  // Tizim holati (status) — pbx-klon vazifa (2026-11-02)
  systemStatus: ['system-status'] as const,
  // M8 — qarang ../../replica/m8-network-contract.md
  networkState: ['network-state'] as const,
  // M11 — qarang ../../replica/m11-update-contract.md
  systemUpdate: ['system-update'] as const,
  systemUpdateLog: ['system-update-log'] as const,
  // M9 — qarang ../../replica/m9-freepbx-gaps-contract.md
  announcements: ['announcements'] as const,
  miscDestinations: ['misc-destinations'] as const,
  miscApplications: ['misc-applications'] as const,
  parkingSettings: ['parking-settings'] as const,
  parkedCalls: ['parked-calls'] as const,
  pageGroups: ['page-groups'] as const,
  pinSets: ['pin-sets'] as const,
  pinSetPins: (id: string) => ['pin-set-pins', id] as const,
  phonebook: (p: ListPhonebookParams) => ['phonebook', p] as const,
  cidSources: ['cid-sources'] as const,
  // M10 C — qarang ../../replica/m10-onlinepbx-contract.md (Bo'lak C)
  callbackWidgets: ['callback-widgets'] as const,
  callbackRequests: (p: ListCallbackRequestsParams) => ['callback-requests', p] as const,
  missedCallRules: ['missed-call-rules'] as const,
  missedCallNotices: (p: ListMissedCallNoticesParams) => ['missed-call-notices', p] as const,
  ttsSettings: ['tts-settings'] as const,
  qaChecklists: ['qa-checklists'] as const,
  qaEvaluations: (p: ListQaEvaluationsParams) => ['qa-evaluations', p] as const,
  qaSummary: ['qa-summary'] as const,
  callEvaluations: (linkedid: string) => ['call-evaluations', linkedid] as const,
  myEvaluations: (p: { page?: number; size?: number }) => ['my-evaluations', p] as const,
  // M12 A1/A2 — qarang ../../replica/m12-contract.md §A1/§A2.
  dayNight: ['day-night'] as const,
  disa: ['disa'] as const,
  // M12 B1/B2/B3 — qarang ../../replica/m12-contract.md §B1/§B2/§B3
  systemTime: ['system-time'] as const,
  systemPower: ['system-power'] as const,
  firewallState: ['firewall-state'] as const,
  accessState: ['access-state'] as const,
};

export function useSetupState() {
  return useQuery({ queryKey: qk.setupState, queryFn: () => apiClient.setupState() });
}

/** `enabled=false` — operator uchun (endpoint faqat admin; aks holda 403 va abadiy "yuklanmoqda"). */
export function useSystemHealth(enabled = true) {
  return useQuery({ queryKey: qk.health, queryFn: () => apiClient.systemHealth(), refetchInterval: 30_000, enabled });
}

export function useConfigRevisions(limit = 20, enabled = true) {
  return useQuery({ queryKey: qk.revisions, queryFn: () => apiClient.configRevisions(limit), refetchInterval: 30_000, enabled });
}

/** S04'da "jonli holat" uchun davriy yangilanadi — ro'yxat o'zi deyarli statik, status maydoni o'zgaradi. */
export function useExtensions(params: ListExtensionsParams) {
  return useQuery({ queryKey: qk.extensions(params), queryFn: () => apiClient.listExtensions(params), refetchInterval: 15_000 });
}

function useInvalidate() {
  const qc = useQueryClient();
  return (keys: readonly (readonly unknown[])[]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: k as unknown[] }));
}

// Eʼtibor: ['extensions']/['queues']/['ivrs']/['ring-groups']/['time-conditions'] — bu beshtasi
// DestinationPicker katalogida nishon (`target`) sifatida chiqadi, shu sabab ularning
// yaratish/yangilash/oʻchirish mutatsiyalari ['targets'] prefiksini ham invalidatsiya qiladi
// (TanStack Query queryKey prefiks bo'yicha mos keladi — `qk.targets(params)` = ['targets', params]).
export function useCreateExtension() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateExtensionPayload) => apiClient.createExtension(payload),
    onSuccess: () => invalidate([['extensions'], ['targets'], qk.health, qk.revisions]),
  });
}

export function useUpdateExtension() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateExtensionPayload }) => apiClient.updateExtension(id, payload),
    // Follow Me `updated_at` = ichki raqamniki: raqam saqlansa Follow Me keshi ham eskiradi (aks holda 409 stale).
    onSuccess: () => invalidate([['extensions'], ['follow-me'], ['targets'], qk.health, qk.revisions]),
  });
}

export function useRotateExtensionSecret() {
  return useMutation({ mutationFn: (id: string) => apiClient.rotateExtensionSecret(id) });
}

export function useSetExtensionSecret() {
  return useMutation({ mutationFn: ({ id, password }: { id: string; password: string }) => apiClient.setExtensionSecret(id, password) });
}

export function useDeleteExtension() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteExtension(id),
    onSuccess: () => invalidate([['extensions'], ['targets'], qk.health, qk.revisions]),
  });
}

/** Trunk sogʻligʻi "jonli" koʻrsatiladi — davriy yangilanadi. */
export function useTrunks() {
  return useQuery({ queryKey: qk.trunks, queryFn: () => apiClient.listTrunks(), refetchInterval: 15_000 });
}

export function useCreateTrunk() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateTrunkPayload) => apiClient.createTrunk(payload),
    onSuccess: () => invalidate([qk.trunks, qk.health, qk.revisions]),
  });
}

export function useUpdateTrunk() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateTrunkPayload }) => apiClient.updateTrunk(id, payload),
    onSuccess: () => invalidate([qk.trunks, qk.health, qk.revisions]),
  });
}

export function useDeleteTrunk() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteTrunk(id),
    onSuccess: () => invalidate([qk.trunks, qk.health, qk.revisions]),
  });
}

export function useTestTrunk() {
  return useMutation({ mutationFn: (id: string) => apiClient.testTrunk(id) });
}

export function useInboundRoutes() {
  return useQuery({ queryKey: qk.routes, queryFn: () => apiClient.listInboundRoutes() });
}

export function useTargets(params: ListTargetsParams) {
  return useQuery({ queryKey: qk.targets(params), queryFn: () => apiClient.listTargets(params) });
}

export function useCreateInboundRoute() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateInboundRoutePayload) => apiClient.createInboundRoute(payload),
    onSuccess: () => invalidate([qk.routes, qk.health, qk.revisions]),
  });
}

export function useUpdateInboundRoute() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateInboundRoutePayload }) => apiClient.updateInboundRoute(id, payload),
    onSuccess: () => invalidate([qk.routes, qk.health, qk.revisions]),
  });
}

export function useDeleteInboundRoute() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteInboundRoute(id),
    onSuccess: () => invalidate([qk.routes, qk.health, qk.revisions]),
  });
}

export function useCalls(params: ListCallsParams) {
  return useQuery({ queryKey: qk.calls(params), queryFn: () => apiClient.listCalls(params) });
}

export function useTargetUsages(id: string | undefined) {
  return useQuery({ queryKey: qk.targetUsages(id ?? ''), queryFn: () => apiClient.targetUsages(id as string), enabled: !!id });
}

export function useFlow(inboundRouteId: string | undefined) {
  return useQuery({ queryKey: qk.flow(inboundRouteId ?? ''), queryFn: () => apiClient.flow(inboundRouteId as string), enabled: !!inboundRouteId });
}

export function useNumbersFree(params: NumbersFreeParams, enabled = true) {
  return useQuery({ queryKey: qk.numbersFree(params), queryFn: () => apiClient.numbersFree(params), enabled });
}

// ─────────────────────── M1a — Ish vaqti (S08) ───────────────────────

export function useTimeGroups() {
  return useQuery({ queryKey: qk.timeGroups, queryFn: () => apiClient.listTimeGroups() });
}
export function useCreateTimeGroup() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateTimeGroupPayload) => apiClient.createTimeGroup(payload), onSuccess: () => invalidate([qk.timeGroups, qk.health, qk.revisions]) });
}
export function useUpdateTimeGroup() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateTimeGroupPayload }) => apiClient.updateTimeGroup(id, payload), onSuccess: () => invalidate([qk.timeGroups, qk.health, qk.revisions]) });
}
export function useDeleteTimeGroup() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteTimeGroup(id), onSuccess: () => invalidate([qk.timeGroups, qk.health, qk.revisions]) });
}

export function useHolidays() {
  return useQuery({ queryKey: qk.holidays, queryFn: () => apiClient.listHolidays() });
}
export function useCreateHoliday() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateHolidayPayload) => apiClient.createHoliday(payload), onSuccess: () => invalidate([qk.holidays, qk.health, qk.revisions]) });
}
export function useUpdateHoliday() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateHolidayPayload }) => apiClient.updateHoliday(id, payload), onSuccess: () => invalidate([qk.holidays, qk.health, qk.revisions]) });
}
export function useDeleteHoliday() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteHoliday(id), onSuccess: () => invalidate([qk.holidays, qk.health, qk.revisions]) });
}
export function useImportUzHolidays() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: ImportUzHolidaysPayload) => apiClient.importUzHolidays(payload), onSuccess: () => invalidate([qk.holidays, qk.health, qk.revisions]) });
}

export function useTimeConditions() {
  return useQuery({ queryKey: qk.timeConditions, queryFn: () => apiClient.listTimeConditions(), refetchInterval: 30_000 });
}
export function useCreateTimeCondition() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateTimeConditionPayload) => apiClient.createTimeCondition(payload), onSuccess: () => invalidate([qk.timeConditions, ['targets'], qk.health, qk.revisions]) });
}
export function useUpdateTimeCondition() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateTimeConditionPayload }) => apiClient.updateTimeCondition(id, payload), onSuccess: () => invalidate([qk.timeConditions, ['targets'], qk.health, qk.revisions]) });
}
export function useDeleteTimeCondition() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteTimeCondition(id), onSuccess: () => invalidate([qk.timeConditions, ['targets'], qk.health, qk.revisions]) });
}
export function useOverrideTimeCondition() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: OverrideTimeConditionPayload }) => apiClient.overrideTimeCondition(id, payload), onSuccess: () => invalidate([qk.timeConditions, ['targets'], qk.health, qk.revisions]) });
}

// ─────────────────────── M1a — IVR (S09) ───────────────────────

export function useIvrs() {
  return useQuery({ queryKey: qk.ivrs, queryFn: () => apiClient.listIvrs() });
}
export function useCreateIvr() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateIvrPayload) => apiClient.createIvr(payload), onSuccess: () => invalidate([qk.ivrs, ['targets'], qk.health, qk.revisions]) });
}
export function useUpdateIvr() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateIvrPayload }) => apiClient.updateIvr(id, payload), onSuccess: () => invalidate([qk.ivrs, ['targets'], qk.health, qk.revisions]) });
}
export function useDeleteIvr() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteIvr(id), onSuccess: () => invalidate([qk.ivrs, ['targets'], qk.health, qk.revisions]) });
}

// ─────────────────────── M1a — Qoʻngʻiroq guruhlari (S21) ───────────────────────

export function useRingGroups() {
  return useQuery({ queryKey: qk.ringGroups, queryFn: () => apiClient.listRingGroups() });
}
export function useCreateRingGroup() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateRingGroupPayload) => apiClient.createRingGroup(payload), onSuccess: () => invalidate([qk.ringGroups, ['targets'], qk.health, qk.revisions]) });
}
export function useUpdateRingGroup() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateRingGroupPayload }) => apiClient.updateRingGroup(id, payload), onSuccess: () => invalidate([qk.ringGroups, ['targets'], qk.health, qk.revisions]) });
}
export function useDeleteRingGroup() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteRingGroup(id), onSuccess: () => invalidate([qk.ringGroups, ['targets'], qk.health, qk.revisions]) });
}

// ─────────────────────── M1a — Navbatlar (S10) ───────────────────────

export function useQueues() {
  return useQuery({ queryKey: qk.queues, queryFn: () => apiClient.listQueues(), refetchInterval: 10_000 });
}
export function useCreateQueue() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateQueuePayload) => apiClient.createQueue(payload), onSuccess: () => invalidate([qk.queues, ['targets'], qk.health, qk.revisions]) });
}
export function useUpdateQueue() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateQueuePayload }) => apiClient.updateQueue(id, payload), onSuccess: () => invalidate([qk.queues, ['targets'], qk.health, qk.revisions]) });
}
export function useDeleteQueue() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteQueue(id), onSuccess: () => invalidate([qk.queues, ['targets'], qk.health, qk.revisions]) });
}
/** M2b §1 — navbat a'zosining penalty/dynamic belgisi (admin konsoli). */
export function useUpdateQueueMember() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ queueId, extensionId, payload }: { queueId: string; extensionId: string; payload: UpdateQueueMemberPayload }) =>
      apiClient.updateQueueMember(queueId, extensionId, payload),
    onSuccess: () => invalidate([qk.queues, qk.live]),
  });
}
/** M2b §1 — admin konsolidan a'zoni login/logout/pauza qilish. */
export function useQueueMemberAction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ queueId, extensionId, action, payload }: { queueId: string; extensionId: string; action: QueueMemberAction; payload?: QueueMemberActionPayload }) =>
      apiClient.queueMemberAction(queueId, extensionId, action, payload),
    onSuccess: () => invalidate([qk.queues, qk.live]),
  });
}

// ─────────────────────── M1a — Audio (S11) ───────────────────────

export function useAudio() {
  return useQuery({ queryKey: qk.audio, queryFn: () => apiClient.listAudio() });
}
export function useUploadAudio() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ file, name }: { file: File; name: string }) => apiClient.uploadAudio(file, name), onSuccess: () => invalidate([qk.audio]) });
}
export function useDeleteAudio() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteAudio(id), onSuccess: () => invalidate([qk.audio]) });
}

// ─────────────────────── M1b — Tashqi marshrutlar (S22) ───────────────────────

export function useOutboundRoutes() {
  return useQuery({ queryKey: qk.outboundRoutes, queryFn: () => apiClient.listOutboundRoutes() });
}
export function useCreateOutboundRoute() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateOutboundRoutePayload) => apiClient.createOutboundRoute(payload), onSuccess: () => invalidate([qk.outboundRoutes, qk.health, qk.revisions]) });
}
export function useUpdateOutboundRoute() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateOutboundRoutePayload }) => apiClient.updateOutboundRoute(id, payload), onSuccess: () => invalidate([qk.outboundRoutes, qk.health, qk.revisions]) });
}
export function useDeleteOutboundRoute() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteOutboundRoute(id), onSuccess: () => invalidate([qk.outboundRoutes, qk.health, qk.revisions]) });
}

/** Ustunlik tartibini drag-drop bilan darhol koʻrsatish uchun optimistik yangilanadi. */
export function useReorderOutboundRoutes() {
  const qc = useQueryClient();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: OutboundOrderPayload) => apiClient.reorderOutboundRoutes(payload),
    onMutate: async (payload) => {
      const prev = qc.getQueryData<{ items: import('./types').OutboundRoute[] }>(qk.outboundRoutes);
      if (prev) {
        const byId = new Map(prev.items.map((r) => [r.id, r]));
        const reordered = payload.ids.map((id, i) => { const r = byId.get(id); return r ? { ...r, priority: i + 1 } : r; }).filter((r): r is import('./types').OutboundRoute => !!r);
        qc.setQueryData(qk.outboundRoutes, { items: reordered });
      }
      return { prev };
    },
    onError: (_err, _payload, ctx) => { if (ctx?.prev) qc.setQueryData(qk.outboundRoutes, ctx.prev); },
    onSuccess: () => invalidate([qk.outboundRoutes, qk.health, qk.revisions]),
  });
}

export function useSimulateOutboundRoute() {
  return useMutation({ mutationFn: (params: OutboundSimulateParams) => apiClient.simulateOutboundRoute(params) });
}

// ─────────────────────── M1b — SIP va tarmoq (S32) ───────────────────────

export function useSipSettings() {
  return useQuery({ queryKey: qk.sipSettings, queryFn: () => apiClient.sipSettings() });
}
export function useUpdateSipSettings() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: UpdateSipSettingsPayload) => apiClient.updateSipSettings(payload), onSuccess: () => invalidate([qk.sipSettings, qk.health, qk.revisions]) });
}
export function useRestartAsterisk() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (force: boolean | undefined) => apiClient.restartAsterisk(force), onSuccess: () => invalidate([qk.health]) });
}

// ─────────────────────── M1b — Boshqaruv paneli (S03) ───────────────────────

export function useDashboard() {
  return useQuery({ queryKey: qk.dashboard, queryFn: () => apiClient.dashboard(), refetchInterval: 10_000 });
}

// ─────────────────────── M1b — Audit jurnali ───────────────────────

export function useAudit(params: ListAuditParams) {
  return useQuery({ queryKey: qk.audit(params), queryFn: () => apiClient.listAudit(params) });
}

// ─────────────────────── M1b — Reviziyalar / qaytarish ───────────────────────

export function useRevisionDetail(id: string | undefined) {
  return useQuery({ queryKey: qk.revisionDetail(id ?? ''), queryFn: () => apiClient.revisionDetail(id as string), enabled: !!id });
}
export function useRevisionDiff(id: string | undefined, against: RevisionDiffAgainst) {
  return useQuery({ queryKey: qk.revisionDiff(id ?? '', against), queryFn: () => apiClient.revisionDiff(id as string, against), enabled: !!id });
}
export function useRestoreRevision() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.restoreRevision(id), onSuccess: () => invalidate([qk.revisions, qk.health]) });
}

// ─────────────────────── M1b — Kutish musiqasi (MoH) ───────────────────────

export function useMohClasses() {
  return useQuery({ queryKey: qk.mohClasses, queryFn: () => apiClient.listMohClasses() });
}
export function useCreateMohClass() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateMohClassPayload) => apiClient.createMohClass(payload), onSuccess: () => invalidate([qk.mohClasses, qk.queues, qk.health, qk.revisions]) });
}
export function useUpdateMohClass() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UpdateMohClassPayload }) => apiClient.updateMohClass(id, payload), onSuccess: () => invalidate([qk.mohClasses, qk.queues, qk.health, qk.revisions]) });
}
export function useDeleteMohClass() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteMohClass(id), onSuccess: () => invalidate([qk.mohClasses, qk.queues]) });
}

// ─────────────────────── M1c — Ovozli pochta (S23) ───────────────────────

export function useVoicemailBoxes(params: ListVoicemailBoxesParams) {
  return useQuery({ queryKey: qk.voicemailBoxes(params), queryFn: () => apiClient.listVoicemailBoxes(params) });
}
export function useCreateVoicemailBox() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateVoicemailBoxPayload) => apiClient.createVoicemailBox(payload),
    onSuccess: () => invalidate([['voicemail-boxes'], qk.health, qk.revisions]),
  });
}
export function useUpdateVoicemailBox() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateVoicemailBoxPayload }) => apiClient.updateVoicemailBox(id, payload),
    onSuccess: () => invalidate([['voicemail-boxes'], qk.health, qk.revisions]),
  });
}
export function useDeleteVoicemailBox() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteVoicemailBox(id),
    onSuccess: () => invalidate([['voicemail-boxes'], qk.health, qk.revisions]),
  });
}

export function useVoicemailMessages(boxId: string | undefined) {
  return useQuery({ queryKey: qk.voicemailMessages(boxId ?? ''), queryFn: () => apiClient.listVoicemailMessages(boxId as string), enabled: !!boxId });
}
export function useMarkVoicemailMessageHeard() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ boxId, msg }: { boxId: string; msg: string }) => apiClient.markVoicemailMessageHeard(boxId, msg),
    onSuccess: (_void, { boxId }) => invalidate([qk.voicemailMessages(boxId), ['voicemail-boxes']]),
  });
}
export function useDeleteVoicemailMessage() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ boxId, msg }: { boxId: string; msg: string }) => apiClient.deleteVoicemailMessage(boxId, msg),
    onSuccess: (_void, { boxId }) => invalidate([qk.voicemailMessages(boxId), ['voicemail-boxes']]),
  });
}

// ─────────────────────── M1c — Bildirishnomalar (/settings/notify) ───────────────────────

export function useNotifySettings() {
  return useQuery({ queryKey: qk.notifySettings, queryFn: () => apiClient.notifySettings() });
}
export function useUpdateNotifySettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateNotifySettingsPayload) => apiClient.updateNotifySettings(payload),
    onSuccess: () => invalidate([qk.notifySettings]),
  });
}
export function useTestNotify() {
  return useMutation({ mutationFn: (payload: NotifyTestPayload) => apiClient.testNotify(payload) });
}

// ─────────────────────── M1c — SIP TLS ───────────────────────

export function useSipTls() {
  return useQuery({ queryKey: qk.sipTls, queryFn: () => apiClient.sipTls() });
}
export function useUploadSipTlsCertificate() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ cert, key, chain }: { cert: File; key: File; chain?: File }) => apiClient.uploadSipTlsCertificate(cert, key, chain),
    onSuccess: () => invalidate([qk.sipTls, qk.sipSettings]),
  });
}
export function useCreateSelfSignedTls() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: SelfSignedTlsPayload) => apiClient.createSelfSignedSipTls(payload),
    onSuccess: () => invalidate([qk.sipTls, qk.sipSettings]),
  });
}

// ─────────────────────── M2a — Xususiyat kodlari (S24) ───────────────────────

export function useFeatureCodes() {
  return useQuery({ queryKey: qk.featureCodes, queryFn: () => apiClient.listFeatureCodes() });
}
export function useUpdateFeatureCode() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ feature, payload }: { feature: string; payload: UpdateFeatureCodePayload }) => apiClient.updateFeatureCode(feature, payload),
    onSuccess: () => invalidate([qk.featureCodes, qk.health, qk.revisions]),
  });
}
export function useResetFeatureCode() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (feature: string) => apiClient.resetFeatureCode(feature),
    onSuccess: () => invalidate([qk.featureCodes, qk.health, qk.revisions]),
  });
}

// ─────────────────────── M2a — Konferensiya (S25) ───────────────────────

export function useConferences() {
  return useQuery({ queryKey: qk.conferences, queryFn: () => apiClient.listConferences(), refetchInterval: 15_000 });
}
export function useCreateConference() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateConferencePayload) => apiClient.createConference(payload),
    onSuccess: () => invalidate([qk.conferences, ['targets'], qk.health, qk.revisions]),
  });
}
export function useUpdateConference() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateConferencePayload }) => apiClient.updateConference(id, payload),
    onSuccess: () => invalidate([qk.conferences, ['targets'], qk.health, qk.revisions]),
  });
}
export function useDeleteConference() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteConference(id),
    onSuccess: () => invalidate([qk.conferences, ['targets'], qk.health, qk.revisions]),
  });
}

// ─────────────────────── M2a — Qora roʻyxat (S27) ───────────────────────

export function useBlacklist(params: ListBlacklistParams) {
  return useQuery({ queryKey: qk.blacklist(params), queryFn: () => apiClient.listBlacklist(params) });
}
export function useCreateBlacklistEntry() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateBlacklistPayload) => apiClient.createBlacklistEntry(payload),
    onSuccess: () => invalidate([['blacklist']]),
  });
}
export function useDeleteBlacklistEntry() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (number: string) => apiClient.deleteBlacklistEntry(number),
    onSuccess: () => invalidate([['blacklist']]),
  });
}

// ─────────────────────── M2a — Park (S26, dashboard kartasi) ───────────────────────

export function useParking(enabled = true) {
  return useQuery({ queryKey: qk.parking, queryFn: () => apiClient.parking(), refetchInterval: 10_000, enabled });
}

// ─────────────────────── M2b §2 — Jonli monitoring (S29) ───────────────────────

/** 2 soniyalik polling — sahifa koʻrinmay qolganda toʻxtaydi (`refetchIntervalInBackground: false`, sukut). */
export function useLive(enabled = true) {
  return useQuery({ queryKey: qk.live, queryFn: () => apiClient.live(), refetchInterval: enabled ? 2_000 : false, enabled });
}
export function useLiveSpy() {
  return useMutation({ mutationFn: (payload: LiveSpyPayload) => apiClient.liveSpy(payload) });
}

// ─────────────────────── M2b §3 — Foydalanuvchilar (S31) ───────────────────────

export function useUsers() {
  return useQuery({ queryKey: qk.users, queryFn: () => apiClient.listUsers() });
}
export function useCreateUser() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateUserPayload) => apiClient.createUser(payload), onSuccess: () => invalidate([qk.users]) });
}
export function useUpdateUser() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateUserPayload }) => apiClient.updateUser(id, payload),
    onSuccess: () => invalidate([qk.users]),
  });
}
export function useDeleteUser() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteUser(id), onSuccess: () => invalidate([qk.users]) });
}
export function useChangePassword() {
  return useMutation({ mutationFn: (payload: ChangePasswordPayload) => apiClient.changePassword(payload) });
}

// ─────────────────────── M7 — Rollar (qarang ../../replica/m7-roles-contract.md §2) ───────────────────────

export function useRoles() {
  return useQuery({ queryKey: qk.roles, queryFn: () => apiClient.listRoles() });
}
export function useCreateRole() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: CreateRolePayload) => apiClient.createRole(payload), onSuccess: () => invalidate([qk.roles]) });
}
export function useUpdateRole() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateRolePayload }) => apiClient.updateRole(id, payload),
    onSuccess: () => invalidate([qk.roles]),
  });
}
export function useDeleteRole() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteRole(id), onSuccess: () => invalidate([qk.roles]) });
}

// ─────────────────────── M2b §4 — Mening kabinetim (S30) ───────────────────────

export function useMeOverview() {
  return useQuery({ queryKey: qk.meOverview, queryFn: () => apiClient.meOverview() });
}
export function usePatchMeExtension() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (payload: PatchMeExtensionPayload) => apiClient.patchMeExtension(payload), onSuccess: () => invalidate([qk.meOverview, qk.followMe(null)]) });
}
export function useMeQueueAction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ queueId, action, payload }: { queueId: string; action: QueueMemberAction; payload?: QueueMemberActionPayload }) =>
      apiClient.meQueueAction(queueId, action, payload),
    onSuccess: () => invalidate([qk.meOverview]),
  });
}
export function useMeCalls(params: ListCallsParams) {
  return useQuery({ queryKey: qk.meCalls(params), queryFn: () => apiClient.meCalls(params) });
}
export function useMeVoicemailMessages() {
  return useQuery({ queryKey: qk.meVoicemail, queryFn: () => apiClient.meVoicemailMessages() });
}
export function useMeVoicemailHeard() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (msg: string) => apiClient.meVoicemailHeard(msg), onSuccess: () => invalidate([qk.meVoicemail]) });
}
export function useMeVoicemailDelete() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (msg: string) => apiClient.meVoicemailDelete(msg), onSuccess: () => invalidate([qk.meVoicemail]) });
}

// ─────────────────────── M2b §5 — Analitika (S13) ───────────────────────

export function useReportsSummary(params: ReportRangeParams) {
  return useQuery({ queryKey: qk.reportsSummary(params), queryFn: () => apiClient.reportsSummary(params) });
}
export function useReportsQueues(params: ReportRangeParams) {
  return useQuery({ queryKey: qk.reportsQueues(params), queryFn: () => apiClient.reportsQueues(params) });
}
export function useReportsAgents(params: ReportRangeParams) {
  return useQuery({ queryKey: qk.reportsAgents(params), queryFn: () => apiClient.reportsAgents(params) });
}
export function useReportsHourly(params: ReportRangeParams) {
  return useQuery({ queryKey: qk.reportsHourly(params), queryFn: () => apiClient.reportsHourly(params) });
}
export function useReportsDaily(params: ReportRangeParams) {
  return useQuery({ queryKey: qk.reportsDaily(params), queryFn: () => apiClient.reportsDaily(params) });
}

// ─────────────────────── M2c §1-2 — Xavfsizlik (S33) ───────────────────────

export function useSecuritySettings() {
  return useQuery({ queryKey: qk.securitySettings, queryFn: () => apiClient.securitySettings() });
}
export function useUpdateSecuritySettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateSecuritySettingsPayload) => apiClient.updateSecuritySettings(payload),
    onSuccess: () => invalidate([qk.securitySettings, qk.health, qk.revisions]),
  });
}
export function useSecurityBans() {
  return useQuery({ queryKey: qk.securityBans, queryFn: () => apiClient.securityBans() });
}
export function useCreateBan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateBanPayload) => apiClient.createSecurityBan(payload),
    onSuccess: () => invalidate([qk.securityBans, ['security-stats'], ['security-events']]),
  });
}
export function useDeleteBan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteSecurityBan(id),
    onSuccess: () => invalidate([qk.securityBans, ['security-stats'], ['security-events']]),
  });
}
export function useSecurityStats(params: SecurityStatsParams) {
  return useQuery({ queryKey: qk.securityStats(params), queryFn: () => apiClient.securityStats(params), refetchInterval: 30_000 });
}
export function useSecurityEvents(params: ListSecurityEventsParams) {
  return useQuery({ queryKey: qk.securityEvents(params), queryFn: () => apiClient.securityEvents(params) });
}

// ─────────────────────── M2c §3 — Toll-fraud ───────────────────────

export function useTollBlocks() {
  return useQuery({ queryKey: qk.tollBlocks, queryFn: () => apiClient.tollBlocks() });
}
export function useUnblockToll() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (extensionId: string) => apiClient.unblockToll(extensionId),
    onSuccess: () => invalidate([qk.tollBlocks, ['extensions'], ['security-events']]),
  });
}

// ─────────────────────── M2c §4 — Ogohlantirishlar (/settings/alerts) ───────────────────────

export function useAlertSettings() {
  return useQuery({ queryKey: qk.alertSettings, queryFn: () => apiClient.alertSettings() });
}
export function useUpdateAlertSettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateAlertSettingsPayload) => apiClient.updateAlertSettings(payload),
    onSuccess: () => invalidate([qk.alertSettings]),
  });
}
export function useTestAlert() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.testAlert(),
    onSuccess: () => invalidate([['alert-log']]),
  });
}
export function useAlertLog(params: ListAlertLogParams) {
  return useQuery({ queryKey: qk.alertLog(params), queryFn: () => apiClient.alertLog(params) });
}

// ─────────────────────── M3b — Integratsiyalar (/settings/integrations) ───────────────────────

export function useApiKeys() {
  return useQuery({ queryKey: qk.apiKeys, queryFn: () => apiClient.listApiKeys() });
}
export function useCreateApiKey() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateApiKeyPayload) => apiClient.createApiKey(payload),
    onSuccess: () => invalidate([qk.apiKeys]),
  });
}
export function useRevokeApiKey() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.revokeApiKey(id),
    onSuccess: () => invalidate([qk.apiKeys]),
  });
}

export function useWebhooks() {
  return useQuery({ queryKey: qk.webhooks, queryFn: () => apiClient.listWebhooks() });
}
export function useCreateWebhook() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateWebhookPayload) => apiClient.createWebhook(payload),
    onSuccess: () => invalidate([qk.webhooks]),
  });
}
export function useUpdateWebhook() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateWebhookPayload }) => apiClient.updateWebhook(id, payload),
    onSuccess: () => invalidate([qk.webhooks]),
  });
}
export function useDeleteWebhook() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteWebhook(id),
    onSuccess: () => invalidate([qk.webhooks]),
  });
}
export function useRotateWebhookSecret() {
  return useMutation({ mutationFn: (id: string) => apiClient.rotateWebhookSecret(id) });
}
export function useTestWebhook() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.testWebhook(id),
    onSuccess: (_, id) => invalidate([['webhook-deliveries', id]]),
  });
}
export function useWebhookDeliveries(id: string, params: ListDeliveriesParams) {
  return useQuery({
    queryKey: qk.webhookDeliveries(id, params), queryFn: () => apiClient.webhookDeliveries(id, params), enabled: !!id,
  });
}
export function useReplayDelivery(webhookId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (deliveryId: string) => apiClient.replayDelivery(deliveryId),
    onSuccess: () => invalidate([['webhook-deliveries', webhookId]]),
  });
}

export function useBitrix24Config() {
  return useQuery({ queryKey: qk.bitrix24Config, queryFn: () => apiClient.bitrix24Config() });
}
export function useUpdateBitrix24Config() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateBitrixPayload) => apiClient.updateBitrix24Config(payload),
    onSuccess: () => invalidate([qk.bitrix24Config]),
  });
}
export function useAmoCrmConfig() {
  return useQuery({ queryKey: qk.amoCrmConfig, queryFn: () => apiClient.amoCrmConfig() });
}
export function useUpdateAmoCrmConfig() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateAmoPayload) => apiClient.updateAmoCrmConfig(payload),
    onSuccess: () => invalidate([qk.amoCrmConfig]),
  });
}
export function useTestCrm(provider: CrmProvider) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.testCrm(provider),
    onSuccess: () => invalidate([provider === 'bitrix24' ? qk.bitrix24Config : qk.amoCrmConfig]),
  });
}
export function useUpdateCrmUserMap(provider: CrmProvider) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateCrmUserMapPayload) => apiClient.updateCrmUserMap(provider, payload),
    onSuccess: () => invalidate([provider === 'bitrix24' ? qk.bitrix24Config : qk.amoCrmConfig]),
  });
}
/** M3b §5 — oxirgi sinxrondan keshlangan CRM foydalanuvchilari (hali sinxron boʻlmagan boʻlsa boʻsh). */
export function useCrmUsers(provider: CrmProvider) {
  return useQuery({ queryKey: qk.crmUsers(provider), queryFn: () => apiClient.listCrmUsers(provider) });
}
/** M3b §5 — «Bitrix'dan sinxronlash»: foydalanuvchilar + ichki raqamlar (UF_PHONE_INNER) roʻyxatini hozir yuklaydi. */
export function useSyncCrm(provider: CrmProvider) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.syncCrm(provider),
    onSuccess: () => invalidate([provider === 'bitrix24' ? qk.bitrix24Config : qk.amoCrmConfig, qk.crmUsers(provider)]),
  });
}

// Bitrix OAuth ulash — qarang ../../../bitrix-oauth-shartnoma.md §2. `connect/poll` `useMutation` orqali
// (CrmTab.tsx 2 soniyalik intervalni oʻzi boshqaradi, 5 daqiqalik chegara bilan — `useQuery` ichki pollingi mos kelmaydi).
export function useConnectBitrix24() {
  return useMutation({ mutationFn: (domain: string) => apiClient.connectBitrix24(domain) });
}
export function usePollBitrix24Connect() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.pollBitrix24Connect(),
    onSuccess: (result) => { if (result.status === 'connected') invalidate([qk.bitrix24Config, qk.bitrix24License]); },
  });
}
export function useSetupBitrix24() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.setupBitrix24(),
    onSuccess: () => invalidate([qk.bitrix24Config]),
  });
}
export function useDisconnectBitrix24() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.disconnectBitrix24(),
    onSuccess: () => invalidate([qk.bitrix24Config, qk.bitrix24License]),
  });
}
export function useBitrix24License(enabled: boolean) {
  return useQuery({ queryKey: qk.bitrix24License, queryFn: () => apiClient.bitrix24License(), enabled });
}

export function useOneCSamples() {
  return useQuery({ queryKey: qk.oneCSamples, queryFn: () => apiClient.listOneCSamples() });
}

export function useIntegrationsSettings() {
  return useQuery({ queryKey: qk.integrationsSettings, queryFn: () => apiClient.integrationsSettings() });
}
export function useUpdateIntegrationsSettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateIntegrationsSettingsPayload) => apiClient.updateIntegrationsSettings(payload),
    onSuccess: () => invalidate([qk.integrationsSettings]),
  });
}
export function useRecordingSettings() {
  return useQuery({ queryKey: qk.recordingSettings, queryFn: () => apiClient.recordingSettings() });
}
export function useUpdateRecordingSettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateRecordingSettingsPayload) => apiClient.updateRecordingSettings(payload),
    onSuccess: () => invalidate([qk.recordingSettings]),
  });
}

/** M3b §1 — qoʻngʻiroq yozuvini oʻchirish (admin). `CallsPage`/`MePage` qoʻngʻiroqlar roʻyxatini yangilaydi. */
export function useDeleteRecording() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteRecording(id),
    onSuccess: () => invalidate([['calls'], ['me-calls']]),
  });
}

// ─────────────────────── M4a — qarang ../../replica/m4a-contract.md (S35 «Qurilmalar») ───────────────────────

export function useDevices(params: ListDevicesParams) {
  return useQuery({ queryKey: qk.devices(params), queryFn: () => apiClient.listDevices(params) });
}
export function useCreateDevice() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateDevicePayload) => apiClient.createDevice(payload),
    onSuccess: () => invalidate([['devices']]),
  });
}
export function useUpdateDevice() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateDevicePayload }) => apiClient.updateDevice(id, payload),
    onSuccess: () => invalidate([['devices']]),
  });
}
export function useDeleteDevice() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteDevice(id),
    onSuccess: () => invalidate([['devices']]),
  });
}
export function useDeviceKeys(id: string) {
  return useQuery({ queryKey: qk.deviceKeys(id), queryFn: () => apiClient.deviceKeys(id), enabled: !!id });
}
export function useUpdateDeviceKeys() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateDeviceKeysPayload }) => apiClient.updateDeviceKeys(id, payload),
    onSuccess: (_, { id }) => invalidate([['devices'], qk.deviceKeys(id)]),
  });
}
export function useResyncDevice() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.resyncDevice(id),
    onSuccess: () => invalidate([['devices']]),
  });
}
/** Config "koʻrish" talabiga koʻra — faqat modal ochilganda soʻraladi, shu sabab `enabled: !!id` emas, qoʻlda chaqiriladi. */
export function useDeviceConfig(id: string, enabled: boolean) {
  return useQuery({ queryKey: qk.deviceConfig(id), queryFn: () => apiClient.deviceConfig(id), enabled: !!id && enabled });
}
export function useDiscoveredDevices() {
  return useQuery({ queryKey: qk.discoveredDevices, queryFn: () => apiClient.discoveredDevices(), refetchInterval: 15_000 });
}
export function useAssignDiscoveredDevice() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ mac, payload }: { mac: string; payload: AssignDiscoveredDevicePayload }) => apiClient.assignDiscoveredDevice(mac, payload),
    onSuccess: () => invalidate([['devices'], qk.discoveredDevices]),
  });
}
export function useDeleteDiscoveredDevice() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (mac: string) => apiClient.deleteDiscoveredDevice(mac),
    onSuccess: () => invalidate([qk.discoveredDevices]),
  });
}
export function useDeviceModels() {
  return useQuery({ queryKey: qk.deviceModels, queryFn: () => apiClient.deviceModels(), staleTime: Infinity });
}
export function useProvisionRequests(params: ListProvisionRequestsParams) {
  return useQuery({ queryKey: qk.provisionRequests(params), queryFn: () => apiClient.provisionRequests(params), refetchInterval: 15_000 });
}
export function useProvisioningSettings() {
  return useQuery({ queryKey: qk.provisioningSettings, queryFn: () => apiClient.provisioningSettings() });
}
export function useUpdateProvisioningSettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateProvisioningSettingsPayload) => apiClient.updateProvisioningSettings(payload),
    onSuccess: () => invalidate([qk.provisioningSettings]),
  });
}
export function useRotateProvisioningToken() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.rotateProvisioningToken(),
    onSuccess: () => invalidate([qk.provisioningSettings]),
  });
}

// ─────────────────────── M4b — qarang ../../replica/m4b-contract.md (S34 «Zaxira») ───────────────────────

export function useBackups() {
  return useQuery({ queryKey: qk.backups, queryFn: () => apiClient.listBackups() });
}
export function useCreateBackup() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateBackupPayload) => apiClient.createBackup(payload),
    onSuccess: () => invalidate([qk.backups]),
  });
}
export function useDeleteBackup() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteBackup(id),
    onSuccess: () => invalidate([qk.backups]),
  });
}
export function useDownloadBackup() {
  return useMutation({ mutationFn: (id: string) => apiClient.downloadBackup(id) });
}
export function useFetchBackupCopy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.fetchBackupCopy(id),
    onSuccess: () => invalidate([qk.backups]),
  });
}
export function useUploadBackup() {
  return useMutation({ mutationFn: (file: File) => apiClient.uploadBackup(file) });
}
export function useInspectBackup() {
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: InspectBackupPayload }) => apiClient.inspectBackup(id, payload),
  });
}
export function useRestoreBackup() {
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RestoreBackupPayload }) => apiClient.restoreBackup(id, payload),
  });
}
/** Ish tugaguncha (`running`) har 1s so'raladi; `done`/`error` holatida to'xtaydi. */
export function useBackupJob(id: string | null) {
  return useQuery({
    queryKey: qk.backupJob(id ?? ''),
    queryFn: () => apiClient.backupJob(id as string),
    enabled: !!id,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 1000 : false),
  });
}
export function useRestoreJobs() {
  return useQuery({ queryKey: qk.restoreJobs, queryFn: () => apiClient.listRestores() });
}
export function useBackupSettings() {
  return useQuery({ queryKey: qk.backupSettings, queryFn: () => apiClient.backupSettings() });
}
export function useUpdateBackupSettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateBackupSettingsPayload) => apiClient.updateBackupSettings(payload),
    onSuccess: () => invalidate([qk.backupSettings]),
  });
}
export function useUpdateBackupPassphrase() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateBackupPassphrasePayload) => apiClient.updateBackupPassphrase(payload),
    onSuccess: () => invalidate([qk.backupSettings]),
  });
}
export function useTestBackupTarget() {
  return useMutation({
    mutationFn: (payload: TestBackupTargetPayload) => apiClient.testBackupTarget(payload),
  });
}
export function useTrustSftpHostKey() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: TrustSftpHostKeyPayload) => apiClient.trustSftpHostKey(payload),
    onSuccess: () => invalidate([qk.backupSettings]),
  });
}

// ─────────────────────── M5a — qarang ../../replica/m5a-contract.md (S36 «Ko'chirish») ───────────────────────

export function useMigrationJobs() {
  return useQuery({ queryKey: qk.migrationJobs, queryFn: () => apiClient.listMigrationJobs() });
}
/** Tahlil/qo'llash ketayotganda (`analyzing`/`applying`) har 1s so'raladi; aks holda to'xtaydi. */
export function useMigrationJob(id: string | null) {
  return useQuery({
    queryKey: qk.migrationJob(id ?? ''),
    queryFn: () => apiClient.migrationJob(id as string),
    enabled: !!id,
    refetchInterval: (query) => (
      query.state.data?.item.status === 'analyzing' || query.state.data?.item.status === 'applying' ? 1000 : false
    ),
  });
}
export function useUploadMigrationBundle() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (file: File) => apiClient.uploadMigrationBundle(file),
    onSuccess: () => invalidate([qk.migrationJobs]),
  });
}
export function useTestMigrationSsh() {
  return useMutation({ mutationFn: (payload: SshTestPayload) => apiClient.testMigrationSsh(payload) });
}
export function useFetchMigrationSsh() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: SshFetchPayload) => apiClient.fetchMigrationSsh(payload),
    onSuccess: () => invalidate([qk.migrationJobs]),
  });
}
export function useAnalyzeMigrationJob() {
  const qc = useQueryClient();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.analyzeMigrationJob(id),
    // Avval keshga yangi (hali `analyzing`) holatni yozamiz — aks holda eski `analyzed` keshi
    // bir zum ko'rinib, "Ko'rib chiqish" bosqichi tahlil tugamasdan qayta ko'rsatilishi mumkin
    // (masalan `plan_stale`dan keyingi qayta tahlilda).
    onSuccess: (data, id) => {
      qc.setQueryData(qk.migrationJob(id), data);
      invalidate([qk.migrationJobs]);
    },
  });
}
export function useMigrationPlan(id: string | null, params: ListMigrationPlanParams) {
  return useQuery({
    queryKey: qk.migrationPlan(id ?? '', params),
    queryFn: () => apiClient.migrationPlan(id as string, params),
    enabled: !!id,
  });
}
export function useMigrationIgnored(id: string | null) {
  return useQuery({
    queryKey: qk.migrationIgnored(id ?? ''),
    queryFn: () => apiClient.migrationIgnored(id as string),
    enabled: !!id,
  });
}
export function useMigrationWarnings(id: string | null) {
  return useQuery({
    queryKey: qk.migrationWarnings(id ?? ''),
    queryFn: () => apiClient.migrationWarnings(id as string),
    enabled: !!id,
  });
}
export function useUpdateMigrationPlan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: PatchMigrationPlanPayload }) => apiClient.updateMigrationPlan(id, payload),
    onSuccess: (_data, { id }) => invalidate([qk.migrationJob(id), qk.migrationPlan(id, {})]),
  });
}
export function useApplyMigrationJob() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ApplyMigrationPayload }) => apiClient.applyMigrationJob(id, payload),
    onSuccess: (_data, { id }) => invalidate([qk.migrationJob(id), qk.migrationJobs]),
  });
}
export function useDeleteMigrationJob() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteMigrationJob(id),
    onSuccess: () => invalidate([qk.migrationJobs]),
  });
}
export function useMigrationReport() {
  return useMutation({ mutationFn: (id: string) => apiClient.migrationReport(id) });
}
export function useMigrationExportScript() {
  return useMutation({ mutationFn: () => apiClient.migrationExportScript() });
}

// ─────────────────────── M5b — qarang ../../replica/m5b-contract.md ───────────────────────

/** `target` — ichki raqam id (admin) yoki `null` (operatorning o'z raqami). */
export function useFollowMe(target: FollowMeTarget) {
  return useQuery({ queryKey: qk.followMe(target), queryFn: () => apiClient.followMe(target) });
}
/** Saqlash `updated_at`ni yangilaydi — ro'yxat va kabinet ham qayta o'qiladi (keyingi tahrir `stale` bo'lmasin). */
export function useUpdateFollowMe(target: FollowMeTarget) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateFollowMePayload) => apiClient.updateFollowMe(target, payload),
    onSuccess: () => invalidate([qk.followMe(target), ['extensions'], qk.meOverview]),
  });
}
export function useCreateQrProvisioning(target: FollowMeTarget) {
  return useMutation({ mutationFn: () => apiClient.createQrProvisioning(target) });
}

// ─────────────────────── M6 — kampaniyalar (S18) ───────────────────────
/** Ishlayotgan kampaniya bo'lsa 3 s, aks holda 30 s — progress jonli ko'rinsin, bo'sh paytda yuk bo'lmasin. */
export function useCampaigns() {
  return useQuery({
    queryKey: qk.campaigns,
    queryFn: () => apiClient.listCampaigns(),
    refetchInterval: (query) => (query.state.data?.items.some((c) => c.status === 'running') ? 3_000 : 30_000),
  });
}
export function useCampaignContacts(id: string, params: ListCampaignContactsParams, live: boolean) {
  return useQuery({
    queryKey: qk.campaignContacts(id, params),
    queryFn: () => apiClient.listCampaignContacts(id, params),
    refetchInterval: live ? 3_000 : false,
    placeholderData: (prev) => prev,
  });
}
export function useCreateCampaign() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateCampaignPayload) => apiClient.createCampaign(payload),
    onSuccess: () => invalidate([qk.campaigns]),
  });
}
export function useUpdateCampaign() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateCampaignPayload }) => apiClient.updateCampaign(id, payload),
    onSuccess: () => invalidate([qk.campaigns]),
  });
}
export function useDeleteCampaign() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteCampaign(id), onSuccess: () => invalidate([qk.campaigns]) });
}
export function useCampaignAction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: CampaignAction }) => apiClient.campaignAction(id, action),
    onSuccess: () => invalidate([qk.campaigns]),
  });
}
export function useImportCampaignContacts() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ImportCampaignContactsPayload }) => apiClient.importCampaignContacts(id, payload),
    onSuccess: () => invalidate([qk.campaigns]),
  });
}

// ─────────────────────── Tizim holati (status) — pbx-klon vazifa (2026-11-02), S36 ───────────────────────

export function useSystemStatus() {
  return useQuery({ queryKey: qk.systemStatus, queryFn: () => apiClient.systemStatus(), refetchInterval: 30_000 });
}
export function usePreviewCleanup() {
  return useMutation({ mutationFn: (payload: CleanupIn) => apiClient.previewCleanup(payload) });
}
export function useCleanup() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CleanupIn) => apiClient.cleanup(payload),
    onSuccess: () => invalidate([qk.systemStatus]),
  });
}

// ─────────────────────── Tarmoq sozlamalari (network) — M8, S38 ───────────────────────

/** `pending` bor ekan — 3s'da bir yangilanadi (muddat/tasdiqlash holatini kuzatish uchun), aks holda 30s. */
export function useNetworkState() {
  return useQuery({
    queryKey: qk.networkState,
    queryFn: () => apiClient.networkState(),
    refetchInterval: (query) => (query.state.data?.pending ? 3_000 : 30_000),
  });
}
export function useValidateNetwork() {
  return useMutation({ mutationFn: (payload: NetworkConfigIn) => apiClient.validateNetwork(payload) });
}
export function useApplyNetwork() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: NetworkConfigIn) => apiClient.applyNetwork(payload),
    onSuccess: () => invalidate([qk.networkState]),
  });
}
export function useConfirmNetwork() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (pendingId: string) => apiClient.confirmNetwork(pendingId),
    onSuccess: () => invalidate([qk.networkState]),
  });
}
export function useRollbackNetwork() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (pendingId: string) => apiClient.rollbackNetwork(pendingId),
    onSuccess: () => invalidate([qk.networkState]),
  });
}
/** «Ping» tabi — faqat diagnostika: keshni yangilamaydi. */
export function usePingHost() {
  return useMutation({ mutationFn: (payload: PingIn) => apiClient.pingHost(payload) });
}

// ─────────────────────── M12 B1 — Sana va vaqt (../../replica/m12-contract.md §B1) ───────────────────────
// Pending/confirm yo'q — `applyTime` muvaffaqiyatli bo'lsa darhol keshni yangilaydi.

export function useSystemTime() {
  return useQuery({ queryKey: qk.systemTime, queryFn: () => apiClient.systemTime() });
}
export function useApplyTime() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: TimeConfigIn) => apiClient.applyTime(payload),
    onSuccess: () => invalidate([qk.systemTime]),
  });
}
export function useSyncTime() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => apiClient.syncTime(),
    onSuccess: () => invalidate([qk.systemTime]),
  });
}

// ─────────────────────── M12 B2 — Qayta yuklash/o'chirish (../../replica/m12-contract.md §B2) ───────────────────────

export function useSystemPower() {
  return useQuery({ queryKey: qk.systemPower, queryFn: () => apiClient.systemPower() });
}
export function useExecutePower() {
  return useMutation({ mutationFn: (payload: PowerActionIn) => apiClient.executePower(payload) });
}

// ─────────────────────── M12 B3 — Firewall GUI (../../replica/m12-contract.md §B3) ───────────────────────
// `network`dagi bilan bir xil naqsh — `pending` bor ekan tezroq pollanadi.

export function useFirewallState() {
  return useQuery({
    queryKey: qk.firewallState,
    queryFn: () => apiClient.firewallState(),
    refetchInterval: (query) => (query.state.data?.pending ? 3_000 : 30_000),
  });
}
export function useValidateFirewall() {
  return useMutation({ mutationFn: (payload: FirewallConfigIn) => apiClient.validateFirewall(payload) });
}
export function useApplyFirewall() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: FirewallConfigIn) => apiClient.applyFirewall(payload),
    onSuccess: () => invalidate([qk.firewallState]),
  });
}
export function useConfirmFirewall() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (pendingId: string) => apiClient.confirmFirewall(pendingId),
    onSuccess: () => invalidate([qk.firewallState]),
  });
}
export function useRollbackFirewall() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (pendingId: string) => apiClient.rollbackFirewall(pendingId),
    onSuccess: () => invalidate([qk.firewallState]),
  });
}

// ─────────────────────── M12 B4 — Kirish: SSH va veb-panel ───────────────────────
// Firewall'dagi bilan bir xil naqsh — `pending` bor ekan tezroq pollanadi.

export function useAccessState() {
  return useQuery({
    queryKey: qk.accessState,
    queryFn: () => apiClient.accessState(),
    refetchInterval: (query) => (query.state.data?.pending ? 3_000 : 30_000),
  });
}
export function useApplySsh() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: AccessSshApplyIn) => apiClient.applySsh(payload),
    onSuccess: () => invalidate([qk.accessState]),
  });
}
export function useApplyWeb() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: AccessWebApplyIn) => apiClient.applyWeb(payload),
    onSuccess: () => invalidate([qk.accessState]),
  });
}
export function useConfirmAccess() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (pendingId: string) => apiClient.confirmAccess(pendingId),
    onSuccess: () => invalidate([qk.accessState]),
  });
}
export function useRollbackAccess() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (pendingId: string) => apiClient.rollbackAccess(pendingId),
    onSuccess: () => invalidate([qk.accessState]),
  });
}
/** Autentifikatsiyasiz — `/access-confirm` ommaviy sahifasi ishlatadi, `accessState`ni invalidatsiya qilmaydi (login qilinmagan). */
export function useConfirmAccessWebPublic() {
  return useMutation({ mutationFn: (pendingId: string) => apiClient.confirmAccessWebPublic(pendingId) });
}

// ─────────────────────── M11 — Paneldan yangilash (../../replica/m11-update-contract.md) ───────────────────────
// `checking`/`updating`/`pending` paytida 2s poll (domain/update.ts); 502/503/tarmoq xatosida ham oldingi
// `data` saqlanadi (`retry: false` — o'zimiz pollaymiz, react-query ichki qayta urinishi kerak emas).

export function useSystemUpdate() {
  return useQuery({
    queryKey: qk.systemUpdate,
    queryFn: () => apiClient.systemUpdate(),
    retry: false,
    refetchInterval: (query) => updateStatePollMs(query.state.data),
  });
}

export function useCheckSystemUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.checkSystemUpdate(),
    onSuccess: (data: SystemUpdateOut) => qc.setQueryData(qk.systemUpdate, data),
  });
}

export function useStartSystemUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartSystemUpdatePayload) => apiClient.startSystemUpdate(payload),
    onSuccess: (data: SystemUpdateOut) => qc.setQueryData(qk.systemUpdate, data),
  });
}

/** Jurnal — chaqiruvchi `offset`ni o'zi saqlaydi va qaytgan matnni qo'shib boradi (domain/update.ts `appendUpdateLog`). */
export function useSystemUpdateLog(offset: number, enabled: boolean, pollMs: number | false) {
  return useQuery({
    queryKey: qk.systemUpdateLog,
    queryFn: () => apiClient.systemUpdateLog(offset),
    enabled,
    refetchInterval: pollMs,
  });
}

/** M12 B4 — menyudagi "Yangilash" nuqtasi uchun; shu `qk.systemUpdate`ni qayta ishlatadi (dryer) — alohida kesh
 * emas, faqat shu kuzatuvchiga xos uzun `staleTime` orqali 12 soatlik keshni taʼminlaydi (`UpdatePage`ning
 * o'z, tezroq pollashi bilan bir xil yozuvni ulashadi). `enabled=false` — admin bo'lmaganlarga chaqirilmaydi. */
export function useUpdateAvailableDot(enabled: boolean) {
  const { data } = useQuery({
    queryKey: qk.systemUpdate,
    queryFn: () => apiClient.systemUpdate(),
    enabled,
    staleTime: 12 * 60 * 60 * 1000,
    retry: false,
  });
  return enabled && !!data?.available;
}

// ─────────────────────── M9 A1 — Eʼlon (Announcement) ───────────────────────
// `['targets']` ham invalidatsiya qilinadi — Announcement DestinationPicker katalogida nishon sifatida chiqadi.

export function useAnnouncements() {
  return useQuery({ queryKey: qk.announcements, queryFn: () => apiClient.listAnnouncements() });
}
export function useCreateAnnouncement() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateAnnouncementPayload) => apiClient.createAnnouncement(payload),
    onSuccess: () => invalidate([qk.announcements, ['targets'], qk.health, qk.revisions]),
  });
}
export function useUpdateAnnouncement() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateAnnouncementPayload }) => apiClient.updateAnnouncement(id, payload),
    onSuccess: () => invalidate([qk.announcements, ['targets'], qk.health, qk.revisions]),
  });
}
export function useDeleteAnnouncement() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteAnnouncement(id),
    onSuccess: () => invalidate([qk.announcements, ['targets'], qk.health, qk.revisions]),
  });
}

// ─────────────────────── M9 A2 — Boshqa manzillar / Maxsus kodlar ───────────────────────

export function useMiscDestinations() {
  return useQuery({ queryKey: qk.miscDestinations, queryFn: () => apiClient.listMiscDestinations() });
}
export function useCreateMiscDestination() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateMiscDestinationPayload) => apiClient.createMiscDestination(payload),
    onSuccess: () => invalidate([qk.miscDestinations, ['targets'], qk.health, qk.revisions]),
  });
}
export function useUpdateMiscDestination() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateMiscDestinationPayload }) => apiClient.updateMiscDestination(id, payload),
    onSuccess: () => invalidate([qk.miscDestinations, ['targets'], qk.health, qk.revisions]),
  });
}
export function useDeleteMiscDestination() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteMiscDestination(id),
    onSuccess: () => invalidate([qk.miscDestinations, ['targets'], qk.health, qk.revisions]),
  });
}
export function useMiscApplications() {
  return useQuery({ queryKey: qk.miscApplications, queryFn: () => apiClient.listMiscApplications() });
}
export function useCreateMiscApplication() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateMiscApplicationPayload) => apiClient.createMiscApplication(payload),
    onSuccess: () => invalidate([qk.miscApplications, qk.health, qk.revisions]),
  });
}
export function useUpdateMiscApplication() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateMiscApplicationPayload }) => apiClient.updateMiscApplication(id, payload),
    onSuccess: () => invalidate([qk.miscApplications, qk.health, qk.revisions]),
  });
}
export function useDeleteMiscApplication() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteMiscApplication(id),
    onSuccess: () => invalidate([qk.miscApplications, qk.health, qk.revisions]),
  });
}

// ─────────────────────── M9 A3 — Parkovka sozlamalari + jonli roʻyxat ───────────────────────

export function useParkingSettings() {
  return useQuery({ queryKey: qk.parkingSettings, queryFn: () => apiClient.parkingSettings() });
}
export function useUpdateParkingSettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateParkingSettingsPayload) => apiClient.updateParkingSettings(payload),
    onSuccess: () => invalidate([qk.parkingSettings, qk.health, qk.revisions]),
  });
}
/** Parkovkadagi qoʻng'iroqlar — jonli koʻrinish uchun 5 soniyada bir yangilanadi. */
export function useParkedCalls(enabled = true) {
  return useQuery({ queryKey: qk.parkedCalls, queryFn: () => apiClient.parkedCalls(), refetchInterval: enabled ? 5_000 : false, enabled });
}

// ─────────────────────── M9 A4 — Paging / Intercom guruhlari ───────────────────────

export function usePageGroups() {
  return useQuery({ queryKey: qk.pageGroups, queryFn: () => apiClient.listPageGroups() });
}
export function useCreatePageGroup() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreatePageGroupPayload) => apiClient.createPageGroup(payload),
    onSuccess: () => invalidate([qk.pageGroups, qk.health, qk.revisions]),
  });
}
export function useUpdatePageGroup() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdatePageGroupPayload }) => apiClient.updatePageGroup(id, payload),
    onSuccess: () => invalidate([qk.pageGroups, qk.health, qk.revisions]),
  });
}
export function useDeletePageGroup() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deletePageGroup(id),
    onSuccess: () => invalidate([qk.pageGroups, qk.health, qk.revisions]),
  });
}

// ─────────────────────── M9 B1 — PIN toʻplamlari ───────────────────────

export function usePinSets() {
  return useQuery({ queryKey: qk.pinSets, queryFn: () => apiClient.listPinSets() });
}
export function useCreatePinSet() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreatePinSetPayload) => apiClient.createPinSet(payload),
    onSuccess: () => invalidate([qk.pinSets]),
  });
}
export function useUpdatePinSet() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdatePinSetPayload }) => apiClient.updatePinSet(id, payload),
    onSuccess: () => invalidate([qk.pinSets]),
  });
}
export function useDeletePinSet() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deletePinSet(id),
    onSuccess: () => invalidate([qk.pinSets]),
  });
}
export function usePinSetPins(id: string, enabled = true) {
  return useQuery({ queryKey: qk.pinSetPins(id), queryFn: () => apiClient.listPinSetPins(id), enabled });
}
export function useAddPins() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AddPinsPayload }) => apiClient.addPinSetPins(id, payload),
    onSuccess: (_data, { id }) => invalidate([qk.pinSetPins(id), qk.pinSets]),
  });
}
export function useDeletePin() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, pinId }: { id: string; pinId: string }) => apiClient.deletePinSetPin(id, pinId),
    onSuccess: (_data, { id }) => invalidate([qk.pinSetPins(id), qk.pinSets]),
  });
}

// ─────────────────────── M9 B2 — Telefon kitobi (phonebook) + CID manbalari ───────────────────────

export function usePhonebook(params: ListPhonebookParams) {
  return useQuery({ queryKey: qk.phonebook(params), queryFn: () => apiClient.listPhonebook(params), placeholderData: (prev) => prev });
}
export function useCreateContact() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateContactPayload) => apiClient.createContact(payload),
    onSuccess: () => invalidate([['phonebook']]),
  });
}
export function useUpdateContact() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateContactPayload }) => apiClient.updateContact(id, payload),
    onSuccess: () => invalidate([['phonebook']]),
  });
}
export function useDeleteContact() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteContact(id),
    onSuccess: () => invalidate([['phonebook']]),
  });
}
export function useImportPhonebookCsv() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (params: ImportPhonebookParams) => apiClient.importPhonebookCsv(params),
    onSuccess: (result) => { if (result.errors.length === 0) invalidate([['phonebook']]); },
  });
}
export function useCidSources() {
  return useQuery({ queryKey: qk.cidSources, queryFn: () => apiClient.listCidSources() });
}
export function useCreateCidSource() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateCidSourcePayload) => apiClient.createCidSource(payload),
    onSuccess: () => invalidate([qk.cidSources]),
  });
}
export function useUpdateCidSource() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateCidSourcePayload }) => apiClient.updateCidSource(id, payload),
    onSuccess: () => invalidate([qk.cidSources]),
  });
}
export function useDeleteCidSource() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteCidSource(id),
    onSuccess: () => invalidate([qk.cidSources]),
  });
}
export function useTestCidSource() {
  return useMutation({
    mutationFn: ({ id, number }: { id: string; number: string }) => apiClient.testCidSource(id, number),
  });
}

// ─────────────────────── M9 B4 — ichki raqamlar CSV import ───────────────────────
// Eksport (`exportExtensionsCsv`) toʻgʻridan-toʻgʻri `apiClient`dan chaqiriladi (Blob yuklab olish — mutatsiya emas).

export function useImportExtensionsCsv() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (params: ImportExtensionsParams) => apiClient.importExtensionsCsv(params),
    onSuccess: (result) => { if (!result.errors) invalidate([['extensions'], ['targets']]); },
  });
}

// ─────────────────────── M10 C A1 — Callback vidjet ───────────────────────

export function useCallbackWidgets() {
  return useQuery({ queryKey: qk.callbackWidgets, queryFn: () => apiClient.listCallbackWidgets() });
}
export function useCreateCallbackWidget() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateCallbackWidgetPayload) => apiClient.createCallbackWidget(payload),
    onSuccess: () => invalidate([qk.callbackWidgets]),
  });
}
export function useUpdateCallbackWidget() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateCallbackWidgetPayload }) => apiClient.updateCallbackWidget(id, payload),
    onSuccess: () => invalidate([qk.callbackWidgets]),
  });
}
export function useDeleteCallbackWidget() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteCallbackWidget(id), onSuccess: () => invalidate([qk.callbackWidgets]) });
}
export function useRotateCallbackWidgetKey() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.rotateCallbackWidgetKey(id), onSuccess: () => invalidate([qk.callbackWidgets]) });
}
export function useCallbackRequests(params: ListCallbackRequestsParams) {
  return useQuery({ queryKey: qk.callbackRequests(params), queryFn: () => apiClient.listCallbackRequests(params) });
}

// ─────────────────────── M10 C A2 — Javobsiz qoʻngʻiroq xabari ───────────────────────

export function useMissedCallRules() {
  return useQuery({ queryKey: qk.missedCallRules, queryFn: () => apiClient.listMissedCallRules() });
}
export function useCreateMissedCallRule() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateMissedCallRulePayload) => apiClient.createMissedCallRule(payload),
    onSuccess: () => invalidate([qk.missedCallRules]),
  });
}
export function useUpdateMissedCallRule() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateMissedCallRulePayload }) => apiClient.updateMissedCallRule(id, payload),
    onSuccess: () => invalidate([qk.missedCallRules]),
  });
}
export function useDeleteMissedCallRule() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteMissedCallRule(id), onSuccess: () => invalidate([qk.missedCallRules]) });
}
export function useTestMissedCallRule() {
  return useMutation({ mutationFn: (id: string) => apiClient.testMissedCallRule(id) });
}
export function useMissedCallNotices(params: ListMissedCallNoticesParams) {
  return useQuery({ queryKey: qk.missedCallNotices(params), queryFn: () => apiClient.listMissedCallNotices(params) });
}

// ─────────────────────── M10 C A3 — TTS ───────────────────────
// `previewTts` (Blob) — bevosita `apiClient`dan chaqiriladi (mutatsiya emas, qarang AudioPage.tsx).

export function useTtsSettings() {
  return useQuery({ queryKey: qk.ttsSettings, queryFn: () => apiClient.getTtsSettings() });
}
export function useUpdateTtsSettings() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: UpdateTtsSettingsPayload) => apiClient.updateTtsSettings(payload),
    onSuccess: () => invalidate([qk.ttsSettings]),
  });
}
export function useTestTtsSettings() {
  return useMutation({ mutationFn: () => apiClient.testTtsSettings() });
}
export function useCreateTtsAudio() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: { name: string; text: string }) => apiClient.createTtsAudio(payload),
    onSuccess: () => invalidate([qk.audio]),
  });
}

// ─────────────────────── M10 C B1 — Sifat baholash ───────────────────────

export function useQaChecklists() {
  return useQuery({ queryKey: qk.qaChecklists, queryFn: () => apiClient.listQaChecklists() });
}
export function useCreateQaChecklist() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateQaChecklistPayload) => apiClient.createQaChecklist(payload),
    onSuccess: () => invalidate([qk.qaChecklists]),
  });
}
export function useUpdateQaChecklist() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateQaChecklistPayload }) => apiClient.updateQaChecklist(id, payload),
    onSuccess: () => invalidate([qk.qaChecklists]),
  });
}
export function useDeleteQaChecklist() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => apiClient.deleteQaChecklist(id), onSuccess: () => invalidate([qk.qaChecklists]) });
}
export function useQaEvaluations(params: ListQaEvaluationsParams) {
  return useQuery({ queryKey: qk.qaEvaluations(params), queryFn: () => apiClient.listQaEvaluations(params) });
}
export function useCreateQaEvaluation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateQaEvaluationPayload) => apiClient.createQaEvaluation(payload),
    onSuccess: () => invalidate([['qa-evaluations'], ['qa-summary'], ['call-evaluations'], ['my-evaluations'], ['calls']]),
  });
}
export function useUpdateQaEvaluation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateQaEvaluationPayload }) => apiClient.updateQaEvaluation(id, payload),
    onSuccess: () => invalidate([['qa-evaluations'], ['qa-summary'], ['call-evaluations'], ['my-evaluations']]),
  });
}
export function useDeleteQaEvaluation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteQaEvaluation(id),
    onSuccess: () => invalidate([['qa-evaluations'], ['qa-summary'], ['call-evaluations'], ['my-evaluations']]),
  });
}
export function useQaSummary() {
  return useQuery({ queryKey: qk.qaSummary, queryFn: () => apiClient.qaSummary() });
}
export function useCallEvaluations(linkedid: string) {
  return useQuery({ queryKey: qk.callEvaluations(linkedid), queryFn: () => apiClient.listCallEvaluations(linkedid), enabled: !!linkedid });
}
export function useMyEvaluations(params: { page?: number; size?: number }) {
  return useQuery({ queryKey: qk.myEvaluations(params), queryFn: () => apiClient.listMyEvaluations(params) });
}

// ─────────────────────── M10 C B2 — 2FA (TOTP) ───────────────────────
// `loginTotp` — LoginPage'da bevosita chaqiriladi (sessiyagacha, boshqa kirish mutatsiyalari kabi ilgaksiz).

export function useSetupTotp() {
  return useMutation({ mutationFn: () => apiClient.setupTotp() });
}
export function useEnableTotp() {
  return useMutation({ mutationFn: (payload: TotpEnablePayload) => apiClient.enableTotp(payload) });
}
export function useDisableTotp() {
  return useMutation({ mutationFn: (payload: TotpDisablePayload) => apiClient.disableTotp(payload) });
}
export function useRegenerateTotpRecoveryCodes() {
  return useMutation({ mutationFn: (payload: TotpRecoveryCodesPayload) => apiClient.regenerateTotpRecoveryCodes(payload) });
}
export function useResetUserTotp() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (userId: string) => apiClient.resetUserTotp(userId), onSuccess: () => invalidate([qk.users]) });
}

// ─────────────────────── M12 A1 — Kun/Tun rejimi (*28N) ───────────────────────
// `['targets']` ham invalidatsiya qilinadi — day_night DestinationPicker katalogida nishon sifatida chiqadi.

export function useDayNight() {
  return useQuery({ queryKey: qk.dayNight, queryFn: () => apiClient.listDayNight() });
}
export function useCreateDayNight() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateDayNightPayload) => apiClient.createDayNight(payload),
    onSuccess: () => invalidate([qk.dayNight, ['targets'], qk.health, qk.revisions]),
  });
}
export function useUpdateDayNight() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateDayNightPayload }) => apiClient.updateDayNight(id, payload),
    onSuccess: () => invalidate([qk.dayNight, ['targets'], qk.health, qk.revisions]),
  });
}
export function useToggleDayNight() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.toggleDayNight(id),
    onSuccess: () => invalidate([qk.dayNight, ['targets'], qk.health, qk.revisions]),
  });
}
export function useDeleteDayNight() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteDayNight(id),
    onSuccess: () => invalidate([qk.dayNight, ['targets'], qk.health, qk.revisions]),
  });
}

// ─────────────────────── M12 A2 — DISA ───────────────────────

export function useDisa() {
  return useQuery({ queryKey: qk.disa, queryFn: () => apiClient.listDisa() });
}
export function useCreateDisa() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateDisaPayload) => apiClient.createDisa(payload),
    onSuccess: () => invalidate([qk.disa, ['targets'], qk.health, qk.revisions]),
  });
}
export function useUpdateDisa() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateDisaPayload }) => apiClient.updateDisa(id, payload),
    onSuccess: () => invalidate([qk.disa, ['targets'], qk.health, qk.revisions]),
  });
}
export function useDeleteDisa() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteDisa(id),
    onSuccess: () => invalidate([qk.disa, ['targets'], qk.health, qk.revisions]),
  });
}
