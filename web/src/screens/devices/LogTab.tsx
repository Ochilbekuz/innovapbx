import { useTranslation } from 'react-i18next';
import { useProvisionRequests } from '@/api/queries';
import type { ProvisionRequest } from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, queryState, type Column } from '@/ui/Table';

const REASON_TONE: Record<ProvisionRequest['reason'], Tone> = {
  ok: 'success', unknown_mac: 'warning', bad_token: 'danger', network_denied: 'danger', rate_limited: 'danger', legacy_binary: 'neutral',
};

function logColumns(
  t: (k: string) => string,
): Column<ProvisionRequest>[] {
  return [
    { key: 'at', header: t('log.column.at'), sortValue: (r) => r.at, cell: (r) => <span className="num text-sm text-muted">{formatDateTimeShort(r.at)}</span> },
    { key: 'ip', header: t('log.column.ip'), cell: (r) => <span className="num text-sm">{r.ip}</span> },
    { key: 'mac', header: t('log.column.mac'), cell: (r) => <span className="num text-sm text-muted">{r.mac ?? '—'}</span> },
    { key: 'vendor', header: t('log.column.vendor'), cell: (r) => <span className="text-sm text-muted">{r.vendor ?? '—'}</span> },
    { key: 'path', header: t('log.column.path'), cell: (r) => <span className="num text-xs text-muted break-all">{r.path}</span> },
    { key: 'status_code', header: t('log.column.statusCode'), align: 'right', cell: (r) => <span className="num text-sm">{r.status_code}</span> },
    { key: 'reason', header: t('log.column.reason'), cell: (r) => <Badge tone={REASON_TONE[r.reason]}>{t(`log.reason.${r.reason}`)}</Badge> },
  ];
}

/** Jurnal tabi — provizioning soʻrovlari (shartnoma §3-4), oxirgi 200. */
export function LogTab() {
  const { t } = useTranslation('devices');
  const { data, isLoading, isError, refetch } = useProvisionRequests({});
  return (
    <DataTable
      caption={t('log.title')}
      rows={data?.items ?? []}
      columns={logColumns(t)}
      rowId={(r) => `${r.at}-${r.ip}-${r.mac ?? ''}-${r.path}-${r.status_code}`}
      searchText={(r) => `${r.ip} ${r.mac ?? ''} ${r.path}`}
      state={queryState(isLoading, isError)}
      onRetry={() => void refetch()}
      empty={{ title: t('log.empty'), body: '' }}
    />
  );
}
