import { describe, expect, it } from 'vitest';
import { isInsecureLocation } from './secureContext';

describe('isInsecureLocation', () => {
  it('https: hech qachon insecure emas', () => {
    expect(isInsecureLocation({ protocol: 'https:', hostname: 'pbx.example.com' })).toBe(false);
  });

  it('http: + oddiy LAN host — insecure', () => {
    expect(isInsecureLocation({ protocol: 'http:', hostname: '192.168.1.10' })).toBe(true);
  });

  it.each(['localhost', '127.0.0.1', '::1'])('http: + %s — xavfsiz kontekst (brauzer qoidasi)', (hostname) => {
    expect(isInsecureLocation({ protocol: 'http:', hostname })).toBe(false);
  });
});
