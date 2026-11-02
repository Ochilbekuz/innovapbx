import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { ProvisioningSettings } from '@/api/types';
import {
  adminPasswordHint, extraFieldError, networksToText, provisioningPayload, textToNetworks, useProvisioningForm,
} from './provisioningForm';

const t = (key: string) => key;

const DATA: ProvisioningSettings = {
  url: 'https://pbx.example/provision', has_admin_password: false, allowed_networks: ['10.0.0.0/24', '192.168.1.0/24'],
  language: 'uz', timezone: 'Asia/Tashkent', ntp_server: 'pool.ntp.org', sip_transport: 'udp',
  sip_server_host: null, extra: { yealink: '', grandstream: '', fanvil: '' }, updated_at: '2026-01-01T00:00:00Z',
};

describe('networksToText / textToNetworks', () => {
  it('roʻyxatni qatorlarga va qaytarib aylantiradi, boʻsh qatorlarni tashlab yuboradi', () => {
    const text = networksToText(['10.0.0.0/24', '192.168.1.0/24']);
    expect(text).toBe('10.0.0.0/24\n192.168.1.0/24');
    expect(textToNetworks(`${text}\n\n  `)).toEqual(['10.0.0.0/24', '192.168.1.0/24']);
  });
});

describe('adminPasswordHint', () => {
  it('parol oʻrnatilgan boʻlsa — "set" xabari', () => { expect(adminPasswordHint(t, true)).toBe('settings.adminPasswordSet'); });
  it('parol oʻrnatilmagan boʻlsa — hint', () => { expect(adminPasswordHint(t, false)).toBe('settings.adminPasswordHint'); });
});

describe('extraFieldError', () => {
  it('errorField "extra" va stale emas boʻlsa — xabarni qaytaradi', () => {
    expect(extraFieldError('extra', false, 'xato')).toBe('xato');
  });
  it('stale boʻlsa — undefined', () => { expect(extraFieldError('extra', true, 'xato')).toBeUndefined(); });
  it('boshqa maydon boʻlsa — undefined', () => { expect(extraFieldError('timezone', false, 'xato')).toBeUndefined(); });
});

describe('provisioningPayload', () => {
  it('maydonlarni trim qiladi va boʻsh server hostni null qiladi', () => {
    const state = {
      language: 'uz' as const, timezone: '  Asia/Tashkent  ', ntpServer: '  pool.ntp.org  ', sipTransport: 'udp' as const,
      sipServerHost: '  ', allowedNetworks: '10.0.0.0/24', adminPassword: '', extra: { yealink: '', grandstream: '', fanvil: '' },
    };
    expect(provisioningPayload(state, DATA.updated_at)).toEqual({
      language: 'uz', timezone: 'Asia/Tashkent', ntp_server: 'pool.ntp.org', sip_transport: 'udp',
      sip_server_host: null, allowed_networks: ['10.0.0.0/24'], extra: { yealink: '', grandstream: '', fanvil: '' },
      updated_at: DATA.updated_at,
    });
  });

  it('adminPassword berilgan boʻlsa — payloadga qoʻshadi', () => {
    const state = {
      language: 'uz' as const, timezone: 't', ntpServer: 'n', sipTransport: 'udp' as const, sipServerHost: '',
      allowedNetworks: '', adminPassword: 'Sirli1!', extra: { yealink: '', grandstream: '', fanvil: '' },
    };
    expect(provisioningPayload(state, DATA.updated_at)).toMatchObject({ admin_password: 'Sirli1!' });
  });
});

describe('useProvisioningForm', () => {
  it('boshlang\'ich holat `data`dan olinadi, keyingi `data` yangilanishi formani qayta ishga tushirmaydi', () => {
    const { result, rerender } = renderHook(({ data }) => useProvisioningForm(data), { initialProps: { data: DATA } });
    expect(result.current.state.timezone).toBe('Asia/Tashkent');

    act(() => result.current.setTimezone('Europe/Moscow'));
    expect(result.current.state.timezone).toBe('Europe/Moscow');

    rerender({ data: { ...DATA, timezone: 'UTC', updated_at: '2026-02-01T00:00:00Z' } });
    expect(result.current.state.timezone).toBe('Europe/Moscow');
  });

  it('setExtraField — faqat koʻrsatilgan vendorni oʻzgartiradi', () => {
    const { result } = renderHook(() => useProvisioningForm(DATA));
    act(() => result.current.setExtraField('yealink', 'account.1.sip.server.host = %PROV_URL%'));
    expect(result.current.state.extra).toEqual({ yealink: 'account.1.sip.server.host = %PROV_URL%', grandstream: '', fanvil: '' });
  });

  it('clearAdminPassword — faqat parolni tozalaydi', () => {
    const { result } = renderHook(() => useProvisioningForm(DATA));
    act(() => result.current.setAdminPassword('Sirli1!'));
    act(() => result.current.setSipServerHost('sip.example.com'));
    act(() => result.current.clearAdminPassword());
    expect(result.current.state.adminPassword).toBe('');
    expect(result.current.state.sipServerHost).toBe('sip.example.com');
  });

  it('setLanguage / setNtpServer / setSipTransport / setAllowedNetworks — holatni yangilaydi', () => {
    const { result } = renderHook(() => useProvisioningForm(DATA));
    act(() => result.current.setLanguage('ru'));
    act(() => result.current.setNtpServer('time.google.com'));
    act(() => result.current.setSipTransport('tls'));
    act(() => result.current.setAllowedNetworks('10.0.0.0/8'));
    expect(result.current.state).toMatchObject({
      language: 'ru', ntpServer: 'time.google.com', sipTransport: 'tls', allowedNetworks: '10.0.0.0/8',
    });
  });
});
