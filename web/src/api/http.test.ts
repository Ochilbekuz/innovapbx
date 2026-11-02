import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { request, requestBlob, requestMultipart } from './http';
import { useSession } from './session';
import type { User } from './types';

const USER: User = { id: 'u-1', login: 'admin', full_name: 'Admin', role: 'admin', permissions: ['pbx.manage'], language: 'uz' };

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('http.request — 401 bo\'lsa avtomatik refresh', () => {
  beforeEach(() => {
    useSession.getState().setSession('eski-access', 'eski-refresh', USER);
  });

  afterEach(() => {
    useSession.getState().clear();
    vi.unstubAllGlobals();
  });

  it('eskirgan access bilan 401 kelsa — refresh qilib, yangi token bilan qayta so\'raydi', async () => {
    const calls: Array<{ url: string; auth: string | null }> = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const auth = (init?.headers as Record<string, string> | undefined)?.Authorization ?? null;
      calls.push({ url, auth });
      if (url.endsWith('/auth/refresh')) {
        return jsonResponse(200, { access: 'yangi-access', refresh: 'yangi-refresh' });
      }
      if (auth === 'Bearer eski-access') {
        return jsonResponse(401, { error: { code: 'unauthorized', message: "Sessiya tugagan" } });
      }
      return jsonResponse(200, { ok: true });
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await request<{ ok: boolean }>('/extensions');

    expect(result).toEqual({ ok: true });
    expect(calls.map((c) => c.url)).toEqual(['/api/v1/extensions', '/api/v1/auth/refresh', '/api/v1/extensions']);
    expect(calls[2]?.auth).toBe('Bearer yangi-access');
    expect(useSession.getState().access).toBe('yangi-access');
    expect(useSession.getState().refresh).toBe('yangi-refresh');
  });

  it("refresh ham 401 bersa — seans tozalanadi va asl 401 xato sifatida chiqadi", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith('/auth/refresh')) return jsonResponse(401, { error: { code: 'bad_refresh', message: 'Yaroqsiz' } });
      return jsonResponse(401, { error: { code: 'unauthorized', message: 'Sessiya tugagan' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(request('/extensions')).rejects.toMatchObject({ status: 401 });
    expect(useSession.getState().access).toBeNull();
    expect(useSession.getState().user).toBeNull();
  });
});

describe('http.requestBlob — audio fayl token bilan olinadi', () => {
  beforeEach(() => useSession.getState().setSession('access-1', 'refresh-1', USER));
  afterEach(() => {
    useSession.getState().clear();
    vi.unstubAllGlobals();
  });

  it('Bearer token yuboradi va baytlarni Blob qilib qaytaradi', async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
      return auth === 'Bearer access-1' ? new Response(new Uint8Array([82, 73, 70, 70]), { status: 200 }) : jsonResponse(401, {});
    });
    vi.stubGlobal('fetch', fetchMock);

    const blob = await requestBlob('/audio/a-1/stream');

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/audio/a-1/stream');
    expect(new Uint8Array(await blob.arrayBuffer())).toEqual(new Uint8Array([82, 73, 70, 70]));
  });

  it('server xatosini ApiError sifatida chiqaradi', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(404, { error: { code: 'not_found', message: 'Audio fayli diskda topilmadi' } })));
    await expect(requestBlob('/audio/x/stream')).rejects.toMatchObject({ status: 404 });
  });
});

describe('http.requestMultipart', () => {
  beforeEach(() => useSession.getState().setSession('access-1', 'refresh-1', USER));
  afterEach(() => {
    useSession.getState().clear();
    vi.unstubAllGlobals();
  });

  it('FormData\'ni POST qiladi, Content-Type qoʻymaydi, token yuboradi', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { item: { id: 'au-1' } }));
    vi.stubGlobal('fetch', fetchMock);
    const form = new FormData();
    const out = await requestMultipart<{ item: { id: string } }>('/audio', form);
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(out.item.id).toBe('au-1');
    expect(init.method).toBe('POST');
    expect(init.body).toBe(form);
    expect(init.headers).toEqual({ Authorization: 'Bearer access-1' });
  });

  it('xato javobni ApiError qiladi', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(413, { error: { code: 'too_large', message: 'katta' } })));
    await expect(requestMultipart('/audio', new FormData())).rejects.toMatchObject({ status: 413 });
  });
});
