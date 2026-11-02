import { useEffect, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useSession } from '@/api';
import { syncLanguageFromUser } from '@/lib/i18n';
import { OPERATOR_VISIBLE_IDS } from '@/shell/screens';
import { useAuthBootstrap } from './useAuthBootstrap';

/** Rolga mos boshlang'ich sahifa — operator uchun `/me`, admin uchun `/dashboard`. */
export function homeFor(role: 'admin' | 'operator' | undefined): string {
  return role === 'operator' ? '/me' : '/dashboard';
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

/** Faqat `screenId` operator uchun ham ko'rinadigan bo'lsa ruxsat beradi — aks holda `/me`ga qaytaradi (M2b §4). */
export function RequireFullAccess({ screenId, children }: { screenId: string; children: ReactNode }) {
  const role = useSession((s) => s.user?.role);
  if (role === 'operator' && !OPERATOR_VISIBLE_IDS.includes(screenId)) return <Navigate to="/me" replace />;
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
  const target = (setupNeeded: boolean) => (setupNeeded ? '/setup' : user ? homeFor(user.role) : null);
  return <BootstrapGate redirectTo={target}>{children}</BootstrapGate>;
}
