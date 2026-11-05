// Ommaviy sahifa — veb-panel porti o'zgargandan keyin brauzer shu yerga keladi (`/access-confirm#<pending_id>`).
// Autentifikatsiyasiz (`RequireAuth` tashqarisida) — eski manzilda sessiya bo'lmasligi mumkin.
import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CircleAlert, CircleCheck } from 'lucide-react';
import { useConfirmAccessWebPublic } from '@/api/queries';
import { navigateTo } from '@/lib/browser';
import { BrandMark } from '@/shell/AppShell';
import { Button } from '@/ui/Button';

/** `location.hash`dan `pending_id`ni ajratadi — boshidagi `#` olib tashlanadi. */
function pendingIdFromHash(hash: string): string | null {
  const id = hash.replace(/^#/, '');
  return id.length > 0 ? id : null;
}

export function AccessConfirmPage() {
  const { t } = useTranslation('access');
  const location = useLocation();
  const [triedWithoutId, setTriedWithoutId] = useState(false);
  const pendingId = pendingIdFromHash(location.hash);
  const mutation = useConfirmAccessWebPublic();

  useEffect(() => {
    if (!pendingId) {
      setTriedWithoutId(true);
      return;
    }
    mutation.mutate(pendingId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingId]);

  return (
    <div className="grid min-h-dvh place-items-center bg-sidebar-bg px-4">
      <div className="w-full max-w-[400px] overflow-hidden rounded-xl border border-sidebar-border bg-surface shadow-modal">
        <div className="flex items-center gap-3 border-b border-line bg-sidebar-bg px-6 py-5">
          <BrandMark />
        </div>
        <div className="flex flex-col items-center gap-3 px-6 py-8 text-center">
          <h1 className="font-display text-lg text-fg">{t('confirmPage.title')}</h1>
          {triedWithoutId ? (
            <p className="flex items-center gap-2 text-sm text-danger"><CircleAlert aria-hidden className="size-4 shrink-0" />{t('confirmPage.missingId')}</p>
          ) : mutation.isPending || mutation.isIdle ? (
            <p className="text-sm text-muted">{t('confirmPage.confirming')}</p>
          ) : mutation.isSuccess ? (
            <>
              <p className="flex items-center gap-2 text-sm text-success"><CircleCheck aria-hidden className="size-4 shrink-0" />{t('confirmPage.success')}</p>
              <Button variant="primary" onClick={() => navigateTo('/')}>{t('confirmPage.loginButton')}</Button>
            </>
          ) : (
            <p className="flex items-center gap-2 text-sm text-danger"><CircleAlert aria-hidden className="size-4 shrink-0" />{t('confirmPage.failed')}</p>
          )}
        </div>
      </div>
    </div>
  );
}
