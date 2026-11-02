// Chiquvchi marshrut moslashtirish (dialplan va simulyator UMUMIY qoida) — qarang
// ../../replica/m1b-contract.md §2. Sof funksiyalar — fake.ts va testlar shuni chaqiradi.

import { matchPattern } from './pattern';

export type SimPattern = { strip_prefix: string | null; pattern: string; add_prefix: string | null; callerid_match: string | null };
export type SimTrunkRef = { id: string; name: string; health_state: string };
export type SimRoute = {
  id: string;
  name: string;
  priority: number;
  enabled: boolean;
  patterns: SimPattern[];
  trunks: SimTrunkRef[];
  callerid: string | null;
  override_extension_callerid: boolean;
  international: boolean;
  extensions: 'all' | string[];
};

export type SimStepResult = 'match' | 'no_pattern' | 'ext_not_allowed' | 'international_blocked' | 'disabled';
export type SimStep = { route: string; result: SimStepResult; detail: string };
export type SimOutcome = {
  allowed: boolean;
  route: { id: string; name: string } | null;
  dialed: string | null;
  callerid: string | null;
  trunks: SimTrunkRef[];
  steps: SimStep[];
  reason: string | null;
};

export const STEP_TEXT: Record<SimStepResult, string> = {
  match: 'Mos keldi',
  no_pattern: 'Hech bir naqsh mos kelmadi',
  ext_not_allowed: 'Bu ichki raqam uchun ruxsat yoʻq',
  international_blocked: 'Xalqaro qoʻngʻiroqlarga ruxsat yoʻq (toll-fraud himoyasi)',
  disabled: 'Marshrut oʻchirilgan',
};

/** `00` yoki `+` bilan boshlanib, 998 (UZ) bilan boshlanmasa — xalqaro raqam hisoblanadi. */
export function isInternationalNumber(number: string): boolean {
  return /^(00|\+)/.test(number) && !/^(00|\+)?998/.test(number);
}

/** Bitta naqshni sinab ko'rish: strip_prefix kesiladi, qolgani pattern'ga, so'ng add_prefix qo'shiladi. */
function tryPattern(p: SimPattern, number: string): string | null {
  const strip = p.strip_prefix ?? '';
  if (!number.startsWith(strip)) return null;
  const rest = number.slice(strip.length);
  if (!matchPattern(p.pattern, rest)) return null;
  return (p.add_prefix ?? '') + rest;
}

function firstDialed(route: SimRoute, number: string): string | null {
  for (const p of route.patterns) {
    const dialed = tryPattern(p, number);
    if (dialed !== null) return dialed;
  }
  return null;
}

function resolveCallerid(route: SimRoute, extensionCallerid: string | null): string | null {
  if (route.override_extension_callerid) return route.callerid ?? null;
  return extensionCallerid ?? route.callerid ?? null;
}

type StepOutcome = { result: SimStepResult; detail: string; dialed?: string };

function evalRoute(route: SimRoute, extensionId: string, number: string): StepOutcome {
  if (!route.enabled) return { result: 'disabled', detail: STEP_TEXT.disabled };
  if (route.extensions !== 'all' && !route.extensions.includes(extensionId)) {
    return { result: 'ext_not_allowed', detail: STEP_TEXT.ext_not_allowed };
  }
  const dialed = firstDialed(route, number);
  if (dialed === null) return { result: 'no_pattern', detail: STEP_TEXT.no_pattern };
  if (!route.international && isInternationalNumber(number)) {
    return { result: 'international_blocked', detail: STEP_TEXT.international_blocked };
  }
  return { result: 'match', detail: `${STEP_TEXT.match} — teriladi: ${dialed}`, dialed };
}

/**
 * Marshrutlarni priority tartibida sinab, birinchi mos kelganini tanlaydi.
 * `extensionCallerid` — chaqiruvchi ichki raqamning oʻz CallerID'i (boʻlsa); fake rejimda taqribiy hisoblash,
 * haqiqiy serverda bu qoida backend tomonida toʻliq amalga oshiriladi.
 */
export function simulateOutbound(routes: SimRoute[], extensionId: string, number: string, extensionCallerid: string | null = null): SimOutcome {
  const ordered = [...routes].sort((a, b) => a.priority - b.priority);
  const steps: SimStep[] = [];
  for (const route of ordered) {
    const outcome = evalRoute(route, extensionId, number);
    steps.push({ route: route.name, result: outcome.result, detail: outcome.detail });
    if (outcome.result !== 'match' || outcome.dialed === undefined) continue;
    return {
      allowed: true,
      route: { id: route.id, name: route.name },
      dialed: outcome.dialed,
      callerid: resolveCallerid(route, extensionCallerid),
      trunks: route.trunks,
      steps,
      reason: null,
    };
  }
  return {
    allowed: false,
    route: null,
    dialed: null,
    callerid: null,
    trunks: [],
    steps,
    reason: steps.length ? 'Hech bir marshrut mos kelmadi' : 'Chiquvchi marshrut yoʻq',
  };
}

/** `OutboundRouteDrawer` formasi — sof tekshiruv, komponentdan ajratilgan (CRAP past bo'lishi uchun, testlanadi). */
export type OutboundFormDraft = {
  name: string;
  patternCount: number;
  everyPatternFilled: boolean;
  chainLength: number;
  pinOn: boolean;
  pin: string;
  hasExistingPin: boolean;
  extensionsMode: 'all' | 'selected';
  selectedExtensionCount: number;
};
export type OutboundFormValidation = { valid: boolean; pinError: string | null };

function pinFormatError(pinOn: boolean, pin: string): string | null {
  const trimmed = pin.trim();
  if (!pinOn || !trimmed) return null;
  return /^\d{4,8}$/.test(trimmed) ? null : 'PIN 4–8 raqamdan iborat boʻlsin.';
}

function pinMissing(pinOn: boolean, pin: string, hasExistingPin: boolean): boolean {
  return pinOn && !hasExistingPin && !pin.trim();
}

export function validateOutboundForm(f: OutboundFormDraft): OutboundFormValidation {
  const pinError = pinFormatError(f.pinOn, f.pin);
  const missingPin = pinMissing(f.pinOn, f.pin, f.hasExistingPin);
  const valid = f.name.trim().length > 0 && f.patternCount > 0 && f.everyPatternFilled && f.chainLength > 0
    && !pinError && !missingPin && (f.extensionsMode === 'all' || f.selectedExtensionCount > 0);
  return { valid, pinError };
}
