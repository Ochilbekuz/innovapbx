---
id: pinsets
title: PIN sets
group: connect
order: 40
path: /pinsets
summary: Create and manage PIN sets that require a code before placing an outbound call.
---

# PIN sets

A PIN set is a list of PINs that, once attached to an [outbound route](/docs/outbound), requires the user to enter a code before the call connects. A set can contain multiple PINs — each with its own label (e.g. an employee's name), so you can track who placed a call with which code.

## Where to find it

Menu: **Connectivity → PIN sets**. Who sees it: the `connect:view` permission. Adding/editing/deleting/managing PINs requires `connect:edit`; without it, a **"You don't have permission to manage PIN sets — view only"** note appears.

## Core concepts

- **PIN set** — a container defined by a name and settings (record in CDR); it has no effect on its own until it's attached to an [outbound route's](/docs/outbound) **PIN set** field.
- **Record in CDR** — when enabled, which PIN (with its label) was used is saved in the call history — so you can later check who called using which code.
- **Each PIN** — a 4–12 digit numeric code plus a label (e.g. an employee's or department's name). The label is required — you can't enter just a number.
- A single PIN can't be used in more than one set — entering an already-used PIN causes an error.

## Fields

**Sets** table:

| Column | What it shows |
|---|---|
| **Name** | The set's name |
| **Record in CDR** | Enabled (✓) or disabled (—) |
| **PIN count** | Number of PINs in the set |
| **Used in** | Names of the outbound routes using this set |

**Add/edit set** form:

| Field | What it does | Example / default |
|---|---|---|
| **Name** | A recognizable name for the set | — (required) |
| **Record in CDR** | Save the PIN used in the call history | default: disabled |

**Manage PINs** dialog:

| Field | What it does | Example / default |
|---|---|---|
| **Add new PINs** | One PIN per line, format: `pin;label` | `1234;Director` |

## How to

### Create a new PIN set
1. Click **New set**.
2. Enter a **Name**, and enable **Record in CDR** if needed.
3. Click **Add**.

### Add a PIN to a set
1. In the table, click the PIN (key) icon on the set's row.
2. In the dialog, enter one code per line in the **Add new PINs** field, in the format `pin;label` (e.g. `1234;Director`).
3. Click **Add** — if there's an error, the line it's on is shown.

### Delete a PIN
1. Open the set, and click the X button on the row of the label you want to remove from the PIN list.

### Attach a set to an outbound route
1. Edit the route you need in [Outbound routes](/docs/outbound).
2. Select the set you created in the **PIN set** field, then click **Save**.

### Delete a set
1. Click the **Delete** icon on the row.
2. If the set is still used in an outbound route, the system shows which routes and blocks deletion — remove it from the route first.

## Tips and limitations

> [!TIP]
> It's recommended to create a separate PIN and label for each employee/department — that way, when **Record in CDR** is enabled, you can clearly see who used which route.

> [!WARNING]
> A PIN set has no effect on its own — it only starts working once it's attached to an outbound route's **PIN set** field.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Line {{row}} is invalid — format is «PIN;label»..." | The line is in the wrong format (no `;`, PIN isn't 4–12 digits, or the label is empty) | Write each line as `1234;Label` |
| "This PIN is already in use" | The entered code is already used elsewhere | Choose a different code |
| Can't delete the set | The set is still used in an outbound route | Remove it from the shown route(s) first |
| The call doesn't ask for a PIN | The set isn't attached to any outbound route | Edit the route in [Outbound routes](/docs/outbound) and select the **PIN set** |

## Related sections

- [Outbound routes](/docs/outbound)
- [Trunks](/docs/trunks)
