import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Pencil, RotateCcw, ShieldAlert, X } from 'lucide-react';
import { useFeatureCodes, useResetFeatureCode, useUpdateFeatureCode } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { FeatureCode } from '@/api/types';
import { usePermission } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

// M2a — qarang ../../../replica/m2a-contract.md §2
const FEATURE_CODE_RE = /^\*[0-9*#]{1,6}$/;

function CodeCell({ fc, canManage }: { fc: FeatureCode; canManage: boolean }) {
  const { t } = useTranslation('featurecodes');
  const toast = useToast();
  const updateM = useUpdateFeatureCode();
  const resetM = useResetFeatureCode();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(fc.code);

  const valid = FEATURE_CODE_RE.test(value.trim());
  const errorField = isApiError(updateM.error) ? updateM.error.field : undefined;
  const serverError = isApiError(updateM.error) && errorField === 'code' ? updateM.error.message : undefined;

  const save = () => {
    if (!valid) return;
    updateM.mutate({ feature: fc.feature, payload: { code: value.trim() } }, {
      onSuccess: (res) => { setEditing(false); toast(applyToast(res.apply, t('toast.saved'))); },
    });
  };
  const cancel = () => { setEditing(false); setValue(fc.code); updateM.reset(); };

  if (!editing) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="num text-sm">{fc.code}</span>
        {canManage && (
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { feature: t(`feature.${fc.feature}`) })} onClick={() => setEditing(true)} />
        )}
        {canManage && fc.code !== fc.default_code && (
          <Button
            size="sm" variant="ghost" iconOnly icon={<RotateCcw />} loading={resetM.isPending}
            aria-label={t('resetAriaLabel', { feature: t(`feature.${fc.feature}`) })}
            onClick={() => resetM.mutate(fc.feature, { onSuccess: (res) => toast(applyToast(res.apply, t('toast.reset'))) })}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <Input mono className="w-28" value={value} onChange={(e) => setValue(e.target.value)} autoFocus aria-label={t('column.code')} />
        <Button size="sm" variant="ghost" iconOnly icon={<Check />} aria-label={t('saveAriaLabel')} disabled={!valid} loading={updateM.isPending} onClick={save} />
        <Button size="sm" variant="ghost" iconOnly icon={<X />} aria-label={t('cancelAriaLabel')} onClick={cancel} />
      </div>
      {!valid && value.trim() !== '' && <p className="text-xs text-danger">{t('error.badCode')}</p>}
      {serverError && <p className="text-xs text-danger">{serverError}</p>}
    </div>
  );
}

/** S24 — xususiyat kodlari: har bir xususiyatning *-kodi, yoqilgan-oʻchirilganligi, standart holatga qaytarish. */
export function FeatureCodesPage() {
  const { t } = useTranslation('featurecodes');
  const { data, isLoading, isError, refetch } = useFeatureCodes();
  const canManage = usePermission('pbx.manage');
  const toast = useToast();
  const updateM = useUpdateFeatureCode();

  const columns: Column<FeatureCode>[] = [
    { key: 'feature', header: t('column.feature'), cell: (fc) => <span className="font-medium">{t(`feature.${fc.feature}`)}</span> },
    { key: 'code', header: t('column.code'), cell: (fc) => <CodeCell fc={fc} canManage={canManage} /> },
    {
      key: 'enabled', header: t('column.enabled'), cell: (fc) => canManage ? (
        <Toggle
          checked={fc.enabled}
          onCheckedChange={(v) => updateM.mutate({ feature: fc.feature, payload: { enabled: v } }, {
            onSuccess: (res) => toast(applyToast(res.apply, t('toast.saved'))),
          })}
          label={t('column.enabled')}
          hideLabel
        />
      ) : (
        <Badge tone={fc.enabled ? 'success' : 'neutral'}>{fc.enabled ? t('column.enabled') : '—'}</Badge>
      ),
    },
  ];

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(fc) => fc.feature}
        searchText={(fc) => `${t(`feature.${fc.feature}`)} ${fc.code}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        empty={{ title: t('caption'), body: '' }}
      />
    </AppShellPage>
  );
}
