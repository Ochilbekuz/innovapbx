// M5b — fake API uchun Follow Me validatsiyasi: backend `services/follow_me.py` (`normalize_numbers`,
// `_classify`, `validate_follow_me`) bilan bir xil kodlar va `field` (`numbers.{i}`).
import { cleanNumber, isExternalNumber } from '@/domain/followMe';
import { ApiError } from './errors';
import { FOLLOW_ME_MAX_NUMBERS, FOLLOW_ME_RING_MAX, FOLLOW_ME_RING_MIN, type FollowMe } from './types';

const NUMBER_RE = /^[0-9]{2,15}$/;

export type FollowMeContext = {
  own: string;
  extensionNumbers: ReadonlySet<string>;
  /** `outbound_allowed` va toll-blok yo'q. */
  outboundAllowed: boolean;
};

function bad(code: string, message: string, field = 'numbers'): never {
  throw new ApiError(422, { code, message, field });
}

function checkNumber(number: string, index: number, ctx: FollowMeContext, seen: readonly string[]) {
  const field = `numbers.${index}`;
  if (!NUMBER_RE.test(number)) bad('bad_number', 'Raqam notoʻgʻri (2–15 raqam)', field);
  if (number === ctx.own) bad('follow_me_self', 'Oʻz raqamingizni qoʻshmang', field);
  if (seen.includes(number)) bad('follow_me_duplicate', 'Raqam takrorlangan', field);
  if (!isExternalNumber(number) && !ctx.extensionNumbers.has(number)) bad('follow_me_unknown_extension', 'Bunday ichki raqam yoʻq', field);
}

export function normalizeFollowMe(fm: FollowMe, ctx: FollowMeContext): FollowMe {
  if (fm.numbers.length > FOLLOW_ME_MAX_NUMBERS) bad('bad_value', `Koʻpi bilan ${FOLLOW_ME_MAX_NUMBERS} ta raqam`);
  if (fm.ring_seconds < FOLLOW_ME_RING_MIN || fm.ring_seconds > FOLLOW_ME_RING_MAX) bad('bad_value', 'Vaqt chegaradan tashqarida', 'ring_seconds');
  const numbers: string[] = [];
  fm.numbers.forEach((raw, index) => {
    const number = cleanNumber(raw);
    checkNumber(number, index, ctx, numbers);
    numbers.push(number);
  });
  if (fm.enabled && numbers.length === 0) bad('follow_me_empty', 'Yoqish uchun kamida bitta raqam kerak');
  // Backend kabi: o'chirilgan Follow Me'ni saqlash toll-blok paytida ham mumkin.
  if (fm.enabled && numbers.some(isExternalNumber) && !ctx.outboundAllowed) {
    bad('follow_me_outbound_forbidden', 'Bu ichki raqamga tashqi qoʻngʻiroq ruxsat etilmagan');
  }
  return { ...fm, numbers };
}
