import { useEffect, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useSession } from '@/api';
import { syncLanguageFromUser } from '@/lib/i18n';
import { firstVisibleScreen, isScreenVisible, SCREENS } from '@/shell/screens';
import { hasPermission } from './permissions';
import { useAuthBootstrap } from './useAuthBootstrap';

/**
 * Bosh sahifa qoidasi (M7 §4): `*` yoki `monitor:view` bo'lsa — `/dashboard`; aks holda birinchi
 * ko'rinadigan ekran; hech biri ko'rinmasa — `/me` (har kim uchun ochiq shaxsiy kabinet).
 */
export function homeFor(permissions: string[] | undefined): string {
  if (hasPermission(permissions, '*') || hasPermission(permissions, 'monitor:view') || hasPermission(permissions, 'monitor:edit')) {
    return '/dashboard';
  }
  const screen = firstVisibleScreen(permissions);
  return screen ? screen.path : '/me';
}

function FullScreenLoader() {
  return (
    <div className="grid min-h-dvh place-items-center bg-bg text-muted">
      <div className="skeleton h-9 w-9 rounded-full" aria-label="Yuklanmoqda" role="status" />
    </div>
  );
}

/** `/setup` kerak bo'lsa hamma joydan o'zi ochiladi; aks holda kirish talab qilinadi. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { ready, setupNeeded } = useAuthBootstrap();
  const { user } = useSession();
  const location = useLocation();
  // Server tili (`User.language`) haqiqat manbai — kirishda har doim undan sinxronlaymiz (boshqa qurilmada tanlangan til ustun).
  useEffect(() => {
    if (user) syncLanguageFromUser(user.language);
  }, [user]);
  if (!ready) return <FullScreenLoader />;
  if (setupNeeded) return <Navigate to="/setup" replace />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }
  return <>{children}</>;
}

/** Faqat `screenId` joriy `permissions` bilan ko'rinadigan bo'lsa ruxsat beradi — aks holda `/me`ga qaytaradi (M7 §4). */
export function RequireFullAccess({ screenId, children }: { screenId: string; children: ReactNode }) {
  const permissions = useSession((s) => s.user?.permissions);
  const screen = SCREENS.find((s) => s.id === screenId);
  if (screen && !isScreenVisible(screen, permissions)) return <Navigate to="/me" replace />;
  return <>{children}</>;
}

/** Bootstrap tugaguncha loader; `redirectTo` yo'l qaytarsa — o'sha yerga, aks holda bolalarni ko'rsatadi. */
function BootstrapGate({ children, redirectTo }: { children: ReactNode; redirectTo: (setupNeeded: boolean) => string | null }) {
  const { ready, setupNeeded } = useAuthBootstrap();
  if (!ready) return <FullScreenLoader />;
  const to = redirectTo(setupNeeded);
  return to ? <Navigate to={to} replace /> : <>{children}</>;
}

export function RedirectIfSetupDone({ children }: { children: ReactNode }) {
  return <BootstrapGate redirectTo={(setupNeeded) => (setupNeeded ? null : '/login')}>{children}</BootstrapGate>;
}

export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const target = (setupNeeded: boolean) => (setupNeeded ? '/setup' : user ? homeFor(user.permissions) : null);
  return <BootstrapGate redirectTo={target}>{children}</BootstrapGate>;
}
