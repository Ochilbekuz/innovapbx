---
id: tez-boshlash
title: Quick start
group: start
order: 40
summary: A short path from first setup to creating an extension, connecting a trunk, and configuring call routing.
---

# Quick start

After [First setup](/docs/birinchi-sozlash), follow this order to make your first call through
Innova PBX: create an extension, connect a phone, add a carrier trunk, and configure call
routing.

## How to

### 1. Create your first extension
Go to **Users → Extensions**. Click **New extension**, enter a **Number** and **Name** (leave
the number blank to auto-pick one). Click **Create** and copy the SIP login/password/domain/port
shown — it's never shown again.

Details: [Extensions](/docs/extensions).

### 2. Connect a phone

- **If you have a desk phone**: add the device in the Phone devices section and attach it
  to the extension from step 1 (or wait for auto-detection via the provisioning URL/DHCP and
  confirm it in the Phone devices list). Details: [Phone devices](/docs/devices).
- **If you don't have a device**: click the QR icon on that extension's row in
  [Extensions](/docs/extensions), scan it with the mobile Linphone app within 15 minutes — or use
  the browser softphone via [My portal](/docs/portal) (requires HTTPS).

### 3. Add a carrier trunk
Go to **Connectivity → Trunks**, click **New trunk**; enter the host/port and auth info (by IP
or Registration) from your carrier, and set the codecs. After adding it, click **Test** to
verify connectivity.

Details: [Trunks](/docs/trunks).

### 4. Configure outbound calling
On **Connectivity → Outbound routes**, create a **New route**; enter a dial pattern in **Pattern
rule**, e.g. `998XXXXXXXXX`, and choose the trunk from step 3 in **Trunk chain**. Use the page's
**Simulator** with an extension and a test number to verify the route works.

Details: [Outbound routes](/docs/outbound).

### 5. Configure inbound calling
On **Connectivity → Inbound routes**, create a **New route**; enter the DID number from your
carrier (or leave "Any DID" enabled). In the **Destination** field choose where inbound calls go
(e.g. the extension from step 1), then click **Add**.

Details: [Inbound routes](/docs/inbound).

### 6. Verify the result
Open [Dashboard](/docs/dashboard) or [Live monitor](/docs/live); make a test call and check that
it shows up live and later in the daily dashboard stats.

## Tips and limits

> [!TIP]
> Have at least one extension ready before configuring trunks/routes, so the Simulator and
> Destination fields can select it immediately for testing.

> [!WARNING]
> Enabling browser softphone (WebRTC) on an extension removes the ability to attach a
> physical device or connect it via QR — decide which method you want beforehand.

> [!TIP]
> Always verify newly configured trunks/routes with the Test/Simulator tools before making
> a real call — the reason for any error is shown step by step there.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Phone won't register | SIP login/password/domain is wrong, or the device can't reach the server over the network | Recheck the data in [Extensions](/docs/extensions), check network/firewall settings |
| Outbound call doesn't go through | Pattern mismatch, trunk down, or no permission | Use the Simulator in [Outbound routes](/docs/outbound) to find the reason |
| Inbound call isn't arriving | Wrong DID, or trunk registration isn't working | Check trunk health in [Trunks](/docs/trunks), check the DID in [Inbound routes](/docs/inbound) |
| Nothing shows on the dashboard | No call has been made yet | Make a test call and check again |

## Related sections

- [First setup](/docs/birinchi-sozlash)
- [Extensions](/docs/extensions)
- [Trunks](/docs/trunks)
- [Outbound routes](/docs/outbound)
- [Inbound routes](/docs/inbound)
- [Dashboard](/docs/dashboard)
