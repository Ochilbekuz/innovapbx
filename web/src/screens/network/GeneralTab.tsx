// "Umumiy" tab — host nomi, DNS, standart shlyuz (faqat o'qish). M8 §5.
import { useTranslation } from 'react-i18next';
import type { NetworkFieldError, NetworkStateOut } from '@/api/types';
import { Field, Input } from '@/ui/Field';
import { fieldErrorIn } from './networkDraft';
import type { NetworkDraft } from './networkDraft';

function DefaultGateway({ gateway }: { gateway: NetworkStateOut['default_gateway'] }) {
  const { t } = useTranslation('network');
  return (
    <Field label={t('general.defaultGatewayLabel')}>
      {() => (
        <p className="num flex h-ctl-md items-center rounded-md border border-line bg-surface-2 px-2.5 text-base text-fg">
          {gateway.address
            ? t('general.defaultGatewayValue', { address: gateway.address, iface: gateway.interface ?? '—' })
            : t('general.defaultGatewayNone')}
        </p>
      )}
    </Field>
  );
}

export function GeneralTab({
  draft, onChange, errors, defaultGateway, dnsEditable, locked,
}: {
  draft: NetworkDraft;
  onChange: (patch: Partial<NetworkDraft>) => void;
  errors: NetworkFieldError[];
  defaultGateway: NetworkStateOut['default_gateway'];
  dnsEditable: boolean;
  locked: boolean;
}) {
  const { t } = useTranslation('network');
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <Field label={t('general.hostnameLabel')} error={fieldErrorIn(errors, 'hostname')}>
        {(a) => <Input {...a} disabled={locked} value={draft.hostname} onChange={(e) => onChange({ hostname: e.target.value })} />}
      </Field>
      <Field label={t('general.dnsServersLabel')} hint={t('general.dnsServersHint')}>
        {(a) => (
          <Input {...a} mono disabled={locked || !dnsEditable} value={draft.dnsServers} onChange={(e) => onChange({ dnsServers: e.target.value })} />
        )}
      </Field>
      <Field label={t('general.dnsSearchLabel')} hint={t('general.dnsSearchHint')}>
        {(a) => (
          <Input {...a} disabled={locked || !dnsEditable} value={draft.dnsSearch} onChange={(e) => onChange({ dnsSearch: e.target.value })} />
        )}
      </Field>
      <DefaultGateway gateway={defaultGateway} />
    </div>
  );
}
