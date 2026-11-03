import { describe, expect, it } from 'vitest';
import { currentTotpCode, generateRecoveryCodes, generateTotpSecret, otpauthUri, stepOf, verifyTotp } from './totp';

describe('totp', () => {
  it('generates a base32 secret with no padding/invalid chars', () => {
    const secret = generateTotpSecret();
    expect(secret).toMatch(/^[A-Z2-7]+$/);
    expect(secret.length).toBeGreaterThanOrEqual(30);
  });

  it('verifies the code it just generated for "now"', async () => {
    const secret = generateTotpSecret();
    const code = await currentTotpCode(secret);
    expect(code).toMatch(/^\d{6}$/);
    const step = await verifyTotp(secret, code);
    expect(step).toBe(stepOf(Date.now() / 1000));
  });

  it('rejects a wrong code', async () => {
    const secret = generateTotpSecret();
    const code = await currentTotpCode(secret);
    const wrong = code === '000000' ? '111111' : '000000';
    expect(await verifyTotp(secret, wrong)).toBeNull();
  });

  it('rejects replay of an already-used step', async () => {
    const secret = generateTotpSecret();
    const now = Date.now();
    const code = await currentTotpCode(secret, now);
    const step = stepOf(now / 1000);
    expect(await verifyTotp(secret, code, now, step)).toBeNull();
  });

  it('accepts the previous/next step (±1 tolerance)', async () => {
    const secret = generateTotpSecret();
    const now = Date.now();
    const prevStepCode = await (await import('./totp')).totpAt(secret, stepOf(now / 1000) - 1);
    expect(await verifyTotp(secret, prevStepCode, now)).toBe(stepOf(now / 1000) - 1);
  });

  it('builds an otpauth URI with issuer/tenant/username', () => {
    const uri = otpauthUri('ABCDEFGHIJKLMNOP', 'acme', 'admin');
    expect(uri).toContain('otpauth://totp/');
    expect(uri).toContain('issuer=Innova%20PBX');
    expect(uri).toContain('secret=ABCDEFGHIJKLMNOP');
  });

  it('generates 10 unique recovery codes in xxxx-xxxx format', () => {
    const codes = generateRecoveryCodes();
    expect(codes).toHaveLength(10);
    for (const c of codes) expect(c).toMatch(/^[0-9a-f]{4}-[0-9a-f]{4}$/);
    expect(new Set(codes).size).toBe(10);
  });
});
