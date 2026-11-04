---
id: birinchi-sozlash
title: First setup
group: start
order: 30
path: /setup
summary: The page for entering the admin account and network settings the first time you open the panel after installation.
---

# First setup

After installation finishes, the first time you open the web panel a two-step setup page
appears automatically: creating the admin account and entering network settings. This page
appears only **once** — once the admin account is created it's closed for good and can't be
reopened.

## Key concepts

- **Setup code** — a one-time code shown once in the console/terminal when
  [Installation](/docs/ornatish) finishes; needed only on this page, and only once.
- The page has two steps: **1. Administrator** and **2. Language & network**.
- After step 2 there's no separate "Apply Config" step — every change takes effect
  immediately.

## Fields

**Step 1 — Administrator**

| Field | What it does | Example / default |
|---|---|---|
| Setup code | Required, must be correct | — |
| Login | At least 3 characters | — |
| Full name | At least 2 characters | — |
| Password | At least 8 characters | — |
| Panel language | uz/ru/en | Default: Uzbek |

**Step 2 — Language & network**

| Field | What it does | Example / default |
|---|---|---|
| Time zone | Asia/Tashkent or Asia/Samarkand, both UTC+5 | Required |
| External IP address | Optional, IPv4 format | — |
| Local networks (CIDR) | Required, at least one valid line | Default: `10.0.0.0/8` |

## How to

### Create the admin account
1. On the page that opens first, copy and paste the **setup code** from the
   console/terminal.
2. Enter the **login**, **full name**, and **password**; optionally choose the **panel
   language**.
3. Click **Continue** — an error is shown if the code or a field is wrong.

### Configure language and network
1. Choose the **time zone** (Asia/Tashkent or Asia/Samarkand).
2. If you know the server's external IP, enter it in **External IP address** — you can
   leave it blank and set it later from [Settings → SIP](/docs/trunks).
3. Enter **Local networks (CIDR)**, one per line, e.g. `10.0.0.0/8` — a default value is
   pre-filled, change it if needed.
4. Click **Finish** — you're automatically signed in with the admin account and
   redirected to [Dashboard](/docs/dashboard).

## Tips and limits

> [!WARNING]
> The setup code is used only once — once the admin account is created, this page closes
> for good, the code can't be reused, and no new code is issued.

> [!TIP]
> **Local networks (CIDR)** must be entered correctly — this list is used so extensions
> work correctly behind NAT, e.g. on an office local network; if you're unsure, leave the
> default `10.0.0.0/8` and refine it later if needed.

> [!TIP]
> You can leave **External IP address** blank — it's settable any time later from the
> Settings section.

> [!NOTE]
> After step 2 there's no separate confirmation (Apply Config) step — the network
> settings you entered start working immediately.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Setup code incorrect" | The code was entered wrong, or taken from a different server's console | Re-copy the code from THIS server's console/terminal exactly |
| Blocked after multiple wrong code entries | The attempt count is limited for security | Wait a bit and try again |
| "The password must be at least 8 characters" / "The login must be at least 3 characters" etc. | A field doesn't meet the requirement | Enter a value matching the shown requirement |
| Error in the CIDR field | A line isn't in the right format (e.g. not like `10.0.0.0/8`) | Write each line in the correct CIDR format |
| The page won't reopen | The admin account was already created — setup is one-time | Sign in via the normal [Login](/docs/kirish) page |

## Related sections

- [Installation](/docs/ornatish)
- [Quick start](/docs/tez-boshlash)
- [Dashboard](/docs/dashboard)
