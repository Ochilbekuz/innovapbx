import i18n, { type Resource } from 'i18next';
import { initReactI18next } from 'react-i18next';

import * as shell from '@/i18n/shell';
import * as common from '@/i18n/common';
import * as errors from '@/i18n/errors';
import * as auth from '@/i18n/auth';
import * as calls from '@/i18n/calls';
import * as revisions from '@/i18n/revisions';
import * as setup from '@/i18n/setup';
import * as audit from '@/i18n/audit';
import * as dashboard from '@/i18n/dashboard';
import * as sip from '@/i18n/sip';
import * as extensions from '@/i18n/extensions';
import * as ringgroups from '@/i18n/ringgroups';
import * as trunks from '@/i18n/trunks';
import * as routes from '@/i18n/routes';
import * as audio from '@/i18n/audio';
import * as ivr from '@/i18n/ivr';
import * as outbound from '@/i18n/outbound';
import * as queues from '@/i18n/queues';
import * as timegroups from '@/i18n/timegroups';
import * as voicemail from '@/i18n/voicemail';
import * as notify from '@/i18n/notify';
import * as featurecodes from '@/i18n/featurecodes';
import * as conferences from '@/i18n/conferences';
import * as blacklist from '@/i18n/blacklist';
import * as users from '@/i18n/users';
import * as me from '@/i18n/me';
import * as live from '@/i18n/live';
import * as analytics from '@/i18n/analytics';
import * as security from '@/i18n/security';
import * as alerts from '@/i18n/alerts';
import * as integrations from '@/i18n/integrations';
import * as recordings from '@/i18n/recordings';
import * as devices from '@/i18n/devices';
import * as backup from '@/i18n/backup';
import * as migration from '@/i18n/migration';
import * as followme from '@/i18n/followme';
import * as campaigns from '@/i18n/campaigns';
import * as status from '@/i18n/status';
import * as network from '@/i18n/network';
import * as announcements from '@/i18n/announcements';
import * as misc from '@/i18n/misc';
import * as parking from '@/i18n/parking';
import * as paging from '@/i18n/paging';
import * as phonebook from '@/i18n/phonebook';
import * as pinsets from '@/i18n/pinsets';
import * as cidsources from '@/i18n/cidsources';
import * as quality from '@/i18n/quality';
import * as callback from '@/i18n/callback';
import * as missedcalls from '@/i18n/missedcalls';
import * as update from '@/i18n/update';
import * as daynight from '@/i18n/daynight';
import * as disa from '@/i18n/disa';
import * as time from '@/i18n/time';
import * as firewall from '@/i18n/firewall';
import * as access from '@/i18n/access';
import * as license from '@/i18n/license';
import * as docs from '@/i18n/docs';
import { apiClient } from '@/api';

export const LANGS = ['uz', 'ru', 'en'] as const;
export type Lang = (typeof LANGS)[number];

const NAMESPACES = {
  shell, common, errors, auth, calls, revisions, setup, audit, dashboard, sip,
  extensions, ringgroups, trunks, routes, audio, ivr, outbound, queues, timegroups,
  voicemail, notify, featurecodes, conferences, blacklist,
  users, me, live, analytics, security, alerts, integrations, recordings, devices, backup, migration, followme, campaigns,
  status, network,
  announcements, misc, parking, paging, phonebook, pinsets, cidsources, quality, callback, missedcalls,
  update,
  daynight, disa,
  time, firewall, access, license,
  docs,
} as const;

function resourcesFor(lang: Lang) {
  const out: Record<string, unknown> = {};
  for (const [ns, mod] of Object.entries(NAMESPACES)) out[ns] = mod[lang];
  return out;
}

const resources = { uz: resourcesFor('uz'), ru: resourcesFor('ru'), en: resourcesFor('en') } as unknown as Resource;

const STORAGE_KEY = 'pbx.language';

/** Brauzer localStorage'ida saqlangan til — kirishgacha ishlatiladi; kirgandan keyin `User.language` (PATCH /auth/me) ustun. */
export function storedLanguage(): Lang | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v !== null && (LANGS as readonly string[]).includes(v) ? (v as Lang) : null;
  } catch {
    return null;
  }
}

/** Tilni tanlaganda chaqiriladi — i18next'ni almashtiradi, localStorage'ga yozadi va serverga saqlaydi (jim xato). */
export function persistLanguage(lang: Lang): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // xususiy rejim / disk to'la — jim o'tkazib yuboramiz, foydalanuvchi tajribasiga ta'sir qilmaydi.
  }
  void i18n.changeLanguage(lang);
  // Server — darhol UI uchun localStorage ustun, lekin keyingi kirishlarda sinxron bo'lishi uchun saqlaymiz.
  // Xato (masalan tarmoq yo'q) UI'ga ta'sir qilmasligi kerak — localStorage baribir yetarli.
  void apiClient.updateMe({ language: lang }).catch(() => undefined);
}

/**
 * Login'dan keyin `GET /auth/me`'dagi `language` bilan sinxronlash — server qiymati haqiqat manbai
 * hisoblanadi (boshqa qurilmada tanlangan til ustun bo'ladi), shu sabab localStorage'ni har doim qayta yozadi.
 */
export function syncLanguageFromUser(language: string | null | undefined): void {
  if (language !== null && language !== undefined && (LANGS as readonly string[]).includes(language)) {
    void i18n.changeLanguage(language as Lang);
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // xususiy rejim / disk to'la — jim o'tkazib yuboramiz.
    }
  }
}

void i18n.use(initReactI18next).init({
  resources,
  lng: storedLanguage() ?? 'uz',
  fallbackLng: 'uz',
  defaultNS: 'shell',
  interpolation: { escapeValue: false },
});

export default i18n;
