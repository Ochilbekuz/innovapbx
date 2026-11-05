import { lazy, Suspense, type ComponentType } from 'react';
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
import { StatusPage } from '@/screens/status/StatusPage';
import { LicensePage } from '@/screens/license/LicensePage';
import { NetworkPage } from '@/screens/network/NetworkPage';
import { AnnouncementsPage } from '@/screens/announcements/AnnouncementsPage';
import { MiscPage } from '@/screens/misc/MiscPage';
import { ParkingPage } from '@/screens/parking/ParkingPage';
import { PagingPage } from '@/screens/paging/PagingPage';
import { PhonebookPage } from '@/screens/phonebook/PhonebookPage';
import { PinSetsPage } from '@/screens/pinsets/PinSetsPage';
import { CidSourcesPage } from '@/screens/cidsources/CidSourcesPage';
import { QualityPage } from '@/screens/quality/QualityPage';
import { MissedCallsPage } from '@/screens/missedcalls/MissedCallsPage';
import { CallbackWidgetPage } from '@/screens/callback/CallbackWidgetPage';
import { Enroll2faPage } from '@/screens/auth/Enroll2faPage';
import { UpdatePage } from '@/screens/update/UpdatePage';
import { DayNightPage } from '@/screens/daynight/DayNightPage';
import { DisaPage } from '@/screens/disa/DisaPage';
import { TimeSettingsPage } from '@/screens/time/TimeSettingsPage';
import { FirewallPage } from '@/screens/firewall/FirewallPage';
import { AccessConfirmPage } from '@/screens/access/AccessConfirmPage';

// Qo'llanma matnlari (~300 KB) asosiy bundle'ga kirmasin — alohida chunk, birinchi ochilganda yuklanadi.
const DocsPage = lazy(() => import('@/screens/docs/DocsPage').then((m) => ({ default: m.DocsPage })));

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
  status: StatusPage,
  license: LicensePage,
  network: NetworkPage,
  announcements: AnnouncementsPage,
  misc: MiscPage,
  parking: ParkingPage,
  paging: PagingPage,
  phonebook: PhonebookPage,
  pinsets: PinSetsPage,
  cidsources: CidSourcesPage,
  quality: QualityPage,
  missedcalls: MissedCallsPage,
  update: UpdatePage,
  day_night: DayNightPage,
  disa: DisaPage,
  time: TimeSettingsPage,
  firewall: FirewallPage,
};

/** `/` va noma'lum yo'llar uchun ruxsatga mos boshlang'ich sahifa (M7 §4 — qarang `homeFor`). */
function RoleHome() {
  const permissions = useSession((s) => s.user?.permissions);
  return <Navigate to={homeFor(permissions)} replace />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/design/*" element={<DesignPage />} />

      <Route path="/setup" element={<RedirectIfSetupDone><SetupPage /></RedirectIfSetupDone>} />
      <Route path="/login" element={<RedirectIfAuthed><LoginPage /></RedirectIfAuthed>} />
      {/* Autentifikatsiyasiz — veb-panel porti o'zgargandan keyin brauzer shu yerga keladi (M12 B4 §3). */}
      <Route path="/access-confirm" element={<AccessConfirmPage />} />
      {/* 1.0.25: Kirish (SSH va veb-panel) — Firewall sahifasining tabi; eski manzil u yerga yo'naltiriladi. */}
      <Route path="/settings/access" element={<RequireAuth><Navigate to="/settings/firewall?tab=access" replace /></RequireAuth>} />

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
        <Route
          key={r.reconId}
          path={r.path}
          element={
            <RequireAuth>
              {r.reconId === 'S17' ? <CallbackWidgetPage /> : <ExtraScreenStub reconId={r.reconId} titleKey={r.titleKey} />}
            </RequireAuth>
          }
        />
      ))}
      {/* Sidebarda ko'rsatilmaydi — header'dagi RevisionBadge orqali ochiladi (M1b §7). */}
      <Route path="/settings/revisions" element={<RequireAuth><RevisionsPage /></RequireAuth>} />
      <Route path="/settings/revisions/:id" element={<RequireAuth><RevisionsPage /></RequireAuth>} />
      {/* Sidebarda ko'rsatilmaydi — `must_change_password` bo'lsa `RequireAuth` shu yerga qaytaradi (M2b §3). */}
      <Route path="/change-password" element={<RequireAuth><ChangePasswordPage /></RequireAuth>} />
      {/* Sidebarda ko'rsatilmaydi — `must_enroll_2fa` bo'lsa `RequireAuth` shu yerga qaytaradi (M10 C B2). */}
      <Route path="/enroll-2fa" element={<RequireAuth><Enroll2faPage /></RequireAuth>} />

      {/* Qo'llanma — hamma rolga (sidebar pastidagi «Qo'llanma» va sarlavhadagi «?» tugmasi). */}
      <Route path="/docs" element={<RequireAuth><Suspense fallback={null}><DocsPage /></Suspense></RequireAuth>} />
      <Route path="/docs/:id" element={<RequireAuth><Suspense fallback={null}><DocsPage /></Suspense></RequireAuth>} />

      <Route path="/" element={<RequireAuth><RoleHome /></RequireAuth>} />
      <Route path="*" element={<RequireAuth><RoleHome /></RequireAuth>} />
    </Routes>
  );
}
