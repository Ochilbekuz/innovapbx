// tokens.json (+ tokens.dark.json) -> replica/design/tokens.css
// Bitta manba: rang/o'lcham qarori faqat JSON'da yashaydi. CSS qo'lda tahrirlanmaydi.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const designDir = resolve(here, '../../replica/design');
const read = (name) => JSON.parse(readFileSync(resolve(designDir, name), 'utf8'));

const light = read('tokens.json');
const dark = read('tokens.dark.json');

const channels = (hex) => {
  const h = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).join(' ');
};
const visible = (obj) => Object.entries(obj).filter(([k]) => !k.startsWith('_'));
const px = (n) => `${n}px`;

const colorVars = (color) => visible(color).map(([k, v]) => `  --c-${k}: ${channels(v)};`);
const shadowVars = (shadow) => visible(shadow).map(([k, v]) => `  --shadow-${k}: ${v};`);

const rootVars = [
  ...colorVars(light.color),
  ...visible(light.font).map(([k, v]) => `  --font-${k}: ${v};`),
  ...visible(light.radius).map(([k, v]) => `  --radius-${k}: ${px(v)};`),
  ...shadowVars(light.shadow),
  ...visible(light.motion).map(([k, v]) => `  --motion-${k}: ${v};`),
  ...visible(light.control).map(([k, v]) => `  --control-${k}: ${px(v)};`),
  ...visible(light.layout)
    .filter(([, v]) => typeof v === 'number')
    .map(([k, v]) => `  --layout-${k}: ${px(v)};`),
];

const css = `/* YARATILGAN FAYL — tahrirlamang. Manba: tokens.json, tokens.dark.json. Qayta yaratish: (web) npm run tokens */
:root {
  color-scheme: light;
${rootVars.join('\n')}
}

[data-theme='dark'] {
  color-scheme: dark;
${[...colorVars(dark.color), ...shadowVars(dark.shadow ?? {})].join('\n')}
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-fast: 0.01ms;
    --motion-base: 0.01ms;
    --motion-slow: 0.01ms;
  }
}
`;

writeFileSync(resolve(designDir, 'tokens.css'), css);
console.log(`tokens.css: ${rootVars.length} root vars, ${Object.keys(dark.color).length} dark colours`);
