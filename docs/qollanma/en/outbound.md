---
id: outbound
title: Outbound routes
group: connect
order: 30
path: /outbound
summary: Rules for placing outbound calls — patterns, trunk chain, PIN, international calls, simulator.
---

# Outbound routes

Outbound routes determine which trunk(s) a number dialed from an extension goes out through, and how it is
rewritten (prefix stripped/added) before leaving. Routes work as a priority-ordered list — the first
matching route from the top is used.

## Where

Menu: **Connectivity → Outbound routes**. Who can see it: the `connect:view` permission.
Adding/editing/deleting/reordering requires `connect:edit`; without it, the notice **"You don't have
permission to manage outbound routes — view and test only"** is shown (testing works with view permission
too).

## Key concepts

- **Priority** — routes are checked top to bottom; the first one matching the dialed number is
  used. The list can be reordered by dragging.
- **Pattern rules** — each route can have several rows: **Prepend** (value added to the front
  of the number), **Prefix** (part stripped off), **Pattern** (which numbers it matches, e.g.
  `998XXXXXXXXX`), and a row-specific **CallerID**.
- **Trunk chain** — which trunk(s) the call goes out through: the first is **Primary**, the
  rest are **Backup 1**, **Backup 2**, and so on — if the primary fails, the next one is tried. Each
  trunk is shown together with its health status.
- **PIN vs PIN set** — two independent protections can work together on one route: a plain
  **PIN** field (one code specific to this route) and a separate **PIN set** (manages multiple
  codes/users). **Either one is enough** — entering either correctly lets the call through.
- **International calls** — a separate toggle; enabling it shows a warning about toll-fraud risk
  (large charges from misuse).
- **Who can use it** — a route can be limited to **All** extensions or a list of **Selected**
  extensions.
- **Simulator** — a built-in tool where you pick an extension and a number to see, in real
  time, how the route actually behaves (allowed/rejected, which trunk chain, step-by-step reasons).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **Name** | A recognizable name for the route | — (required) |
| **Enabled** | Temporarily disables the route | default: enabled |
| **Pattern rules** | Prepend / Prefix / Pattern / CallerID rows | Pattern: `998XXXXXXXXX` |
| **Trunk chain** | Order of trunks used for the outbound call | First one — Primary |
| **Outbound Caller ID** | Overrides the trunk's default caller ID for this route | blank — uses the trunk's default |
| **Override** toggle | This route's CallerID takes priority over the extension's own caller ID | default: off |
| **PIN** + PIN value | Requires a code specific to this route | digits only, 4–12 characters |
| **PIN set** | Uses a separately managed set of codes | default: Not selected |
| **International calls** | Allows outbound calls to international destinations | default: off |
| **Who can use it** | **All** or **Selected** extensions | default: All |

## How to

### Add a new outbound route
1. Click **New route**.
2. Enter a **Name**.
3. Enter at least one **Pattern** rule (e.g. `998XXXXXXXXX`), and fill in **Prepend**/**Prefix**
   if needed.
4. Select at least one trunk in the **Trunk chain**.
5. Click **Add**.

### Configure patterns and the trunk chain
1. Edit the route.
2. Use **Add rule** to add more pattern rows; a row with an error is underlined in red below it.
3. Add/remove trunks in the **Trunk chain**, reorder by dragging — the first one becomes **Primary**.
4. Click **Save**.

### Protect a route with a PIN or PIN set
1. Edit the route.
2. Enable **PIN** and enter the code, and/or pick an existing set from **PIN set**.
3. Click **Save** — dialing through this route now asks for the code.

### Enable international calls
1. Edit the route.
2. Enable the **International calls** toggle — read the warning banner.
3. Click **Save**.

### Restrict a route to specific extensions
1. Edit the route.
2. Choose **Selected** under **Who can use it**.
3. Add the extensions you need to the list (remove any you don't need).
4. Click **Save**.

### Use the simulator
1. In the **Simulator** section of the side panel, enter the extension and the number
   to test.
2. Click **Test**.
3. The result shows **Allowed**/**Rejected**, which trunk chain was used, and a step-by-step
   list of reasons.

### Reorder routes by priority
1. In the list, grab a route row by its drag handle and drop it in a new position.
2. The new order is saved automatically.

### Delete a route
1. Click the **Delete** icon on the row.
2. If the route is still in use (e.g. referenced by an extension's list), the system shows
   where it's used in and doesn't allow deletion — remove it from those places first.

## Tips and limits

> [!WARNING]
> Be careful before enabling **International calls** — misuse (e.g. a compromised extension)
> can lead to large international charges (toll fraud). Only grant it to extensions that genuinely
> need it.

> [!TIP]
> If both PIN and a PIN set are used on one route, entering **either** code correctly is
> enough — knowing both isn't required.

> [!TIP]
> If **Outbound Caller ID** is left blank, the trunk's default caller ID is used; fill it in
> only when this route needs to show a specific number.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| A red underline on a pattern row | The pattern is written in the wrong format | Check the part before the shown marker and fix it |
| "At least one trunk is required" | The trunk chain was left empty | Add at least one trunk to the **Trunk chain** |
| Can't delete the route | The route is still in use elsewhere (e.g. on an extension) | Remove it from the listed usages first |
| Call "Rejected" (in the simulator) | No pattern matched, the trunk is down, or the PIN was wrong | Check the step-by-step reasons in the simulator and fix the relevant field |
| Can't dial an international number | **International calls** is disabled | Enable it on the route (after reading the warning) |

## Related sections

- [Trunks](/docs/trunks)
- [PIN sets](/docs/pinsets)
- [Inbound routes](/docs/inbound)
