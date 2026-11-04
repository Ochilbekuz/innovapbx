---
id: kirish
title: Introduction
group: start
order: 10
summary: What Innova PBX is, what it consists of, and how this guide is organized — a general introduction.
---

# Introduction

Innova PBX is an IP-PBX (telephone exchange) built on Asterisk 22 with its own web panel: it lets you manage staff extensions, external trunk lines, inbound/outbound call routes, queues, conference rooms, and other communication tools from a single browser window. This guide explains every section of the panel step by step.

## Core concepts

- **Technical base** — Asterisk 22 (the "heart" that connects calls), FastAPI + PostgreSQL 16 (the server managing settings and data), React (the web panel itself). Everything runs on a single server via Docker Compose.
- **Web panel** — the browser-based control center; you move between sections through the left menu, and the **?** icon in each page header opens the guide for that exact section.
- **Roles** — every user is assigned a role, and the role defines which sections they can view/change (details: [Roles and permissions](/docs/rollar)).
- **Section groups** — the panel menu is grouped logically: **Overview** (dashboard, live status), **Users** (extensions, devices, personal portal), **Connectivity** (trunks, inbound/outbound routes, PIN sets, CID sources), **Routing** (business hours, IVR, queues, etc.), **Applications** (audio, conferences, parking, etc.), **Reports** (call history and analytics), **System** (settings, security, backups — admin only).

## How to

### Using the guide
1. Open the **Guide** section in the left menu, or click the **?** icon next to the heading on any page — it opens the section relevant to that exact page.
2. Every section follows the same structure: why it is needed, a field table, step-by-step instructions, tips/warnings, and a common-issues table.

### Getting started for the first time
1. If the system is not yet installed, start with [Installation](/docs/ornatish).
2. After installation, go through the setup page that appears on first launch via the [First-time setup](/docs/birinchi-sozlash) section.
3. Then follow the steps in [Quick start](/docs/tez-boshlash) to set up your first extension and call route.

## Tips and limitations

> [!TIP]
> The guide's **start** group (this section, installation, first-time setup, quick start, roles) is meant to be read in order by newcomers.

> [!NOTE]
> The panel version (currently 1.0.15) is shown in the settings section; updating is described in [Installation](/docs/ornatish).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| An expected section is missing from the menu | The user's role does not have permission for that section | Check [Roles and permissions](/docs/rollar), ask your administrator |
| I don't know where to start | The system was just installed | Follow this order: [Installation](/docs/ornatish) → [First-time setup](/docs/birinchi-sozlash) → [Quick start](/docs/tez-boshlash) |

## Related sections

- [Installation](/docs/ornatish)
- [First-time setup](/docs/birinchi-sozlash)
- [Quick start](/docs/tez-boshlash)
- [Roles and permissions](/docs/rollar)
