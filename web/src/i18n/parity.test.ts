import { describe, expect, it } from 'vitest';
import * as shell from './shell';
import * as common from './common';
import * as errors from './errors';
import * as auth from './auth';
import * as calls from './calls';
import * as revisions from './revisions';
import * as setup from './setup';
import * as audit from './audit';
import * as dashboard from './dashboard';
import * as sip from './sip';
import * as extensions from './extensions';
import * as ringgroups from './ringgroups';
import * as trunks from './trunks';
import * as routes from './routes';
import * as audio from './audio';
import * as ivr from './ivr';
import * as outbound from './outbound';
import * as queues from './queues';
import * as timegroups from './timegroups';
import * as voicemail from './voicemail';
import * as notify from './notify';
import * as featurecodes from './featurecodes';
import * as conferences from './conferences';
import * as blacklist from './blacklist';
import * as users from './users';
import * as me from './me';
import * as live from './live';
import * as analytics from './analytics';
import * as security from './security';
import * as alerts from './alerts';
import * as integrations from './integrations';
import * as recordings from './recordings';
import * as devices from './devices';
import * as backup from './backup';
import * as migration from './migration';
import * as followme from './followme';
import * as campaigns from './campaigns';
import * as status from './status';
import * as network from './network';

type AnyObj = Record<string, unknown>;

/** Obyektni "a.b.c" ko'rinishidagi yo'llar ro'yxatiga yoyadi — chuqurlikdan qat'i nazar, barglarni topadi. */
function leafPaths(obj: AnyObj, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) return leafPaths(value as AnyObj, path);
    return [path];
  });
}

const NAMESPACES: Record<string, { uz: AnyObj; ru: AnyObj; en: AnyObj }> = {
  shell, common, errors, auth, calls, revisions, setup, audit, dashboard, sip,
  extensions, ringgroups, trunks, routes, audio, ivr, outbound, queues, timegroups,
  voicemail, notify, featurecodes, conferences, blacklist,
  users, me, live, analytics, security, alerts, integrations, recordings, devices, backup, migration, followme, campaigns,
  status, network,
};

describe('i18n namespace key parity', () => {
  for (const [ns, mod] of Object.entries(NAMESPACES)) {
    it(`${ns}: uz/ru/en have exactly the same keys`, () => {
      const uzKeys = leafPaths(mod.uz).sort();
      const ruKeys = leafPaths(mod.ru).sort();
      const enKeys = leafPaths(mod.en).sort();
      expect(ruKeys).toEqual(uzKeys);
      expect(enKeys).toEqual(uzKeys);
    });

    it(`${ns}: every value is a string (interpolation-ready)`, () => {
      for (const lang of ['uz', 'ru', 'en'] as const) {
        for (const path of leafPaths(mod[lang])) {
          const value = path.split('.').reduce<unknown>((o, k) => (o as AnyObj)[k], mod[lang]);
          expect(typeof value, `${ns}.${lang}.${path}`).toBe('string');
        }
      }
    });
  }

  it('ringgroups memoryhunt label matches the m1c-contract requirement exactly', () => {
    expect(ringgroups.uz.strategy.memoryhunt).toBe('Yigʻilib boruvchi (1, 1+2, 1+2+3…)');
    expect(ringgroups.ru.strategy.memoryhunt).toBe('Нарастающий (1, 1+2, 1+2+3…)');
    expect(ringgroups.en.strategy.memoryhunt).toBe('Cumulative (1, 1+2, 1+2+3…)');
  });
});
