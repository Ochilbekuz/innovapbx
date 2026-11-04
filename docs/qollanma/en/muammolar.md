---
id: muammolar
title: Troubleshooting
group: appendix
order: 20
summary: Causes and fixes for frequent cross-cutting problems — linked to from other sections.
---

# Troubleshooting

This page collects common cross-cutting problems. Each screen has its own "Troubleshooting"
table for issues specific to it — this page only covers issues referenced **from** other
sections and that span multiple areas.

## Lost 2FA device

If a user loses the phone/app used for 2FA, they can't enter the code and are locked out. Only a
full administrator (`*`) can help:

1. The admin goes to **System → Users**.
2. Clicks the shield icon on the row of the user with 2FA enabled, and confirms **Reset
   2FA**.
3. The user can now sign in without a code; on their next sign-in, the system asks them to
   re-link 2FA (with a new app/device).

Details: [Users](/docs/users), [Security](/docs/security).

## No audio, or one-way audio

A call connects but there's no audio at all, or only one side can hear — almost always because
RTP (voice) packets aren't reaching the other side correctly:

1. On the **SIP & network** page, check that **External IP** is set correctly (the
   server's real public IP) — especially if the server is behind the cloud/NAT.
2. On the **Firewall** page, check the SIP and RTP service modes — if they're in
   allowlist mode, the calling/receiving party's addresses must be on the list.
3. The **RTP port range** (shown on the SIP & network page) must also be open on the
   server's **external** firewall (at the carrier/router level, outside this panel).
4. After changing settings, remember to click **Restart** on the SIP & network page to
   reload Asterisk — otherwise the new setting doesn't take effect.

Details: [SIP & network](/docs/sip), [Firewall](/docs/firewall), [Network](/docs/network).

## Lost connection to the server (Network/Firewall)

If after applying a change on the Network or Firewall page you can no longer connect to the
server (SSH, web panel):

- Do nothing — on these two pages every change first stays **pending**, and if it isn't
  confirmed within the time limit, the system **automatically reverts** to the previous state.
- If you can still connect, use the **Roll back now** button to revert immediately.

Details: [Network](/docs/network), [Firewall](/docs/firewall).

## Error during restore from backup or migration

If a restore/migration process fails or hangs, check the log (if shown) on the **Backups** page
and restart the action by re-typing the confirmation word. Don't manually power off or reboot
the server during the process.

Details: [Backups](/docs/backup), [Migration](/docs/migration).

## Error updating from the panel

If an update fails, the reason (e.g. at the backup or install stage) is shown clearly on the
page. If it stopped at the backup stage, the code hasn't changed yet and the system works as
before. If the error occurs after the install stage, contact your administrator — a manual
restore from backup may be needed.

Details: [Update](/docs/update).

## Extension/trunk not connecting (SIP registration)

- For an extension: check the login/password, the extension's status (active/disabled),
  and the device settings (host/port/transport).
- For an external trunk: if "No connection" is shown, verify the host/port and diagnose
  with the **Test** button; if "Registration rejected" is shown, confirm the login/password
  with the carrier.

Details: [SIP & network](/docs/sip), [Trunks](/docs/trunks).

## I got blocked myself

SIP protection may treat wrong login attempts as an attack and auto-block the IP:

1. An admin unblocks your address from the **Blocked IPs** list on the **Security** page.
2. Then add your own address to **Trusted networks** to prevent re-blocking.

Details: [Security](/docs/security).

## Related sections

- [Users](/docs/users)
- [Security](/docs/security)
- [SIP & network](/docs/sip)
- [Firewall](/docs/firewall)
- [Network](/docs/network)
- [Backups](/docs/backup)
- [Update](/docs/update)
- [Glossary](/docs/lugat)
