---
id: users
title: Users
group: system
order: 110
path: /settings/users
summary: Panel user accounts (login/password), roles, and per-area view/edit permissions.
---

# Users

A **user** here is a panel access account (login + password) — not an internal extension. One
user can be linked to an extension, but the two are managed separately: this page controls who
can sign in to the panel and what they're allowed to see/change.

## Where

Menu: **System → Users**, with two tabs: **Users** and **Roles**. Who can see it: only a user
with `*` (full administrator) permission can add, edit, or delete; others can only view.

## Key concepts

- **User** — login, full name, optional email, a role, an optional linked extension,
  panel language (uz/ru/en), active/disabled status, and 2FA on/off.
- **System roles** — **Admin** (full rights to every area) and **Operator** (sees only
  their own call history). These can't be edited or deleted — opening one shows it as view-only.
- **Custom role** — a role created beyond the system roles, with a **None/View/Edit**
  level set per area (Monitoring, Extensions, Connectivity, Routing, Apps, Reports).
- **System-group pages** aren't included in this per-area list — only a full administrator
  (`*`) can reach them; no custom role grants access.
- **Extension link** — one extension can only be linked to **one** panel user.
- **2FA reset** — an administrator can reset a user's 2FA without needing their code,
  which forces them to set it up again on their next sign-in.
- **Self-restriction** — you can't delete your own account or change your own role or
  active status.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Login | Sign-in name | — |
| Full name | — | — |
| Email | Optional | — |
| Role | — | Default: Operator |
| Extension | Optional link | Default: Not linked |
| Language | — | — |
| Password | — | At least 10 characters |
| Active | — | — |
| **Role** → Name | — | 1–40 characters |
| **Role** → Area level | None / View / Edit | Default: None |

## How to

### Add a new user
1. On the **Users** tab, click **New user**.
2. Fill in login, full name, email, role, extension, language, and password (at least 10
   characters).
3. Click **Add**.

### Edit a user
1. Click the row or the pencil icon.
2. Change the fields you need — leave the password blank to keep it unchanged.
3. Click **Save**.

### Reset a user's 2FA
1. Click the shield icon on the row of a user with 2FA enabled.
2. Confirm — the user can now sign in without a code, but must re-link 2FA on their next
   sign-in.

### Delete a user
1. Click the trash icon and confirm in the dialog — the account is permanently deleted.
2. You can't delete your own account — the button is disabled for yourself.

### Create a custom role
1. On the **Roles** tab, click **New role**.
2. Enter a name (1–40 characters) and set **None/View/Edit** for each area row.
3. Click **Add**.

### Edit or delete a role
1. Click the pencil icon to change the name/permissions, then **Save**; click the trash
   icon to delete.
2. If users are linked to the role, reassign them first.
3. The system roles **Admin**/**Operator** can't be deleted or edited — opening one shows
   it as view-only.

## Tips and limits

> [!WARNING]
> System-group pages can't be granted through a custom role — only a full administrator
> (`*`) can reach them.

> [!TIP]
> Operators usually only need **View** level — grant **Edit** only where editing rights
> are genuinely required.

- One extension can't be linked to two users.
- You can't change your own role or active status.
- A role with linked users can't be deleted.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "N users are linked to this role" | The role has linked users | Reassign them to another role first |
| New user wasn't added (login error) | The login is already taken | Choose a different login |
| Extension isn't in the dropdown | It's already linked to another user | Remove the old link first |
| "Could not delete" | A server error or insufficient permission | Retry, or check your permission |
| Edit/delete buttons are disabled | You don't have full administrator permission | Ask an admin for `*` |

## Related sections

- [Audit log](/docs/audit)
- [Security](/docs/security)
