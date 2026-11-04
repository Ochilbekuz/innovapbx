---
id: trunks
title: Trunks
group: connect
order: 10
path: /trunks
summary: Connections (trunks) to SIP carriers — host/port, authentication, codecs, health status, testing.
---

# Trunks

A trunk is the SIP connection between your Innova PBX and a telephone carrier (or another PBX); it's how outbound calls leave and inbound calls arrive. On this page you can add trunks, configure them, monitor their health status, and test them.

## Where to find it

Menu: **Connectivity → Trunks**. Who sees it: the `connect:view` permission. Adding/editing/deleting requires `connect:edit`; without it, the page shows a **"You don't have permission to manage trunks — view and test only"** note (testing works with view access too).

## Core concepts

- **Authentication method**:
  - **By IP (CIDR)** — checks that packets from the carrier come from the specified network(s); no login/password needed.
  - **Registration (login/password)** — Innova PBX registers with the carrier using a login/password (classic SIP registration).
- **Health status** — **Up**, **No connection**, **Not checked**, **Disabled**; in Registration mode there is also a **Registered** / **rejected** / **pending** indicator.
- **Test** — sends an immediate test request to the trunk and shows whether it is reachable and the response time.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **Name** | A recognizable name for the trunk | — (required) |
| **Host** | The carrier's IP or domain | `sip.operator.uz` (required) |
| **Port** | SIP port | 1–65535 range, default: 5060 |
| **Authentication method** | **By IP (CIDR)** or **Registration (login/password)** | — |
| **Match CIDR** | *(IP mode only)* Which networks' packets are accepted as belonging to this trunk | One CIDR per line, e.g. `203.0.113.0/24` |
| **Login** / **Password** | *(Registration mode only)* Credentials provided by the carrier | Leave the password blank to keep the current one unchanged |
| **From domain** | *(Registration mode only)* The domain/host used for registration | `sip.operator.uz` |
| **Outbound Caller ID** | The number shown on outbound calls placed through this trunk | optional, e.g. `+998712000000` |
| **Codecs** | Which audio codecs are used | `ulaw`, `alaw`, `g722`, `opus` — at least one must be selected |
| **Max. channels** | How many simultaneous calls this trunk allows | empty — unlimited |
| **Enabled** | Temporarily disable the trunk | default: enabled |

## How to

### Add a new trunk (by IP)
1. Click **New trunk**.
2. Enter **Name**, **Host**, **Port**, and choose **By IP (CIDR)** as the **Authentication method**.
3. Enter the carrier's network in the **Match CIDR** field.
4. Select the required **Codecs**, and optionally enter **Outbound Caller ID** and **Max. channels**.
5. Click **Add**.

### Add a new trunk (via Registration)
1. Click **New trunk**, and choose **Registration (login/password)** as the **Authentication method**.
2. Fill in the **Login**, **Password**, and **From domain** fields.
3. Select codecs, then click **Add**.

### Test a trunk
1. In the table, click the plug icon on the trunk's row.
2. The dialog that opens shows a **Success**/**Failure** result and the response time (ms).

### Delete a trunk
1. Click the **Delete** icon on the row.
2. Read the warning — outbound/inbound traffic through this trunk stops immediately — and confirm.

## Tips and limitations

> [!WARNING]
> Deleting a trunk takes effect immediately — if the trunk is used in outbound routes, those routes will stop working. Before deleting, check which routes use this trunk in [Outbound routes](/docs/outbound).

> [!TIP]
> If you don't need to change the password, leave the **Password** field blank — the current password stays unchanged.

> [!TIP]
> At least one codec must be selected; choosing a codec the carrier doesn't support can degrade call quality.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Invalid host" | The Host field is not a valid IP or domain | Enter a valid IP/domain |
| "'...' is not in CIDR format" | A line in the **Match CIDR** field is not written as CIDR | Use a format like `203.0.113.0/24` |
| "Password required in Register mode" | No password was entered in Registration mode (and the trunk doesn't already have a saved password) | Fill in the Password field |
| **No connection** status | The carrier's server is not responding, or there's a network issue | Check the host/port, diagnose with the **Test** button |
| **Registration rejected** | Login/password is incorrect or blocked by the carrier | Verify the login/password with the carrier and re-enter them |

## Related sections

- [Outbound routes](/docs/outbound)
- [Inbound routes](/docs/inbound)
