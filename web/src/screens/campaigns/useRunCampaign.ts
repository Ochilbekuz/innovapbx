import { useTranslation } from 'react-i18next';
import { apiErrorMessage } from '@/api/errors';
import { useCampaignAction } from '@/api/queries';
import type { Campaign, CampaignAction } from '@/api/types';
import { useToast } from '@/ui/Toast';

const TOAST: Record<CampaignAction, string> = { start: 'toast.started', pause: 'toast.paused', stop: 'toast.stopped' };

/** Boshlash/pauza/to'xtatish — jadval qatori va detal panel bir xil toast bilan ishlatadi. */
export function useRunCampaign() {
  const { t } = useTranslation('campaigns');
  const toast = useToast();
  const m = useCampaignAction();
  const run = (c: Campaign, action: CampaignAction, onDone?: () => void) =>
    m.mutate({ id: c.id, action }, {
      onSuccess: () => { toast({ kind: 'success', title: t(TOAST[action], { name: c.name }) }); onDone?.(); },
      onError: (e) => toast({ kind: 'error', title: t('toast.failed'), description: apiErrorMessage(e) }),
    });
  const busy = (c: Campaign, action?: CampaignAction) =>
    m.isPending && m.variables?.id === c.id && (action === undefined || m.variables.action === action);
  return { run, busy };
}
