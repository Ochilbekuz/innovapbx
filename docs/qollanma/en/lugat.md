---
id: lugat
title: Glossary
group: appendix
order: 30
summary: Explanation of terms and abbreviations used in the guide and the panel.
---

# Glossary

A brief, alphabetically ordered explanation of the terms and abbreviations you'll encounter throughout the guide.

| Term | Explanation |
|---|---|
| **2FA** | Two-factor authentication — an extra step beyond login/password that requires a one-time code from a TOTP app (Google Authenticator, etc.). |
| **API key** | A scope-limited key issued so external applications can access the public API at `/api/public/v1/*`. |
| **Audit log** | A complete record of who did what in the system (created/changed/deleted/logged in). |
| **BLF** (Busy Lamp Field) | The light on a phone button showing whether another extension/destination is busy or free. |
| **CDR** (Call Detail Record) | A record of each call: who, to whom, when, how long it lasted, and how it ended. |
| **CID** (Caller ID) | The visible number/name of the calling party. |
| **CIDR** | A network address notation, e.g. `192.168.1.0/24` — denoting a single IP or an entire network. |
| **Diff** | The "what will change" list shown before applying changes on pages such as Network/Firewall. |
| **DISA** | The ability to call the office number from outside, enter a PIN, and place an outbound call through the office trunk. |
| **DND** (Do Not Disturb) | A mode that blocks calls from reaching an extension while enabled. |
| **Draft** | On Network/Firewall pages, a temporary state in which on-screen changes are saved locally before being sent to the server. |
| **Follow Me** | Forwarding calls to an extension through a sequence of other numbers (e.g. a mobile phone) as well. |
| **IVR** | A voice menu — lets callers choose an option by pressing a key. |
| **Conference** | A PIN-protected call room where several participants can talk at the same time. |
| **Queue** | A mechanism that distributes calls among multiple agents, playing hold music for callers when everyone is busy. |
| **NAT** | A device on a local network appearing with a different (public) IP on the internet — requires special attention in SIP/RTP settings. |
| **Paging / Intercom** | Dialing one number to broadcast a voice announcement to multiple extensions at once. |
| **Park** | Temporarily placing a call "on hold" so it can be picked up from another phone. |
| **Pickup** | Answering another ringing extension's/group's call from your own phone using a code. |
| **PIN set** | A list of PINs attached to an outbound route that are requested before the call is placed. |
| **Blacklist** | A list used to automatically reject inbound calls based on the caller's number. |
| **Ring group** | Routing that rings several extensions at once (no particular order) when a call comes in. |
| **Revision** | A "version history" entry created every time a setting is saved, allowing you to roll back to a previous state. |
| **RTP** (Real-time Transport Protocol) | The protocol used to transmit voice packets during a call (separate from SIP signaling). |
| **SIP** (Session Initiation Protocol) | The main protocol used to start/control phone calls. |
| **SLA** | A service-level metric, e.g. "percentage of calls answered within a set number of seconds". |
| **Toll fraud** | The risk of unauthorized, high-volume/expensive outbound calls being placed from an extension (attack/abuse); prevented with hourly/daily limits. |
| **TOTP** | A time-based one-time code — the basis on which 2FA apps generate codes. |
| **Trunk** | The SIP connection between the PBX and a telephone carrier (or another PBX) through which external calls pass. |
| **Webhook** | An HTTP message automatically sent to your external server when an event occurs in the system (e.g. a call ended). |
| **Feature code** | An action triggered by dialing a `*`-code from a phone (voicemail, DND, Follow Me, etc.). |

## Related sections

- [Feature codes (full list)](/docs/xususiyat-kodlari)
- [Troubleshooting](/docs/muammolar)
