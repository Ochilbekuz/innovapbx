// «Ping» tabi — soxta (demo) natija, deterministik: 192.0.2.x (TEST-NET-1) yoki
// "unreachable" bor host — 100% yo'qotish; `.invalid` — noma'lum nom; qolgani — javob bor.
import type { PingResult } from './types';

function unknownHost(host: string): PingResult {
  return {
    host, ok: false, transmitted: 0, received: 0, loss_pct: 100,
    rtt_min_ms: null, rtt_avg_ms: null, rtt_max_ms: null,
    output: `ping: ${host}: Name or service not known\n`,
  };
}

function header(host: string): string {
  return `PING ${host} (${host}) 56(84) bytes of data.\n`;
}

function unreachable(host: string, count: number): PingResult {
  return {
    host, ok: false, transmitted: count, received: 0, loss_pct: 100,
    rtt_min_ms: null, rtt_avg_ms: null, rtt_max_ms: null,
    output: `${header(host)}\n--- ${host} ping statistics ---\n${count} packets transmitted, 0 received, 100% packet loss, time ${count * 1000}ms\n`,
  };
}

function reachable(host: string, count: number): PingResult {
  const base = 1 + (host.length % 9);
  const times = Array.from({ length: count }, (_, i) => base + ((i * 3) % 5) / 10);
  const lines = times.map((t, i) => `64 bytes from ${host}: icmp_seq=${i + 1} ttl=57 time=${t.toFixed(1)} ms\n`).join('');
  const min = Math.min(...times);
  const max = Math.max(...times);
  const avg = Math.round((times.reduce((a, b) => a + b, 0) / count) * 1000) / 1000;
  return {
    host, ok: true, transmitted: count, received: count, loss_pct: 0,
    rtt_min_ms: min, rtt_avg_ms: avg, rtt_max_ms: max,
    output: `${header(host)}${lines}\n--- ${host} ping statistics ---\n${count} packets transmitted, ${count} received, 0% packet loss, time ${(count - 1) * 1000}ms\nrtt min/avg/max/mdev = ${min.toFixed(3)}/${avg.toFixed(3)}/${max.toFixed(3)}/0.100 ms\n`,
  };
}

export function fakePingResult(host: string, count: number): PingResult {
  if (host.endsWith('.invalid')) return unknownHost(host);
  if (host.startsWith('192.0.2.') || host.includes('unreachable')) return unreachable(host, count);
  return reachable(host, count);
}
