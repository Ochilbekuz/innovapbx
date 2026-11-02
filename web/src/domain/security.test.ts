import { describe, expect, it } from 'vitest';
import { ipInCidr, isTrustedIp } from './security';

describe('security — ipInCidr', () => {
  it('/32 — faqat aynan shu IP', () => {
    expect(ipInCidr('10.0.0.5', '10.0.0.5/32')).toBe(true);
    expect(ipInCidr('10.0.0.6', '10.0.0.5/32')).toBe(false);
  });

  it('/24 — bir xil pastki tarmoq', () => {
    expect(ipInCidr('192.168.1.200', '192.168.1.0/24')).toBe(true);
    expect(ipInCidr('192.168.2.1', '192.168.1.0/24')).toBe(false);
  });

  it('/8 — keng tarmoq', () => {
    expect(ipInCidr('10.200.3.4', '10.0.0.0/8')).toBe(true);
    expect(ipInCidr('11.0.0.1', '10.0.0.0/8')).toBe(false);
  });

  it('/0 — hammasi', () => {
    expect(ipInCidr('203.0.113.9', '0.0.0.0/0')).toBe(true);
  });

  it('notoʻgʻri CIDR — false', () => {
    expect(ipInCidr('10.0.0.1', 'not-a-cidr')).toBe(false);
  });
});

describe('security — isTrustedIp', () => {
  it('127.0.0.0/8 — roʻyxatda boʻlmasa ham ishonchli', () => {
    expect(isTrustedIp('127.0.0.1', [])).toBe(true);
  });

  it('trustedNets ichidagi tarmoq — ishonchli', () => {
    expect(isTrustedIp('10.0.0.9', ['10.0.0.0/8'])).toBe(true);
  });

  it('boshqa IP — ishonchsiz', () => {
    expect(isTrustedIp('203.0.113.9', ['10.0.0.0/8'])).toBe(false);
  });
});
