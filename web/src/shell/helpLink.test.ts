import { describe, expect, it } from 'vitest';
import { helpPathFor } from './helpLink';

describe('helpPathFor — sarlavhadagi «?» qaysi bo\'limni ochadi', () => {
  it.each([
    ['/ivr', 'ivr', '/docs/ivr'],
    ['/extensions/42', 'extensions', '/docs/extensions'],
    ['/settings/firewall', 'firewall', '/docs/firewall'],
    // menyu ekrani bo'lmagan, lekin o'z bo'limi bor sahifalar
    ['/settings/revisions/7', undefined, '/docs/revisions'],
    ['/settings/integrations/widget', 'integrations', '/docs/callback-widget'],
    ['/softphone', undefined, '/docs/portal'],
    // qo'llanmaning o'zi va noma'lum sahifa — mundarija
    ['/docs/ivr', undefined, '/docs'],
    ['/nimadir', undefined, '/docs'],
  ])('%s → %s', (pathname, activeId, expected) => {
    expect(helpPathFor(pathname, activeId)).toBe(expected);
  });
});
