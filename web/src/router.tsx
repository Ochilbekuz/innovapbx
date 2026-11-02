import type { ComponentType } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { homeFor, RedirectIfAuthed, RedirectIfSetupDone, RequireAuth, RequireFullAccess } from '@/auth/guards';
import { useSession } from '@/api/session';
import { DesignPage } from '@/design/DesignPage';
import { EXTRA_ROUTES, SCREENS } from '@/shell/screens';
import { ExtraScreenStub, ScreenStub } from '@/shell/ScreenStub';
import { SetupPage } from '@/screens/setup/SetupPage';
import { LoginPage } from '@/screens/auth/LoginPage';
import { DashboardPage } from '@/screens/dashboard/DashboardPage';
import { ExtensionsPage } from '@/screens/extensions/ExtensionsPage';
import { TrunksPage } from '@/screens/trunks/TrunksPage';
import { InboundRoutesPage } from '@/screens/routes/InboundRoutesPage';
import { CallsPage } from '@/screens/calls/CallsPage';
import { TimeGroupsPage } from '@/screens/timegroups/TimeGroupsPage';
import { IvrPage } from '@/screens/ivr/IvrPage';
import { QueuesPage } from '@/screens/queues/QueuesPage';
import { RingGroupsPage } from '@/screens/ringgroups/RingGroupsPage';
import { AudioPage } from '@/screens/audio/AudioPage';
import { OutboundRoutesPage } from '@/screens/outbound/OutboundRoutesPage';
import { SipPage } from '@/screens/sip/SipPage';
import { AuditPage } from '@/screens/audit/AuditPage';
import { RevisionsPage } from '@/screens/revisions/RevisionsPage';
import { VoicemailPage } from '@/screens/voicemail/VoicemailPage';
import { FeatureCodesPage } from '@/screens/featurecodes/FeatureCodesPage';
import { ConferencesPage } from '@/screens/conferences/ConferencesPage';
import { CampaignsPage } from '@/screens/campaigns/CampaignsPage';
import { BlacklistPage } from '@/screens/blacklist/BlacklistPage';
import { UsersPage } from '@/screens/users/UsersPage';
import { MePage } from '@/screens/me/MePage';
import { LivePage } from '@/screens/live/LivePage';
import { AnalyticsPage } from '@/screens/analytics/AnalyticsPage';
import { ChangePasswordPage } from '@/screens/auth/ChangePasswordPage';
import { SecurityPage } from '@/screens/security/SecurityPage';
import { AlertsPage } from '@/screens/alerts/AlertsPage';
import { IntegrationsPage } from '@/screens/integrations/IntegrationsPage';
import { DevicesPage } from '@/screens/devices/DevicesPage';
import { BackupPage } from '@/screens/backup/BackupPage';
import { MigrationPage } from '@/screens/migration/MigrationPage';

/** M0/M1a/M2b'da to'liq qurilgan ekranlar — qolganlari `ScreenStub` orqali "tez orada". */
const FULL_PAGES: Record<string, ComponentType> = {
  campaigns: CampaignsPage,
  dashboard: DashboardPage,
  extensions: ExtensionsPage,
  trunks: TrunksPage,
  inbound: InboundRoutesPage,
  cdr: CallsPage,
  timegroups: TimeGroupsPage,
  ivr: IvrPage,
  queues: QueuesPage,
  ringgroups: RingGroupsPage,
  audio: AudioPage,
  outbound: OutboundRoutesPage,
  sip: SipPage,
  audit: AuditPage,
  voicemail: VoicemailPage,
  featurecodes: FeatureCodesPage,
  conference: ConferencesPage,
  blacklist: BlacklistPage,
  users: UsersPage,
  portal: MePage,
  live: LivePage,
  analytics: AnalyticsPage,
  security: SecurityPage,
  alerts: AlertsPage,
  integrations: IntegrationsPage,
  devices: DevicesPage,
  backup: BackupPage,
  migration: MigrationPage,
};

/** `/` va noma'lum yo'llar uchun rolga mos boshlang'ich sahifa (operator → `/me`, admin → `/dashboard`). */
function RoleHome() {
  const role = useSession((s) => s.user?.role);
  return <Navigate to={homeFor(role)} replace />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/design/*" element={<DesignPage />} />

      <Route path="/setup" element={<RedirectIfSetupDone><SetupPage /></RedirectIfSetupDone>} />
      <Route path="/login" element={<RedirectIfAuthed><LoginPage /></RedirectIfAuthed>} />

      {SCREENS.map((s) => {
        const Page = FULL_PAGES[s.id];
        return (
          <Route
            key={s.id}
            path={s.path}
            element={<RequireAuth><RequireFullAccess screenId={s.id}>{Page ? <Page /> : <ScreenStub screen={s} />}</RequireFullAccess></RequireAuth>}
          />
        );
      })}
      {EXTRA_ROUTES.map((r) => (
        <Route key={r.reconId} path={r.path} element={<RequireAuth><ExtraScreenStub reconId={r.reconId} titleKey={r.titleKey} /></RequireAuth>} />
      ))}
      {/* Sidebarda ko'rsatilmaydi — header'dagi RevisionBadge orqali ochiladi (M1b §7). */}
      <Route path="/settings/revisions" element={<RequireAuth><RevisionsPage /></RequireAuth>} />
      <Route path="/settings/revisions/:id" element={<RequireAuth><RevisionsPage /></RequireAuth>} />
      {/* Sidebarda ko'rsatilmaydi — `must_change_password` bo'lsa `RequireAuth` shu yerga qaytaradi (M2b §3). */}
      <Route path="/change-password" element={<RequireAuth><ChangePasswordPage /></RequireAuth>} />

      <Route path="/" element={<RequireAuth><RoleHome /></RequireAuth>} />
      <Route path="*" element={<RequireAuth><RoleHome /></RequireAuth>} />
    </Routes>
  );
}
