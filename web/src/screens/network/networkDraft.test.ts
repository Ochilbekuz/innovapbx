import { describe, expect, it } from 'vitest';
import type { NetworkConfigIn, NetworkInterface, NetworkStateOut } from '@/api/types';
import { displayMode, draftToConfig, normalizeServerErrors, stateToDraft } from './networkDraft';

function iface(partial: Partial<NetworkInterface>): NetworkInterface {
  return {
    name: 'ens18', mac: null, kind: 'ethernet', oper_state: 'up', carrier: true, speed_mbps: null,
    mtu: 1500, live_ipv4: [], live_ipv6: [], editable: true,
    config: { mode: 'static', address: '10.0.0.1/24', gateway: null, mtu: null },
    ...partial,
  };
}

function state(interfaces: NetworkInterface[]): NetworkStateOut {
  return {
    helper: { available: true, version: '1', error: null },
    backend: 'ifupdown', editable: true, readonly_reason: null, hostname: 'h',
    dns: { servers: [], search: [], editable: true },
    default_gateway: { address: null, interface: null },
    interfaces,
    routes: { static: [], live: [] },
    pending: null, last_result: null,
  };
}

describe('stateToDraft/draftToConfig — managed interfaces', () => {
  it('sozlangan (dhcp/static) va tahrirlanadigan interfeysni konfiguratsiyaga kiritadi', () => {
    const draft = stateToDraft(state([iface({ name: 'ens18', config: { mode: 'static', address: '10.0.0.1/24', gateway: null, mtu: null } })]));
    expect(draft.interfaces[0]?.managed).toBe(true);
    expect(draftToConfig(draft, 180).interfaces.map((i) => i.name)).toEqual(['ens18']);
  });

  it('sozlanmagan (unconfigured) interfeysni netd\'ga yubormaydi — bond a\'zosi kabi "egasiz" interfeysga tegmaslik uchun', () => {
    const draft = stateToDraft(state([iface({ name: 'eth1', editable: true, config: { mode: 'unconfigured', address: null, gateway: null, mtu: null } })]));
    expect(draft.interfaces[0]?.managed).toBe(false);
    expect(draftToConfig(draft, 180).interfaces).toEqual([]);
  });

  it('tahrirlanmaydigan interfeysni (netplan/NM) konfiguratsiyaga kiritmaydi', () => {
    const draft = stateToDraft(state([iface({ name: 'docker0', editable: false, config: { mode: 'static', address: '172.17.0.1/16', gateway: null, mtu: null } })]));
    expect(draftToConfig(draft, 180).interfaces).toEqual([]);
  });

  it('modalda saqlangan interfeys managed=true bo\'lib qoladi (InterfacesTab save)', () => {
    const draft = stateToDraft(state([iface({ name: 'eth1', config: { mode: 'unconfigured', address: null, gateway: null, mtu: null } })]));
    const saved = { ...draft.interfaces[0]!, mode: 'static' as const, address: '10.0.0.2/24', managed: true };
    expect(draftToConfig({ ...draft, interfaces: [saved] }, 180).interfaces).toEqual([
      { name: 'eth1', mode: 'static', address: '10.0.0.2/24', gateway: null, mtu: null },
    ]);
  });
});

describe('normalizeServerErrors', () => {
  const config: NetworkConfigIn = {
    hostname: 'h', dns: { servers: [], search: [] },
    interfaces: [{ name: 'ens19', mode: 'static', address: '10.0.0.5/24', gateway: null, mtu: null }],
    routes: [{ destination: '0.0.0.0/0', gateway: '10.0.0.1', interface: null, metric: null }],
    timeout_s: 180,
  };

  it('interfaces[N].field ni yuborilgan interfeys nomiga moslaydi', () => {
    const out = normalizeServerErrors([{ field: 'interfaces[0].address', message: 'yaroqsiz' }], config);
    expect(out).toEqual([{ field: 'interfaces.ens19.address', message: 'yaroqsiz' }]);
  });

  it('routes[N].field ni indeksga moslaydi (UI route xato konvensiyasi)', () => {
    const out = normalizeServerErrors([{ field: 'routes[0].gateway', message: 'xato' }], config);
    expect(out).toEqual([{ field: 'routes.0.gateway', message: 'xato' }]);
  });

  it('indeks chegaradan tashqari bo\'lsa — xatoni o\'zgarishsiz qoldiradi', () => {
    const out = normalizeServerErrors([{ field: 'interfaces[9].address', message: 'x' }], config);
    expect(out).toEqual([{ field: 'interfaces[9].address', message: 'x' }]);
  });

  it('umumiy maydon (hostname, interfaces) o\'zgarishsiz qoladi', () => {
    const out = normalizeServerErrors([{ field: 'hostname', message: 'x' }, { field: 'interfaces', message: 'y' }], config);
    expect(out).toEqual([{ field: 'hostname', message: 'x' }, { field: 'interfaces', message: 'y' }]);
  });
});

describe('displayMode', () => {
  it('boshqariladigan interfeys uchun draft rejimini qaytaradi', () => {
    const d = stateToDraft(state([iface({ name: 'ens18', config: { mode: 'static', address: '10.0.0.1/24', gateway: null, mtu: null } })]));
    expect(displayMode(iface({ name: 'ens18' }), d.interfaces[0]!)).toBe('static');
  });

  it('tahrirlanmaydigan va sozlanmagan interfeys uchun null qaytaradi ("—" UI\'da)', () => {
    const f = iface({ name: 'docker0', editable: false, config: { mode: 'unconfigured', address: null, gateway: null, mtu: null } });
    const d = stateToDraft(state([f]));
    expect(displayMode(f, d.interfaces[0]!)).toBeNull();
  });

  it('tahrirlanmaydigan, lekin fayldan sozlangan interfeys uchun shu rejimni ko\'rsatadi', () => {
    const f = iface({ name: 'docker0', editable: false, config: { mode: 'static', address: '172.17.0.1/16', gateway: null, mtu: null } });
    const d = stateToDraft(state([f]));
    expect(displayMode(f, d.interfaces[0]!)).toBe('static');
  });
});
