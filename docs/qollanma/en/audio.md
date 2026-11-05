---
id: audio
title: Audio library
group: apps
order: 10
path: /audio
summary: Audio files for IVR greetings, queue announcements, and music on hold; record or generate from text (TTS).
---

# Audio library

This is the central hub for every audio file used in the system: IVR greetings, announcement
texts, and music-on-hold files. Upload a file, record one with your microphone, or generate one
automatically from text (TTS) — then select it elsewhere (IVR, Announcements, Queues).

## Where

Menu: **Applications → Audio library**. Who can see it: the `apps` permission can edit, others
can only view.

## Key concepts

- **File** — any uploaded audio is automatically converted to WAV 8kHz mono (an Asterisk
  requirement); the original can be WAV/MP3/OGG/WEBM.
- **Music-on-hold (MOH) class** — a collection of files, selected on [Queues](/docs/queues).
  The list always has exactly one **"Default"** class — it's used anywhere no class is explicitly
  chosen (queue, parking, plain channel hold). The default class can't be deleted, but any class can
  be made the default with the **Set as default** button (its name doesn't have to be "default").
- **Shuffle** — if on, the class's files play in random order; if off, in sequence.
- **TTS (text-to-speech)** — enter text and the system converts it to voice and saves it
  to the library; requires a speech synthesis provider (Yandex) configured on the
  [Integrations](/docs/integrations) page.

## Fields

### File upload

| Field | What it does | Example / default |
|---|---|---|
| File | WAV, MP3, or OGG, up to 20MB | — |

### Mic recording

| Field | What it does | Example / default |
|---|---|---|
| Recording name | Optional | Blank = "Recording" |
| Duration | — | Up to 5 minutes |

### MOH class

| Field | What it does | Example / default |
|---|---|---|
| Name | Lowercase letters/digits/`_`/`-` only | 1–32 characters |
| Shuffle files | — | Default: off (sequential) |
| Files | Chosen from existing library files | — |

### Text-to-speech (TTS)

| Field | What it does | Example / default |
|---|---|---|
| Audio name | Optional | Blank = taken from the text |
| Text | — | Up to 2000 characters |

## How to

### Upload a file
1. Drag a file into the drop area, or click **Choose file**.
2. A WAV/MP3/OGG file up to 20MB uploads automatically and is converted to WAV 8kHz mono.

### Record with your microphone
1. Click **Start recording** under "Or record with your microphone" — the browser asks
   for microphone permission.
2. Click **Stop**, enter a name, and click **Save**.

### Generate audio from text (TTS)
1. First configure a speech synthesis provider on [Integrations](/docs/integrations) —
   visible to admins only; the card warns if it's not configured.
2. Click **Start** on the "Create audio from text" card and enter the text (up to 2000
   characters).
3. Click **Preview** to listen to the result; if you're satisfied, enter a name and click
   **Save**.

### Create a music-on-hold class
1. On the **Music on hold** tab, click **New class**, give it a name (lowercase
   letters/digits/`_`/`-`), attach the files you need, and enable **Shuffle** if needed.
2. Click **Add** — select the new class in the **Music on hold** field on
   [Queues](/docs/queues).

### Set a class as default
1. On the **Music on hold** tab, click the star-icon **Set as default** button on the class you want.
2. The "Default" badge moves to that class; the previous default becomes a regular class (and can now be deleted).
3. Everywhere no class was explicitly chosen (queue, parking, channel hold) immediately starts using the new default class — no further setup needed.

### Delete a file
1. Click the trash icon at the end of the row.
2. If the file is used in an IVR, announcement, or MOH class, deletion is blocked —
   remove those links first.

> [!TIP]
> Short, precise greeting texts are very fast with TTS — you can prepare messages like
> "Attention, this call is recorded" in seconds, with no studio needed.

> [!WARNING]
> You can't delete the current default music-on-hold class — set another class as default first.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| File won't upload | Unsupported format or over 20MB | Upload a WAV/MP3/OGG/WEBM file up to 20MB |
| TTS button shows "not configured" | Speech synthesis isn't connected | Configure it on [Integrations](/docs/integrations) (admin only) |
| Microphone doesn't work | The browser denied permission, or no mic found | Allow microphone access in your browser settings and retry |
| Can't delete a file | It's used in an IVR, announcement, or MOH class | Remove those links first |
| Can't delete the default class | It's the current default class | Set another class as default, then delete the old one |

## Related sections

- [IVR](/docs/ivr)
- [Queues](/docs/queues)
- [Announcements](/docs/announcements)
- [Integrations](/docs/integrations)
