import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { Pencil, Plus, ShieldOff, Trash2 } from 'lucide-react';
import {
  useCreateRole, useCreateUser, useDeleteRole, useDeleteUser, useExtensions, useResetUserTotp, useRoles, useUpdateRole,
  useUpdateUser, useUsers,
} from '@/api/queries';
import { isApiError, apiErrorMessage } from '@/api/errors';
import type { CreateRolePayload, CreateUserPayload, ManagedUser, RoleOut, UpdateUserPayload } from '@/api/types';
import type { Lang } from '@/lib/i18n';
import { usePermission } from '@/auth/permissions';
import { useSession } from '@/api/session';
import { formatDateTimeShort } from '@/lib/time';
import { HUDUD_LIST, type Hudud } from '@/shell/screens';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { ConfirmDeleteModal } from '@/ui/ConfirmDeleteModal';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Segmented, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Tabs } from '@/ui/Tabs';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const LANGS: Lang[] = ['uz', 'ru', 'en'];

/** S31 — foydalanuvchilar va rollar: FreePBX uslubidagi ikki tab (M7 §4). */
export function UsersPage() {
  const { t } = useTranslation('users');
  const [tab, setTab] = useState('users');
  // Rollar — faqat `*` uchun (M7 §1: "Tizim" guruhi faqat admin). Foydalanuvchilar tabi ham shu bilan boshqariladi.
  const canManage = usePermission('*');

  return (
    <AppShellPage title={t('title')}>
      <Tabs
        label={t('title')}
        value={tab}
        onValueChange={setTab}
        items={[
          { value: 'users', label: t('tabs.users'), content: <UsersTab canManage={canManage} /> },
          { value: 'roles', label: t('tabs.roles'), content: <RolesTab canManage={canManage} /> },
        ]}
      />
    </AppShellPage>
  );
}

// ─────────────────────────────────── Foydalanuvchilar tabi ───────────────────────────────────

function UsersTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('users');
  const { data, isLoading, isError, refetch } = useUsers();
  const { data: extensionsData } = useExtensions({ page: 1, size: 200 });
  const { data: rolesData } = useRoles();
  const myId = useSession((s) => s.user?.id);
  const toast = useToast();

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [deleting, setDeleting] = useState<ManagedUser | null>(null);
  // M10 C B2 — admin foydalanuvchining 2FA'sini tiklaydi (qurilma yo'qolganda, kod kiritmasdan).
  const [resettingTotp, setResettingTotp] = useState<ManagedUser | null>(null);

  const createM = useCreateUser();
  const updateM = useUpdateUser();
  const deleteM = useDeleteUser();
  const resetTotpM = useResetUserTotp();

  const closeCreate = () => { setCreateOpen(false); createM.reset(); };
  const closeEdit = () => { setEditing(null); updateM.reset(); };

  const roleOptions = (rolesData?.items ?? []).map((r) => ({ value: r.name, label: r.is_system ? t(`role.${r.name}`) : r.name }));
  const roleLabel = (role: string) => roleOptions.find((o) => o.value === role)?.label ?? role;

  const columns: Column<ManagedUser>[] = [
    { key: 'username', header: t('column.username'), sortValue: (r) => r.username, cell: (r) => <span className="num font-medium">{r.username}</span> },
    { key: 'full_name', header: t('column.fullName'), sortValue: (r) => r.full_name, cell: (r) => <span className="block max-w-[220px] truncate">{r.full_name}</span> },
    { key: 'role', header: t('column.role'), cell: (r) => <Badge tone={r.role === 'admin' ? 'accent' : 'neutral'}>{roleLabel(r.role)}</Badge> },
    { key: 'extension', header: t('column.extension'), cell: (r) => <span className="num text-sm text-muted">{r.extension ? `${r.extension.number} — ${r.extension.name}` : '—'}</span> },
    { key: 'status', header: t('column.status'), cell: (r) => <Badge tone={r.is_active ? 'success' : 'neutral'}>{t(r.is_active ? 'status.active' : 'status.inactive')}</Badge> },
    { key: 'last_login_at', header: t('column.lastLogin'), sortValue: (r) => r.last_login_at ?? '', cell: (r) => <span className="num text-sm text-muted">{r.last_login_at ? formatDateTimeShort(r.last_login_at) : t('neverLoggedIn')}</span> },
    { key: 'totp', header: t('column.totp'), cell: (r) => <Badge tone={r.totp_enabled ? 'success' : 'neutral'}>{t(r.totp_enabled ? 'totp.enabled' : 'totp.disabled')}</Badge> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          {r.totp_enabled && (
            <Button size="sm" variant="ghost" iconOnly icon={<ShieldOff />} aria-label={t('totp.resetAriaLabel', { name: r.username })} disabled={!canManage} onClick={() => setResettingTotp(r)} />
          )}
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: r.username })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: r.username })} disabled={!canManage || r.id === myId} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  const takenExtensionIds = new Set((data?.items ?? []).filter((u) => u.id !== editing?.id).map((u) => u.extension?.id).filter(Boolean));
  const availableExtensions = (extensionsData?.items ?? []).filter((e) => !takenExtensionIds.has(e.id));

  return (
    <>
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
          roleOptions={roleOptions}
          onClose={closeCreate}
          onSubmit={(payload) => createM.mutate(payload, {
            onSuccess: () => { closeCreate(); toast({ kind: 'success', title: t('toast.added') }); },
            onError: (e) => { if (isApiError(e) && e.code === 'forbidden') toast({ kind: 'error', title: apiErrorMessage(e) }); },
          })}
          pending={createM.isPending}
          // Maydon xatosi — serverning oʻz xabari (dinamik, masalan «103 allaqachon «race»ga bogʻlangan»);
          // umumiy xatolar (masalan `forbidden`) toast orqali koʻrsatiladi — qarang onError.
          errorField={isApiError(createM.error) ? createM.error.field : undefined}
          errorMessage={isApiError(createM.error) ? createM.error.message : undefined}
        />
      )}

      {editing && (
        <EditUserDrawer
          user={editing}
          extensions={availableExtensions}
          roleOptions={roleOptions}
          isSelf={editing.id === myId}
          onClose={closeEdit}
          onSubmit={(payload) => updateM.mutate({ id: editing.id, payload }, {
            onSuccess: () => { closeEdit(); toast({ kind: 'success', title: t('toast.saved') }); },
            onError: (e) => { if (isApiError(e) && e.code === 'forbidden') toast({ kind: 'error', title: apiErrorMessage(e) }); },
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
                onError: (e) => { toast({ kind: 'error', title: t('toast.deleteFailed'), description: apiErrorMessage(e) }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      />

      <Modal
        open={!!resettingTotp}
        onOpenChange={(v) => !v && setResettingTotp(null)}
        title={resettingTotp ? t('totp.resetModalTitle', { name: resettingTotp.username }) : ''}
        description={resettingTotp ? t('totp.resetModalBody', { name: resettingTotp.username }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setResettingTotp(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={resetTotpM.isPending}
              onClick={() => resettingTotp && resetTotpM.mutate(resettingTotp.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('totp.resetToast', { name: resettingTotp.username }) }); setResettingTotp(null); },
                onError: (e) => { toast({ kind: 'error', title: t('toast.deleteFailed'), description: apiErrorMessage(e) }); setResettingTotp(null); },
              })}
            >
              {t('totp.resetAction')}
            </Button>
          </>
        }
      />
    </>
  );
}

type ExtOption = { id: string; number: string; name: string };
type RoleOption = { value: string; label: string };

function CreateUserDrawer({
  extensions, roleOptions, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  extensions: ExtOption[];
  roleOptions: RoleOption[];
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
  // Qattiq «operator» — `useRoles()` hali yuklanmagan boʻlsa ham (poyga holati) tanlov boʻsh qolmasligi uchun;
  // rollar roʻyxati kelganda ham «operator» tizim roli sifatida doim mavjud.
  const [role, setRole] = useState('operator');
  const [extensionId, setExtensionId] = useState('');
  const [language, setLanguage] = useState<Lang>('uz');
  const [password, setPassword] = useState('');

  const valid = username.trim().length > 0 && fullName.trim().length > 0 && password.length >= 10 && role.length > 0;

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
        {errorMessage && !['username', 'extension_id', 'password', 'role'].includes(errorField ?? '') && (
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
        <Field label={t('form.roleLabel')} error={errorField === 'role' ? errorMessage : undefined}>
          {(a) => <Select {...a} value={role} onValueChange={setRole} options={roleOptions} />}
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
  user, extensions, roleOptions, isSelf, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  user: ManagedUser;
  extensions: ExtOption[];
  roleOptions: RoleOption[];
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
  const [role, setRole] = useState(user.role);
  const [extensionId, setExtensionId] = useState(user.extension?.id ?? '');
  const [isActive, setIsActive] = useState(user.is_active);
  const [password, setPassword] = useState('');

  const options = user.extension && !extensions.some((e) => e.id === user.extension!.id)
    ? [{ id: user.extension.id, number: user.extension.number, name: user.extension.name }, ...extensions]
    : extensions;
  // Joriy rol roʻyxatda yoʻq boʻlsa ham (masalan oʻchirilgan maxsus rol) — tanlovda koʻrinishi uchun qoʻshamiz.
  const roleSelectOptions = roleOptions.some((o) => o.value === user.role) ? roleOptions : [{ value: user.role, label: user.role }, ...roleOptions];

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
        {errorMessage && !['extension_id', 'password', 'role'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}
        <Field label={t('form.fullNameLabel')} required>
          {(a) => <Input {...a} autoFocus value={fullName} onChange={(e) => setFullName(e.target.value)} />}
        </Field>
        <Field label={t('form.emailLabel')} aside={t('form.emailAside')}>
          {(a) => <Input {...a} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Field label={t('form.roleLabel')} error={errorField === 'role' ? errorMessage : undefined}>
          {(a) => <Select {...a} disabled={isSelf} value={role} onValueChange={setRole} options={roleSelectOptions} />}
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

// ─────────────────────────────────── Rollar tabi (M7 §2/§4) ───────────────────────────────────

type PermLevel = 'none' | 'view' | 'edit';

function levelsFromPermissions(perms: string[]): Record<Hudud, PermLevel> {
  const result = {} as Record<Hudud, PermLevel>;
  for (const hudud of HUDUD_LIST) result[hudud] = perms.includes(`${hudud}:edit`) ? 'edit' : perms.includes(`${hudud}:view`) ? 'view' : 'none';
  return result;
}

function permissionsFromLevels(levels: Record<Hudud, PermLevel>): string[] {
  return HUDUD_LIST.flatMap((hudud) => (levels[hudud] === 'none' ? [] : [`${hudud}:${levels[hudud]}`]));
}

function samePermissions(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const sa = [...a].sort();
  const sb = [...b].sort();
  return sa.every((v, i) => v === sb[i]);
}

/** Jadvaldagi "qisqa ruxsatlar xulosasi" ustuni. */
function summarizePermissions(perms: string[], t: TFunction): string {
  if (perms.includes('*')) return t('permSummary.all');
  const parts = HUDUD_LIST
    .filter((h) => perms.includes(`${h}:view`) || perms.includes(`${h}:edit`))
    .map((h) => `${t(`hudud.${h}`)} (${t(perms.includes(`${h}:edit`) ? 'permLevel.edit' : 'permLevel.view')})`);
  if (perms.includes('calls:read:own')) parts.push(t('permSummary.ownCalls'));
  return parts.length ? parts.join(', ') : t('permSummary.none');
}

function RolesTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('users');
  const { data, isLoading, isError, refetch } = useRoles();
  const toast = useToast();

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<RoleOut | null>(null);
  const [deleting, setDeleting] = useState<RoleOut | null>(null);

  const createM = useCreateRole();
  const updateM = useUpdateRole();
  const deleteM = useDeleteRole();

  const closeEditor = () => { setCreateOpen(false); setEditing(null); createM.reset(); updateM.reset(); };

  // Tizim rollari uchun koʻrsatiladigan nom (jadval katakchasi) va aria-label bir xil — aks holda
  // aria-label xom `r.name` (masalan «admin») bilan koʻrinadigan tarjima («Admin») mos kelmay qoladi.
  const roleLabel = (r: RoleOut) => (r.is_system ? t(`role.${r.name}`) : r.name);

  const columns: Column<RoleOut>[] = [
    {
      key: 'name', header: t('rolesColumn.name'), sortValue: (r) => r.name, cell: (r) => (
        <span className="inline-flex items-center gap-2">
          <span className="font-medium">{roleLabel(r)}</span>
          {r.is_system && <Badge tone="neutral">{t('rolesColumn.systemBadge')}</Badge>}
        </span>
      ),
    },
    { key: 'user_count', header: t('rolesColumn.userCount'), sortValue: (r) => r.user_count, cell: (r) => <span className="num text-sm text-muted">{r.user_count}</span> },
    { key: 'permissions', header: t('rolesColumn.permissions'), cell: (r) => <span className="text-sm text-muted">{summarizePermissions(r.permissions, t)}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('rolesEditAriaLabel', { name: roleLabel(r) })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('rolesDeleteAriaLabel', { name: roleLabel(r) })} disabled={!canManage || r.is_system} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  return (
    <>
      <DataTable
        caption={t('rolesCaption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => r.name}
        searchPlaceholder={t('rolesSearch')}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('rolesEmpty.title'), body: t('rolesEmpty.body'), action: canManage ? <Button size="sm" onClick={() => setCreateOpen(true)}>{t('rolesEmpty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setCreateOpen(true)}>{t('newRole')}</Button> : undefined}
      />

      {(createOpen || editing) && (
        <RoleEditorModal
          role={editing}
          onClose={closeEditor}
          onSubmit={(payload) => {
            const onError = (e: unknown) => { if (isApiError(e) && e.code === 'forbidden') toast({ kind: 'error', title: apiErrorMessage(e) }); };
            if (editing) {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: () => { closeEditor(); toast({ kind: 'success', title: t('toast.roleSaved') }); },
                onError,
              });
            } else {
              createM.mutate(payload, {
                onSuccess: () => { closeEditor(); toast({ kind: 'success', title: t('toast.roleAdded') }); },
                onError,
              });
            }
          }}
          pending={createM.isPending || updateM.isPending}
          // Maydon xatosi — serverning oʻz xabari (masalan `role_name_taken` dinamik nomi bilan);
          // `forbidden` kabi umumiy xatolar toast orqali koʻrsatiladi (qarang onError).
          errorField={isApiError(createM.error) ? createM.error.field : isApiError(updateM.error) ? updateM.error.field : undefined}
          errorMessage={isApiError(createM.error) ? createM.error.message : isApiError(updateM.error) ? updateM.error.message : undefined}
        />
      )}

      <ConfirmDeleteModal
        open={!!deleting}
        onClose={() => { setDeleting(null); deleteM.reset(); }}
        onConfirm={() => deleting && deleteM.mutate(deleting.id, {
          onSuccess: () => { toast({ kind: 'success', title: t('toast.roleDeleted', { name: deleting.name }) }); setDeleting(null); },
          onError: (e) => { toast({ kind: 'error', title: t('toast.roleDeleteFailed'), description: apiErrorMessage(e) }); setDeleting(null); },
        })}
        loading={deleteM.isPending}
        title={deleting ? t('roleDeleteModal.title', { name: deleting.name }) : ''}
        body={deleting && deleting.user_count > 0 ? t('roleDeleteModal.inUse', { count: deleting.user_count }) : deleting ? t('roleDeleteModal.body', { name: deleting.name }) : ''}
        cancelLabel={t('cancel')}
        deleteLabel={t('delete')}
      />
    </>
  );
}

function RoleEditorModal({
  role, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  role: RoleOut | null;
  onClose: () => void;
  onSubmit: (payload: CreateRolePayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('users');
  const readOnly = !!role?.is_system;
  const [name, setName] = useState(role?.name ?? '');
  const [levels, setLevels] = useState<Record<Hudud, PermLevel>>(() => levelsFromPermissions(role?.permissions ?? []));

  const permissions = permissionsFromLevels(levels);
  const valid = name.trim().length >= 1 && name.trim().length <= 40;
  const dirty = role ? name !== role.name || !samePermissions(permissions, role.permissions) : true;

  const submit = () => {
    if (readOnly || !valid || !dirty) return;
    onSubmit({ name: name.trim(), permissions });
  };

  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={role ? (readOnly ? t('roleForm.viewTitle', { name: t(`role.${role.name}`) }) : t('roleForm.editTitle', { name: role.name })) : t('roleForm.newTitle')}
      footer={
        readOnly ? (
          <Button variant="ghost" onClick={onClose}>{t('close')}</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
            <Button variant="primary" loading={pending} disabled={!valid || !dirty} onClick={submit}>{role ? t('save') : t('add')}</Button>
          </>
        )
      }
    >
      <div className="flex flex-col gap-4">
        {readOnly ? (
          <>
            <p className="font-medium text-fg">{t(`role.${role!.name}`)}</p>
            <p className="rounded-md bg-surface-2 px-3 py-2 text-sm text-muted">{t(`roleForm.systemDesc.${role!.name}`)}</p>
          </>
        ) : (
          <>
            {errorMessage && errorField !== 'name' && errorField !== 'permissions' && <p className="text-sm text-danger">{errorMessage}</p>}
            <Field label={t('roleForm.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
              {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
            </Field>
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium text-fg">{t('roleForm.permissionsLabel')}</p>
              {errorField === 'permissions' && errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}
              <div className="flex flex-col divide-y divide-line rounded-md border border-line">
                {HUDUD_LIST.map((hudud) => (
                  <div key={hudud} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="text-sm text-fg">{t(`hudud.${hudud}`)}</span>
                    <Segmented
                      label={t(`hudud.${hudud}`)}
                      value={levels[hudud]}
                      onChange={(v) => setLevels((prev) => ({ ...prev, [hudud]: v }))}
                      options={[
                        { value: 'none', label: t('permLevel.none') },
                        { value: 'view', label: t('permLevel.view') },
                        { value: 'edit', label: t('permLevel.edit') },
                      ]}
                    />
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
