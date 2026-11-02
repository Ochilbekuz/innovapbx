import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { KeyRound, Plus } from 'lucide-react';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/api/queries';
import { API_KEY_SCOPES, type ApiKey, type ApiKeyScope } from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, queryState, type Column } from '@/ui/Table';
import { Checkbox } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { SecretOnceModal, useMutationError } from './shared';

// Qo'shtirnoqli i18next `nsSeparator` (':') xavf tug'diradi — xomashyo scope qiymatini kalit yo'liga qo'ymaymiz.
const SCOPE_KEY: Record<ApiKeyScope, string> = {
  'calls:read': 'callsRead', 'recordings:read': 'recordingsRead', 'calls:originate': 'callsOriginate', 'extensions:read': 'extensionsRead',
};

function scopeLabel(t: (k: string) => string, scope: ApiKeyScope): string {
  return t(`apiKeys.scope.${SCOPE_KEY[scope]}`);
}

function keyStatus(item: ApiKey): 'active' | 'revoked' | 'expired' {
  if (item.revoked_at) return 'revoked';
  if (item.expires_at && new Date(item.expires_at).getTime() < Date.now()) return 'expired';
  return 'active';
}

const STATUS_TONE = { active: 'success', expired: 'warning', revoked: 'neutral' } as const;

function ApiKeyStatusBadge({ item }: { item: ApiKey }) {
  const { t } = useTranslation('integrations');
  const s = keyStatus(item);
  return <Badge tone={STATUS_TONE[s]}>{t(`apiKeys.${s}`)}</Badge>;
}

function ApiKeyRevokeAction({ item, canManage, onRevoke }: { item: ApiKey; canManage: boolean; onRevoke: () => void }) {
  const { t } = useTranslation('integrations');
  if (!canManage || item.revoked_at) return null;
  return <Button size="sm" variant="danger-ghost" data-testid={`apikey-revoke-${item.id}`} onClick={onRevoke}>{t('apiKeys.revoke')}</Button>;
}

/** M3b §4 — API kalitlari roʻyxati, yaratish (bir martalik koʻrsatish) va bekor qilish. */
export function ApiKeysTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const { data, isLoading, isError, refetch } = useApiKeys();
  const [createOpen, setCreateOpen] = useState(false);
  const [revoking, setRevoking] = useState<ApiKey | null>(null);
  const [created, setCreated] = useState<{ name: string; key: string } | null>(null);

  const columns: Column<ApiKey>[] = [
    { key: 'name', header: t('apiKeys.name'), sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'prefix', header: t('apiKeys.prefix'), cell: (r) => <span className="num text-muted">{r.prefix}…</span> },
    { key: 'scopes', header: t('apiKeys.scopes'), cell: (r) => <div className="flex flex-wrap gap-1">{r.scopes.map((s) => <Badge key={s}>{scopeLabel(t, s)}</Badge>)}</div> },
    { key: 'created_at', header: t('apiKeys.createdAt'), sortValue: (r) => r.created_at, cell: (r) => <span className="num text-sm text-muted">{formatDateTimeShort(r.created_at)}</span> },
    { key: 'last_used_at', header: t('apiKeys.lastUsed'), cell: (r) => <span className="num text-sm text-muted">{r.last_used_at ? formatDateTimeShort(r.last_used_at) : t('apiKeys.never')}</span> },
    { key: 'status', header: t('apiKeys.statusLabel'), cell: (r) => <ApiKeyStatusBadge item={r} /> },
    { key: 'actions', header: '', align: 'right', cell: (r) => <ApiKeyRevokeAction item={r} canManage={canManage} onRevoke={() => setRevoking(r)} /> },
  ];

  return (
    <section>
      <div className="mb-3 flex items-start justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">{t('apiKeys.desc')}</p>
        {canManage && <Button data-testid="apikey-create" icon={<Plus />} onClick={() => setCreateOpen(true)}>{t('apiKeys.create')}</Button>}
      </div>
      <DataTable
        caption={t('apiKeys.title')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.name} ${r.prefix}`}
        state={queryState(isLoading, isError)}
        onRetry={() => void refetch()}
        empty={{ title: t('apiKeys.empty'), body: '' }}
      />
      <CreateApiKeyModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(name, key) => { setCreateOpen(false); setCreated({ name, key }); }}
      />
      <RevokeApiKeyModal item={revoking} onClose={() => setRevoking(null)} />
      <SecretOnceModal
        open={!!created}
        title={t('apiKeys.secretTitle')}
        warning={t('apiKeys.secretWarning')}
        secret={created?.key}
        secretTestId="apikey-secret"
        onClose={() => setCreated(null)}
      />
    </section>
  );
}

function useApiKeyForm() {
  const [name, setName] = useState('');
  const [scopes, setScopes] = useState<Set<ApiKeyScope>>(new Set());
  const [expiresAt, setExpiresAt] = useState('');
  const reset = () => { setName(''); setScopes(new Set()); setExpiresAt(''); };
  const toggleScope = (s: ApiKeyScope, v: boolean) => setScopes((prev) => { const next = new Set(prev); if (v) next.add(s); else next.delete(s); return next; });
  return { name, setName, scopes, toggleScope, expiresAt, setExpiresAt, reset };
}

/** `errorField`ni belgilangan nom/scope xato maydonlariga aylantiradi — bannerda qayta chiqmasin. */
function otherApiKeyError(errorMessage: string | undefined, errorField: string | undefined): string | null {
  return errorMessage && errorField !== 'name' && errorField !== 'scopes' ? errorMessage : null;
}

function ScopesField({ scopes, onToggle, error }: { scopes: Set<ApiKeyScope>; onToggle: (s: ApiKeyScope, v: boolean) => void; error?: string }) {
  const { t } = useTranslation('integrations');
  return (
    <Field label={t('apiKeys.scopes')} error={error}>
      {() => (
        <div className="flex flex-col gap-2">
          {API_KEY_SCOPES.map((s) => (
            <label key={s} className="flex items-center gap-2 text-sm">
              <Checkbox checked={scopes.has(s)} onCheckedChange={(v) => onToggle(s, v)} aria-label={scopeLabel(t, s)} />
              {scopeLabel(t, s)}
            </label>
          ))}
        </div>
      )}
    </Field>
  );
}

function CreateApiKeyModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (name: string, key: string) => void }) {
  const { t } = useTranslation('integrations');
  const createM = useCreateApiKey();
  const { name, setName, scopes, toggleScope, expiresAt, setExpiresAt, reset } = useApiKeyForm();

  const close = () => { reset(); createM.reset(); onClose(); };
  const { field: errorField, message: errorMessage } = useMutationError(createM.error);

  const submit = () => {
    createM.mutate({ name: name.trim(), scopes: [...scopes], expires_at: expiresAt ? `${expiresAt}T00:00:00.000Z` : null }, {
      onSuccess: (res) => onCreated(res.item.name, res.key),
    });
  };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => !v && close()}
      title={t('apiKeys.create')}
      footer={<><Button variant="ghost" onClick={close}>{t('apiKeys.cancel')}</Button><Button variant="primary" loading={createM.isPending} onClick={submit}>{t('apiKeys.create')}</Button></>}
    >
      <div className="flex flex-col gap-4">
        <Field label={t('apiKeys.name')} error={errorField === 'name' ? t('apiKeys.errors.bad_name') : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <ScopesField scopes={scopes} onToggle={toggleScope} error={errorField === 'scopes' ? t('apiKeys.errors.bad_scopes') : undefined} />
        <Field label={t('apiKeys.expiresAt')} hint={t('apiKeys.expiresAtHint')}>
          {(a) => <Input {...a} type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />}
        </Field>
        {otherApiKeyError(errorMessage, errorField) && <p className="text-sm text-danger">{otherApiKeyError(errorMessage, errorField)}</p>}
      </div>
    </Modal>
  );
}

function RevokeApiKeyModal({ item, onClose }: { item: ApiKey | null; onClose: () => void }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const revokeM = useRevokeApiKey();
  const close = () => { revokeM.reset(); onClose(); };
  return (
    <Modal
      open={!!item}
      onOpenChange={(v) => !v && close()}
      title={t('apiKeys.revokeConfirmTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('apiKeys.cancel')}</Button>
          <Button
            variant="danger" loading={revokeM.isPending} icon={<KeyRound />}
            onClick={() => item && revokeM.mutate(item.id, { onSuccess: () => { toast({ kind: 'success', title: t('apiKeys.revoke') }); close(); } })}
          >
            {t('apiKeys.confirm')}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted">{t('apiKeys.revokeConfirmBody', { name: item?.name })}</p>
    </Modal>
  );
}
