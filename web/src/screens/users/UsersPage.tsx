import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useCreateUser, useDeleteUser, useExtensions, useUpdateUser, useUsers } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { CreateUserPayload, ManagedUser, Role, UpdateUserPayload } from '@/api/types';
import type { Lang } from '@/lib/i18n';
import { usePermission } from '@/auth/permissions';
import { useSession } from '@/api/session';
import { formatDateTimeShort } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const LANGS: Lang[] = ['uz', 'ru', 'en'];

/** S31 — foydalanuvchilar: ro'yxat, yaratish/tahrirlash drawer, faolsizlantirish/o'chirish (M2b §3). */
export function UsersPage() {
  const { t } = useTranslation('users');
  const { data, isLoading, isError, refetch } = useUsers();
  const { data: extensionsData } = useExtensions({ page: 1, size: 200 });
  const canManage = usePermission('system.manage');
  const myId = useSession((s) => s.user?.id);
  const toast = useToast();

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [deleting, setDeleting] = useState<ManagedUser | null>(null);

  const createM = useCreateUser();
  const updateM = useUpdateUser();
  const deleteM = useDeleteUser();

  const closeCreate = () => { setCreateOpen(false); createM.reset(); };
  const closeEdit = () => { setEditing(null); updateM.reset(); };

  const columns: Column<ManagedUser>[] = [
    { key: 'username', header: t('column.username'), sortValue: (r) => r.username, cell: (r) => <span className="num font-medium">{r.username}</span> },
    { key: 'full_name', header: t('column.fullName'), sortValue: (r) => r.full_name, cell: (r) => <span className="block max-w-[220px] truncate">{r.full_name}</span> },
    { key: 'role', header: t('column.role'), cell: (r) => <Badge tone={r.role === 'admin' ? 'accent' : 'neutral'}>{t(`role.${r.role}`)}</Badge> },
    { key: 'extension', header: t('column.extension'), cell: (r) => <span className="num text-sm text-muted">{r.extension ? `${r.extension.number} — ${r.extension.name}` : '—'}</span> },
    { key: 'status', header: t('column.status'), cell: (r) => <Badge tone={r.is_active ? 'success' : 'neutral'}>{t(r.is_active ? 'status.active' : 'status.inactive')}</Badge> },
    { key: 'last_login_at', header: t('column.lastLogin'), sortValue: (r) => r.last_login_at ?? '', cell: (r) => <span className="num text-sm text-muted">{r.last_login_at ? formatDateTimeShort(r.last_login_at) : t('neverLoggedIn')}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: r.username })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: r.username })} disabled={!canManage || r.id === myId} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  const takenExtensionIds = new Set((data?.items ?? []).filter((u) => u.id !== editing?.id).map((u) => u.extension?.id).filter(Boolean));
  const availableExtensions = (extensionsData?.items ?? []).filter((e) => !takenExtensionIds.has(e.id));

  return (
    <AppShellPage title={t('title')}>
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.username} ${r.full_name} ${r.extension?.number ?? ''}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setCreateOpen(true)}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setCreateOpen(true)}>{t('newUser')}</Button> : undefined}
      />

      {createOpen && (
        <CreateUserDrawer
          extensions={availableExtensions}
          onClose={closeCreate}
          onSubmit={(payload) => createM.mutate(payload, {
            onSuccess: () => { closeCreate(); toast({ kind: 'success', title: t('toast.added') }); },
          })}
          pending={createM.isPending}
          errorField={isApiError(createM.error) ? createM.error.field : undefined}
          errorMessage={isApiError(createM.error) ? createM.error.message : undefined}
        />
      )}

      {editing && (
        <EditUserDrawer
          user={editing}
          extensions={availableExtensions}
          isSelf={editing.id === myId}
          onClose={closeEdit}
          onSubmit={(payload) => updateM.mutate({ id: editing.id, payload }, {
            onSuccess: () => { closeEdit(); toast({ kind: 'success', title: t('toast.saved') }); },
          })}
          pending={updateM.isPending}
          errorField={isApiError(updateM.error) ? updateM.error.field : undefined}
          errorMessage={isApiError(updateM.error) ? updateM.error.message : undefined}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('deleteModal.title', { name: deleting.username }) : ''}
        description={deleting ? t('deleteModal.body', { name: deleting.username }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.username }) }); setDeleting(null); },
                onError: (e) => { toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      />
    </AppShellPage>
  );
}

type ExtOption = { id: string; number: string; name: string };

function CreateUserDrawer({
  extensions, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  extensions: ExtOption[];
  onClose: () => void;
  onSubmit: (payload: CreateUserPayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('users');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('operator');
  const [extensionId, setExtensionId] = useState('');
  const [language, setLanguage] = useState<Lang>('uz');
  const [password, setPassword] = useState('');

  const valid = username.trim().length > 0 && fullName.trim().length > 0 && password.length >= 10;

  const submit = () => {
    if (!valid) return;
    onSubmit({
      username: username.trim(), full_name: fullName.trim(), email: email.trim() || null,
      role, extension_id: extensionId || null, password, language,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['username', 'extension_id', 'password'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}
        <Field label={t('form.usernameLabel')} required error={errorField === 'username' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus mono value={username} onChange={(e) => setUsername(e.target.value)} />}
        </Field>
        <Field label={t('form.fullNameLabel')} required>
          {(a) => <Input {...a} value={fullName} onChange={(e) => setFullName(e.target.value)} />}
        </Field>
        <Field label={t('form.emailLabel')} aside={t('form.emailAside')}>
          {(a) => <Input {...a} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Field label={t('form.roleLabel')}>
          {(a) => <Select {...a} value={role} onValueChange={(v) => setRole(v as Role)} options={[{ value: 'admin', label: t('role.admin') }, { value: 'operator', label: t('role.operator') }]} />}
        </Field>
        <Field label={t('form.extensionLabel')} aside={t('form.extensionAside')} error={errorField === 'extension_id' ? errorMessage : undefined}>
          {(a) => (
            <Select
              {...a} value={extensionId} onValueChange={setExtensionId}
              options={[{ value: '', label: t('form.extensionNone') }, ...extensions.map((e) => ({ value: e.id, label: `${e.number} — ${e.name}` }))]}
            />
          )}
        </Field>
        <Field label={t('form.languageLabel')}>
          {(a) => <Select {...a} value={language} onValueChange={(v) => setLanguage(v as Lang)} options={LANGS.map((l) => ({ value: l, label: l.toUpperCase() }))} />}
        </Field>
        <Field label={t('form.passwordLabel')} required hint={t('form.passwordHint')} error={errorField === 'password' ? errorMessage : undefined}>
          {(a) => <Input {...a} type="password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
      </div>
    </Drawer>
  );
}

function EditUserDrawer({
  user, extensions, isSelf, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  user: ManagedUser;
  extensions: ExtOption[];
  isSelf: boolean;
  onClose: () => void;
  onSubmit: (payload: UpdateUserPayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('users');
  const [fullName, setFullName] = useState(user.full_name);
  const [email, setEmail] = useState(user.email ?? '');
  const [role, setRole] = useState<Role>(user.role);
  const [extensionId, setExtensionId] = useState(user.extension?.id ?? '');
  const [isActive, setIsActive] = useState(user.is_active);
  const [password, setPassword] = useState('');

  const options = user.extension && !extensions.some((e) => e.id === user.extension!.id)
    ? [{ id: user.extension.id, number: user.extension.number, name: user.extension.name }, ...extensions]
    : extensions;

  const dirty = fullName !== user.full_name || email !== (user.email ?? '') || role !== user.role
    || extensionId !== (user.extension?.id ?? '') || isActive !== user.is_active || password.length > 0;
  const valid = fullName.trim().length > 0 && (password.length === 0 || password.length >= 10);

  const submit = () => {
    if (!valid || !dirty) return;
    const payload: UpdateUserPayload = { updated_at: user.updated_at };
    if (fullName.trim() !== user.full_name) payload.full_name = fullName.trim();
    const nextEmail = email.trim() || null;
    if (nextEmail !== (user.email ?? null)) payload.email = nextEmail;
    if (role !== user.role) payload.role = role;
    const nextExt = extensionId || null;
    if (nextExt !== (user.extension?.id ?? null)) payload.extension_id = nextExt;
    if (isActive !== user.is_active) payload.is_active = isActive;
    if (password.length > 0) payload.password = password;
    onSubmit(payload);
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={t('form.editTitle', { name: user.username })}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!dirty || !valid} onClick={submit}>{t('save')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['extension_id', 'password'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}
        <Field label={t('form.fullNameLabel')} required>
          {(a) => <Input {...a} autoFocus value={fullName} onChange={(e) => setFullName(e.target.value)} />}
        </Field>
        <Field label={t('form.emailLabel')} aside={t('form.emailAside')}>
          {(a) => <Input {...a} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Field label={t('form.roleLabel')}>
          {(a) => <Select {...a} disabled={isSelf} value={role} onValueChange={(v) => setRole(v as Role)} options={[{ value: 'admin', label: t('role.admin') }, { value: 'operator', label: t('role.operator') }]} />}
        </Field>
        <Field label={t('form.extensionLabel')} aside={t('form.extensionAside')} error={errorField === 'extension_id' ? errorMessage : undefined}>
          {(a) => (
            <Select
              {...a} value={extensionId} onValueChange={setExtensionId}
              options={[{ value: '', label: t('form.extensionNone') }, ...options.map((e) => ({ value: e.id, label: `${e.number} — ${e.name}` }))]}
            />
          )}
        </Field>
        <Toggle checked={isActive} onCheckedChange={setIsActive} disabled={isSelf} label={t('form.activeLabel')} description={t('form.activeDesc')} />
        <Field label={t('form.passwordLabel')} hint={t('form.passwordHint')} error={errorField === 'password' ? errorMessage : undefined}>
          {(a) => <Input {...a} type="password" placeholder={t('form.passwordPlaceholderEdit')} value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        {password.length > 0 && <p className="text-xs text-muted">{t('form.mustChangeLabel')}</p>}
      </div>
    </Drawer>
  );
}
