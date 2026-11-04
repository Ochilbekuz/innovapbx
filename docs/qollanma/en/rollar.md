---
id: rollar
title: Roles and permissions
group: start
order: 50
summary: The role/permission system that defines who can see and change what in Innova PBX.
---

# Roles and permissions

Every user in Innova PBX is assigned a **role** — and the role determines which sections they
can view and change. There are two ready-made (system) roles — **Admin** and **Operator** — and
you can also create your own custom roles.

## Key concepts

- **Area** — the panel's sections are split into six groups: **Monitoring** (dashboard,
  live monitor), **Extensions** (extensions, devices, voicemail), **Connectivity** (trunks,
  inbound/outbound routes, PIN sets, CID sources), **Routing** (business hours, IVR, queues, ring
  groups, etc.), **Apps** (audio, conference, parking, blacklist, campaigns, etc.), **Reports**
  (call history, reports, recordings).
- **Permission level** — set independently per area: **None** (not visible),
  **View** (read-only), **Edit** (full management — Edit includes View).
- **Admin** role — **full** access to every area, plus admin-only sections such as
  users, roles, system settings, and backups. Can't be changed or deleted.
- **Operator** role — only sees **their own call history** and works from their personal
  cabinet ([My portal](/docs/portal)); has no access to any other area. Can't be changed or
  deleted.
- **Custom role** — lets you choose a separate level per area to build your own set of
  permissions (e.g. a technician who can only edit "Connectivity" and only view "Reports").
- Users, roles, and the other "System" sections (settings, security, backups, audit, etc.)
  are **Admin-only** — a custom role can never be granted access to them.
- A role change takes effect **immediately** — the user doesn't need to sign in again.

## How to

### Create a new custom role
1. In the **Users** section, open the **Roles** tab (admin rights required).
2. Click **New role** and enter a role name.
3. Choose the level you need (**None** / **View** / **Edit**) for each area row.
4. Click **Add**.

### Assign a role to a user
1. On the **Users** tab, edit the user you need (or create a new one).
2. Choose the role you need (system or custom) in the **Role** field, and click **Save**.

### Change an existing custom role
1. On the **Roles** tab, edit the role row you need.
2. Change the area levels as needed and click **Save** — the change takes effect
   immediately for every user with that role.

## Tips and limits

> [!WARNING]
> If an area only has the **View** level, that user can't add, change, or delete
> anything in that section — the buttons are hidden or disabled.

> [!TIP]
> The system roles (Admin, Operator) can't be changed — create a custom role with your
> own permission set instead.

> [!WARNING]
> A role with users assigned to it can't be deleted — move those users to another role
> first.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| A needed section doesn't show in the menu | The user's role doesn't have **View**/**Edit** for that area | Raise the area level on the role in [Users](/docs/users) |
| Buttons (add/edit/delete) are hidden or disabled | The role only has **View** for that area | Grant the role **Edit** if needed |
| Can't delete a role | Users are still assigned to it | Move those users to another role first |
| "Can't change a system role" | Attempting to edit Admin or Operator | Create a custom role instead |

## Related sections

- [Users](/docs/users)
- [My portal](/docs/portal)
- [First setup](/docs/birinchi-sozlash)
