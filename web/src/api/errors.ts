// Shartnoma: {"error": {"code","message","field"?,"details"?}} — hamma joyda bir xil.
// Xato ko'rsatish markazi: kod `errors` namespace'da tarjima qilingan bo'lsa — u, bo'lmasa server `message`.

import i18n from '@/lib/i18n';

export type ApiErrorBody = { code: string; message: string; field?: string; details?: Record<string, unknown> };

export class ApiError extends Error {
  code: string;
  field?: string;
  details?: Record<string, unknown>;
  status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.field = body.field;
    this.details = body.details;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

/** Xato kodi `errors` namespace'da tarjima qilingan bo'lsa — uni ko'rsatadi, bo'lmasa serverning o'z xabarini. */
export function apiErrorMessage(e: unknown, fallback?: string): string {
  if (!isApiError(e)) return fallback ?? i18n.t('errors:unexpected');
  return i18n.exists(`errors:${e.code}`) ? i18n.t(`errors:${e.code}`) : e.message;
}
