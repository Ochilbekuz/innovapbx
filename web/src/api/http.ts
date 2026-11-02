import { ApiError, type ApiErrorBody } from './errors';
import { getAccessToken, getRefreshToken, useSession } from './session';

const BASE = '/api/v1';

type Options = { method?: string; body?: unknown; auth?: boolean };

let refreshing: Promise<string | null> | null = null;

async function doRefresh(): Promise<string | null> {
  const token = getRefreshToken();
  if (!token) return null;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: token }),
  });
  if (!res.ok) {
    useSession.getState().clear();
    return null;
  }
  const data = (await res.json()) as { access: string; refresh: string };
  const user = useSession.getState().user;
  if (user) useSession.getState().setSession(data.access, data.refresh, user);
  return data.access;
}

/** 401 bo'lsa bitta marta `/auth/refresh` bilan tiklab qayta uradi; parallel so'rovlar bitta refresh'ni kutadi. */
async function refreshOnce(): Promise<string | null> {
  if (!refreshing) refreshing = doRefresh().finally(() => { refreshing = null; });
  return refreshing;
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const data = (await res.json()) as { error?: ApiErrorBody };
    if (data.error) return new ApiError(res.status, data.error);
  } catch {
    // javob JSON emas — pastda umumiy xato beriladi
  }
  return new ApiError(res.status, { code: 'unknown', message: 'Server xato qaytardi. Qayta urinib koʻring.' });
}

/** Bearer token qo'yadi; 401 bo'lsa bitta refresh bilan qayta uradi. Barcha avtorizatsiyali so'rovlar shu yerdan o'tadi. */
async function authFetch(path: string, init: RequestInit, auth = true): Promise<Response> {
  const withToken = (token: string | null): RequestInit =>
    auth && token ? { ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` } } : init;
  const res = await fetch(`${BASE}${path}`, withToken(getAccessToken()));
  if (res.status !== 401 || !auth) return res;
  const newAccess = await refreshOnce();
  return newAccess ? fetch(`${BASE}${path}`, withToken(newAccess)) : res;
}

export async function request<T>(path: string, { method = 'GET', body, auth = true }: Options = {}): Promise<T> {
  const init = { method, headers: { 'Content-Type': 'application/json' }, body: body !== undefined ? JSON.stringify(body) : undefined };
  const res = await authFetch(path, init, auth);
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Audio yuklash kabi multipart so'rovlar — Content-Type qo'yilmaydi (brauzer chegara bilan o'zi qo'yadi). */
export async function requestMultipart<T>(path: string, form: FormData): Promise<T> {
  const res = await authFetch(path, { method: 'POST', body: form });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

/** Ikkilik fayl (audio). `<audio src>` Authorization yubora olmaydi — shu sabab fayl token bilan olinadi. */
export async function requestBlob(path: string): Promise<Blob> {
  const res = await authFetch(path, { method: 'GET' });
  if (!res.ok) throw await parseError(res);
  return res.blob();
}
