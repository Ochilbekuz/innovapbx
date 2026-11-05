import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { parse, type ParserPlugin } from '@babel/parser';
import traverseModule, { type NodePath } from '@babel/traverse';
import * as bt from '@babel/types';

// `typescript@7` (native port) olib tashlagan klassik Compiler API ('ts.createSourceFile' va sh.k.) o'rniga
// `@babel/parser`+`@babel/traverse` ishlatiladi (Vite/`@vitejs/plugin-react` orqali allaqachon mavjud, pastda
// `package.json`ga ham aniq devDependency sifatida qo'shildi). Babel scope'i yordamida parametr orqali
// soyalangan `t` (masalan `function eventLabel(t, e) {...}`) to'g'ri "useTranslation'dan emas" deb aniqlanadi.
const traverse: typeof traverseModule = (traverseModule as unknown as { default?: typeof traverseModule }).default ?? traverseModule;

// Har bir `src/i18n/<ns>.ts` — `uz`/`ru`/`en` eksport qiladigan nomfazo. Ro'yxat `lib/i18n.ts`dagi
// NAMESPACES bilan bir xil bo'lishi kerak (parity.test.ts ham shunga tayanadi).
import * as access from './access';
import * as alerts from './alerts';
import * as analytics from './analytics';
import * as announcements from './announcements';
import * as audio from './audio';
import * as audit from './audit';
import * as auth from './auth';
import * as backup from './backup';
import * as blacklist from './blacklist';
import * as callback from './callback';
import * as calls from './calls';
import * as campaigns from './campaigns';
import * as cidsources from './cidsources';
import * as common from './common';
import * as conferences from './conferences';
import * as dashboard from './dashboard';
import * as daynight from './daynight';
import * as devices from './devices';
import * as disa from './disa';
import * as docs from './docs';
import * as errors from './errors';
import * as extensions from './extensions';
import * as featurecodes from './featurecodes';
import * as firewall from './firewall';
import * as followme from './followme';
import * as integrations from './integrations';
import * as ivr from './ivr';
import * as license from './license';
import * as live from './live';
import * as me from './me';
import * as migration from './migration';
import * as misc from './misc';
import * as missedcalls from './missedcalls';
import * as network from './network';
import * as notify from './notify';
import * as outbound from './outbound';
import * as paging from './paging';
import * as parking from './parking';
import * as phonebook from './phonebook';
import * as pinsets from './pinsets';
import * as quality from './quality';
import * as queues from './queues';
import * as recordings from './recordings';
import * as revisions from './revisions';
import * as ringgroups from './ringgroups';
import * as routes from './routes';
import * as security from './security';
import * as setup from './setup';
import * as shell from './shell';
import * as sip from './sip';
import * as status from './status';
import * as time from './time';
import * as timegroups from './timegroups';
import * as trunks from './trunks';
import * as update from './update';
import * as users from './users';
import * as voicemail from './voicemail';

type Lang = 'uz' | 'ru' | 'en';
type AnyObj = Record<string, unknown>;

const LANGS: Lang[] = ['uz', 'ru', 'en'];

const RESOURCES: Record<string, Record<Lang, AnyObj>> = {
  access, alerts, analytics, announcements, audio, audit, auth, backup, blacklist, callback, calls, campaigns,
  cidsources, common, conferences, dashboard, daynight, devices, disa, docs, errors, extensions, featurecodes,
  firewall, followme, integrations, ivr, license, live, me, migration, misc, missedcalls, network, notify, outbound,
  paging, parking, phonebook, pinsets, quality, queues, recordings, revisions, ringgroups, routes, security,
  setup, shell, sip, status, time, timegroups, trunks, update, users, voicemail,
};

const SRC_DIR = path.resolve(__dirname, '..');

/** `useTranslation()` (argumentsiz) sukut nomfazosi — `lib/i18n.ts`dagi haqiqiy `defaultNS`dan o'qiladi,
 * shunda u o'zgarsa qo'riqchi avtomatik yangilanadi (qattiq kodlanmagan). */
const DEFAULT_NS: string = (() => {
  const src = fs.readFileSync(path.join(SRC_DIR, 'lib/i18n.ts'), 'utf8');
  const m = src.match(/defaultNS:\s*'([\w-]+)'/);
  const value = m?.[1];
  if (!value) throw new Error("lib/i18n.ts'da `defaultNS: '...'` topilmadi — usage.test.ts shuni kutadi.");
  return value;
})();

/**
 * Noaniq (statik aniqlab bo'lmaydigan) chaqiruvlar — har biri qo'lda tekshirilgan va sababi yozilgan.
 * Kichik tutilsin: yangi noaniq holat chiqsa, avval haqiqiy aniqlashni kengaytirishga harakat qiling,
 * faqat iloji bo'lmasa shu yerga qo'shing.
 */
const ALLOWLIST: Record<string, string> = {
  'shell/TabbedAdminPage.tsx':
    "`ns` — har chaqiruvchidan keladigan runtime prop (devices/integrations/backup), statik aniqlanmaydi. " +
    "Qo'lda tekshirildi: `title`/`readOnlyBanner` uz/ru/en'da uchta chaqiruvchi nomfazosida (devices, integrations, backup) ham bor.",
  'shell/AppErrorBoundary.tsx':
    "Lokal `const t = (k) => i18n.t(\\`common:crash.${k}\\`)` — yopilish ichida tuzilgan nomfazo+prefiks, " +
    "umumiy skaner buni ko'rmaydi. Qo'lda tekshirildi: common.crash.title/body/reload uz/ru/en'da bor.",
  'screens/backup/SettingsTab.tsx':
    "`StorageSection` titleKey/enabledLabelKey/testLabelKey/okKey/failKey'ni boshqa funksiyalarga (StorageTargetSection/" +
    "TestTargetRow/TestResultLine) oddiy prop sifatida uzatadi; chaqiruv joyida ular `` `settings.${kind}.xxx` `` shablonidan " +
    "hosil bo'ladi, lekin ishlatilish joyida faqat identifikator ko'rinadi (kross-funksiya data-flow, statik skaner kuzata olmaydi). " +
    "Qo'lda tekshirildi: kind = 's3'|'sftp' uchun settings.s3.*/settings.sftp.* (title/enabled/test/testOk/testFailed) uz/ru/en'da bor.",
  'screens/backup/RestoreTab.tsx':
    "`t(v.key)` — `v` lokal `COMPATIBILITY_VARIANT` obyektidan kelgan element, kalit ichma-ich `key` maydonida " +
    "(oddiy satr xaritasi emas — ichida obyekt), umumiy xarita-aniqlagich buni qamramaydi. Qo'lda tekshirildi: " +
    "restore.inspect.compatible/incompatible uz/ru/en'da bor.",
  'screens/backup/backupForms.ts':
    "`backupFinishedToast`/`backupFailedToast` `t`ni oddiy parametr sifatida oladi (`JobToastTranslate` tipi); " +
    "haqiqiy nomfazo faqat chaqiruvchi `BackupsTab.tsx`dagi `useTranslation('backup')`da — fayllar-aro oqim, " +
    "statik skaner buni kuzata olmaydi. Qo'lda tekshirildi: job.partialToast/okToast/failedToast uz/ru/en'da bor.",
  'screens/devices/deviceForms.ts':
    "`assignModalDescription`/`keysModalTitle`/`keyTypeOptions` `t`ni parametr sifatida oladi, haqiqiy nomfazo " +
    "faqat chaqiruvchi `DevicesTab.tsx`dagi `useTranslation('devices')`da — fayllar-aro oqim. Qo'lda tekshirildi: " +
    "discovered.assignModalDesc, keysModal.title, keysModal.typeOption.* uz/ru/en'da bor.",
  'screens/devices/provisioningForm.ts':
    "`adminPasswordHint` `t`ni parametr sifatida oladi, haqiqiy nomfazo faqat chaqiruvchi `SettingsTab.tsx`dagi " +
    "`useTranslation('devices')`da — fayllar-aro oqim. Qo'lda tekshirildi: settings.adminPasswordSet/adminPasswordHint " +
    "uz/ru/en'da bor.",
  'screens/time/ClockPanel.tsx':
    "`ClockPanel` komponenti `t`ni oddiy prop sifatida oladi (`TFunc` tipi), haqiqiy nomfazo faqat chaqiruvchi " +
    "`TimeSettingsPage.tsx`dagi `useTranslation('time')`da — fayllar-aro oqim (JSX prop, pozitsion parametr emas, " +
    "shu sabab umumiy render-prop qoidasiga ham mos kelmaydi). Qo'lda tekshirildi: serverTimeLabel/ntpOff/syncedYes/" +
    "syncedNo/syncServerLabel/syncServerNone/syncNow uz/ru/en'da bor.",
};

type NsBinding = { kind: 'single'; ns: string } | { kind: 'array'; list: string[] } | { kind: 'unknown' };

/** `obj.a.b.c` yo'lini navigatsiya qiladi; topilmasa `undefined`. */
function getPath(root: AnyObj, dotted: string): unknown {
  let cur: unknown = root;
  for (const part of dotted.split('.')) {
    if (cur === null || typeof cur !== 'object' || Array.isArray(cur)) return undefined;
    cur = (cur as AnyObj)[part];
    if (cur === undefined) return undefined;
  }
  return cur;
}

function leafExists(ns: string, lang: Lang, key: string, opts: { returnObjects: boolean }): boolean {
  const root = RESOURCES[ns]?.[lang];
  if (!root) return false;
  const value = getPath(root, key);
  if (value === undefined) return false;
  return opts.returnObjects ? true : typeof value === 'string';
}

const PLURAL_SUFFIXES = ['_zero', '_one', '_two', '_few', '_many', '_other'];

/** Kalit uz/ru/en'ning HAMMASIDA mavjudligini tekshiradi (plural variantlarini ham hisobga oladi). */
function keyExistsEverywhere(ns: string, key: string, opts: { hasCount: boolean; returnObjects: boolean }): boolean {
  return LANGS.every((lang) => {
    if (leafExists(ns, lang, key, opts)) return true;
    return opts.hasCount && PLURAL_SUFFIXES.some((suf) => leafExists(ns, lang, key + suf, opts));
  });
}

/** Dinamik kalit prefiksi (`status.` yoki `field.smtpTls`) — oxirgi segment to'liq bo'lmasa, qardosh
 * kalitlar orasida shu bilan boshlanuvchisi bor-yo'qligini tekshiradi. */
function hasPrefixPath(root: AnyObj, prefix: string): boolean {
  const endsWithDot = prefix.endsWith('.');
  const trimmed = endsWithDot ? prefix.slice(0, -1) : prefix;
  const parts = trimmed.split('.');
  const last = endsWithDot ? '' : (parts.pop() ?? '');
  let cur: unknown = root;
  for (const part of parts) {
    if (cur === null || typeof cur !== 'object' || Array.isArray(cur)) return false;
    cur = (cur as AnyObj)[part];
    if (cur === undefined) return false;
  }
  if (cur === null || typeof cur !== 'object' || Array.isArray(cur)) return false;
  if (last === '') return true;
  return Object.keys(cur as AnyObj).some((k) => k.startsWith(last));
}

function prefixExistsEverywhere(ns: string, prefix: string): boolean {
  return LANGS.every((lang) => {
    const root = RESOURCES[ns]?.[lang];
    return root ? hasPrefixPath(root, prefix) : false;
  });
}

/** `"ns:rest"` shaklini ajratadi — faqat `ns` haqiqiy ro'yxatdagi nomfazo bo'lsa (tasodifiy `:` bilan
 * adashmasin, masalan vaqt yoki URL matnlari). */
function splitNs(text: string): { ns: string | null; rest: string } {
  const idx = text.indexOf(':');
  if (idx > 0) {
    const candidate = text.slice(0, idx);
    if (candidate in RESOURCES) return { ns: candidate, rest: text.slice(idx + 1) };
  }
  return { ns: null, rest: text };
}

function nsBindingFromUseTranslationArgs(args: readonly (bt.Expression | bt.SpreadElement | bt.ArgumentPlaceholder)[]): NsBinding {
  if (args.length === 0) return { kind: 'single', ns: DEFAULT_NS };
  const first = args[0];
  if (bt.isStringLiteral(first)) return { kind: 'single', ns: first.value };
  if (bt.isArrayExpression(first) && first.elements.length > 0 && first.elements.every((e) => e !== null && bt.isStringLiteral(e))) {
    return { kind: 'array', list: (first.elements as bt.StringLiteral[]).map((e) => e.value) };
  }
  return { kind: 'unknown' };
}

/** Modul darajasidagi faktlarni to'playdi: (1) `@/lib/i18n`dan import qilingan `i18n`, (2) faylda ishlatilgan
 * yagona literal nomfazo (parametr sifatida uzatilgan `t` uchun zaxira), (3) hamma qiymati literal satr
 * bo'lgan konst xaritalar (`t(MAP[x])` kabi element-access kalitlarni to'liq sanab chiqish uchun). */
function collectFileFacts(ast: bt.File) {
  const fileNamespaces = new Set<string>();
  const stringMaps = new Map<string, string[]>();
  let hasI18nDefaultImport = false;

  traverse(ast, {
    ImportDeclaration(path) {
      if (path.node.source.value !== '@/lib/i18n') return;
      for (const spec of path.node.specifiers) {
        if (bt.isImportDefaultSpecifier(spec) && spec.local.name === 'i18n') hasI18nDefaultImport = true;
      }
    },
    CallExpression(path) {
      const { node } = path;
      if (!bt.isIdentifier(node.callee) || node.callee.name !== 'useTranslation') return;
      const [arg] = node.arguments;
      if (arg && bt.isStringLiteral(arg)) fileNamespaces.add(arg.value);
    },
    VariableDeclarator(path) {
      const { node } = path;
      if (!bt.isIdentifier(node.id) || !node.init) return;
      const init = bt.isTSAsExpression(node.init) ? node.init.expression : node.init;
      if (!bt.isObjectExpression(init)) return;
      const values: string[] = [];
      const allLiteral = init.properties.every((prop) => {
        if (bt.isObjectProperty(prop) && !prop.computed && bt.isStringLiteral(prop.value)) {
          values.push(prop.value.value);
          return true;
        }
        return false;
      });
      if (allLiteral && values.length > 0) stringMaps.set(node.id.name, values);
    },
  });

  return {
    fileDefaultNs: fileNamespaces.size === 1 ? [...fileNamespaces][0] : undefined,
    stringMaps,
    hasI18nDefaultImport,
  };
}

type ParsedKey = { kind: 'skip' } | { kind: 'literal'; texts: string[] } | { kind: 'dynamic'; head: string };

function parseKeyArg(arg: bt.Expression, stringMaps: Map<string, string[]>): ParsedKey {
  if (bt.isStringLiteral(arg)) return { kind: 'literal', texts: [arg.value] };
  if (bt.isTemplateLiteral(arg)) {
    const head = arg.quasis[0]?.value.raw ?? '';
    if (arg.expressions.length === 0) return { kind: 'literal', texts: [head] }; // interpolatsiyasiz shablon
    if (head === '') return { kind: 'skip' }; // boshidanoq dinamik — tekshirish uchun hech narsa yo'q
    return { kind: 'dynamic', head };
  }
  if (bt.isMemberExpression(arg) && arg.computed && bt.isIdentifier(arg.object)) {
    const values = stringMaps.get(arg.object.name);
    if (values) return { kind: 'literal', texts: values };
  }
  return { kind: 'skip' };
}

function findObjectOptionProp(options: bt.ObjectExpression | undefined, name: string): bt.Expression | undefined {
  if (!options) return undefined;
  for (const prop of options.properties) {
    if (bt.isObjectProperty(prop) && !prop.computed && bt.isIdentifier(prop.key) && prop.key.name === name && bt.isExpression(prop.value)) {
      return prop.value;
    }
  }
  return undefined;
}

/** `<TabbedAdminPage ns="x" tabs={({ t, ... }) => [...]} />` — `TabbedAdminPage` ichkarida `useTranslation(ns)`
 * chaqirib, natijadagi `t`ni `tabs` render-prop'iga argument sifatida beradi. `ns` chaqiruv joyida literal
 * satr bo'lgani uchun bu holat umumiy allowlist'siz, statik aniqlanadi. */
function nsFromTabsRenderProp(objectPattern: NodePath, calleeName: string): string | undefined {
  if (calleeName !== 't' || !objectPattern.isObjectPattern()) return undefined; // faqat `t` konvensiyasi — `setTab`/`canManage` kabi qardosh parametrlarga tegmaymiz
  const fn = objectPattern.parentPath;
  if (!fn?.isFunction() || fn.node.params[0] !== objectPattern.node) return undefined;
  const attr = fn.parentPath?.isJSXExpressionContainer() ? fn.parentPath.parentPath : undefined;
  if (!attr?.isJSXAttribute() || !bt.isJSXIdentifier(attr.node.name) || attr.node.name.name !== 'tabs') return undefined;
  const openingElement = attr.parentPath;
  if (!openingElement?.isJSXOpeningElement() || !bt.isJSXIdentifier(openingElement.node.name) || openingElement.node.name.name !== 'TabbedAdminPage') {
    return undefined;
  }
  for (const a of openingElement.node.attributes) {
    if (bt.isJSXAttribute(a) && bt.isJSXIdentifier(a.name) && a.name.name === 'ns' && bt.isStringLiteral(a.value)) return a.value.value;
  }
  return undefined;
}

/** `t` (yoki uning qayta nomlangan nusxasi) chaqiruvchi identifikatorining qaysi `useTranslation(...)`
 * natijasidan kelganini Babel'ning leksik scope'i orqali aniqlaydi. Parametr sifatida soyalangan `t`
 * (masalan `function eventLabel(t, e) {...}`) deklarator emas — shu sabab `undefined` qaytadi va
 * chaqiruvchi faylning yagona nomfazosiga (`fileDefaultNs`) tushadi (yoki `nsFromTabsRenderProp` orqali). */
function resolveTBinding(path: NodePath, calleeName: string): NsBinding | undefined {
  const binding = path.scope.getBinding(calleeName);
  const declPath = binding?.path;
  if (!declPath) return undefined;
  if (declPath.isObjectPattern()) {
    const ns = nsFromTabsRenderProp(declPath, calleeName);
    return ns ? { kind: 'single', ns } : undefined;
  }
  if (!declPath.isVariableDeclarator()) return undefined;
  const init = declPath.node.init;
  if (!init || !bt.isCallExpression(init) || !bt.isIdentifier(init.callee) || init.callee.name !== 'useTranslation') return undefined;
  return nsBindingFromUseTranslationArgs(init.arguments);
}

/** Bitta faylni skanerlaydi va topilgan har bir yetishmayotgan kalit/prefiks/aniqlanmagan chaqiruv uchun
 * inson o'qiydigan satr qaytaradi (bo'sh ro'yxat — fayl toza). */
function analyzeFile(file: string, rel: string): string[] {
  const text = fs.readFileSync(file, 'utf8');
  const plugins: ParserPlugin[] = ['typescript'];
  if (rel.endsWith('.tsx')) plugins.push('jsx');
  const ast = parse(text, { sourceType: 'module', plugins });
  const problems: string[] = [];
  const { fileDefaultNs, stringMaps, hasI18nDefaultImport } = collectFileFacts(ast);

  function lineOf(node: bt.Node): number {
    return node.loc?.start.line ?? 0;
  }

  function resolveNsList(binding: NsBinding): string[] | null {
    if (binding.kind === 'single') return [binding.ns];
    if (binding.kind === 'array') return binding.list;
    return null;
  }

  function reportMissing(node: bt.Node, nsList: string[], key: string, dynamic: boolean) {
    const where = `${rel}:${lineOf(node)}`;
    const label = dynamic ? `${key}*` : key;
    problems.push(`${where} — kalit topilmadi: ${nsList.join('|')}:${label}`);
  }

  function checkCallArgs(node: bt.CallExpression, binding: NsBinding) {
    const [keyArg, optionsArg] = node.arguments;
    if (!keyArg || !bt.isExpression(keyArg)) return;
    const options = optionsArg && bt.isObjectExpression(optionsArg) ? optionsArg : undefined;

    if (findObjectOptionProp(options, 'defaultValue')) return; // ataylab ixtiyoriy — mos kelmasa fallback qaytadi

    const nsOverrideExpr = findObjectOptionProp(options, 'ns');
    const nsOverride = nsOverrideExpr && bt.isStringLiteral(nsOverrideExpr) ? nsOverrideExpr.value : undefined;
    const hasCount = Boolean(findObjectOptionProp(options, 'count'));
    const returnObjects = (() => {
      const expr = findObjectOptionProp(options, 'returnObjects');
      return Boolean(expr && bt.isBooleanLiteral(expr) && expr.value === true);
    })();

    const parsed = parseKeyArg(keyArg, stringMaps);
    if (parsed.kind === 'skip') return;

    if (parsed.kind === 'literal') {
      for (const raw of parsed.texts) {
        const { ns: inlineNs, rest } = splitNs(raw);
        const nsList = nsOverride ? [nsOverride] : inlineNs ? [inlineNs] : resolveNsList(binding);
        if (!nsList) {
          problems.push(`${rel}:${lineOf(node)} — nomfazo aniqlanmadi, kalit tekshirilmadi: ${raw}`);
          continue;
        }
        if (!nsList.some((ns) => keyExistsEverywhere(ns, rest, { hasCount, returnObjects }))) {
          reportMissing(node, nsList, rest, false);
        }
      }
      return;
    }

    // dynamic (shablon, bitta yoki ko'proq ifodali)
    const { ns: inlineNs, rest } = splitNs(parsed.head);
    if (!rest) return; // nomfazodan keyin hech literal qism qolmadi — to'liq dinamik, e'tiborsiz
    const nsList = nsOverride ? [nsOverride] : inlineNs ? [inlineNs] : resolveNsList(binding);
    if (!nsList) {
      problems.push(`${rel}:${lineOf(node)} — nomfazo aniqlanmadi, dinamik kalit tekshirilmadi: ${rest}*`);
      return;
    }
    if (!nsList.some((ns) => prefixExistsEverywhere(ns, rest))) {
      reportMissing(node, nsList, rest, true);
    }
  }

  traverse(ast, {
    CallExpression(path) {
      const { node } = path;
      const callee = node.callee;
      if (bt.isIdentifier(callee)) {
        if (callee.name === 'useTranslation') return; // bu o'zi tekshiriladigan chaqiruv emas
        const resolved = resolveTBinding(path, callee.name);
        if (resolved) {
          checkCallArgs(node, resolved);
          return;
        }
        if (callee.name !== 't') return; // faqat `t` konvensiyasidagi chaqiruvlarga tegamiz
        // `t` useTranslation'dan kelmadi (masalan boshqa funksiyadan parametr sifatida olingan) —
        // faylning yagona nomfazosiga tushamiz; kalitning o'zida inline `ns:` prefiksi bo'lsa
        // (masalan `common:day.${d}`) baribir `checkCallArgs` ichida to'g'ri aniqlanadi.
        checkCallArgs(node, fileDefaultNs ? { kind: 'single', ns: fileDefaultNs } : { kind: 'unknown' });
        return;
      }
      if (
        bt.isMemberExpression(callee) &&
        !callee.computed &&
        bt.isIdentifier(callee.object) &&
        callee.object.name === 'i18n' &&
        bt.isIdentifier(callee.property) &&
        (callee.property.name === 't' || callee.property.name === 'exists')
      ) {
        if (!hasI18nDefaultImport) {
          problems.push(`${rel}:${lineOf(node)} — \`i18n.${callee.property.name}(...)\` chaqirildi, lekin \`@/lib/i18n\` dan standart import topilmadi.`);
          return;
        }
        checkCallArgs(node, { kind: 'single', ns: DEFAULT_NS });
      }
    },
  });

  return problems;
}

function collectFiles(dir: string, out: string[] = []): string[] {
  for (const name of fs.readdirSync(dir)) {
    if (name.startsWith('.')) continue;
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) {
      collectFiles(full, out);
      continue;
    }
    if (!/\.(ts|tsx)$/.test(name)) continue;
    if (name.includes('.bak')) continue;
    if (/\.(test|spec)\.(ts|tsx)$/.test(name)) continue;
    out.push(full);
  }
  return out;
}

describe("i18n kalit foydalanish qo'riqchisi (statik)", () => {
  const files = collectFiles(SRC_DIR);
  const allProblems: string[] = [];

  for (const file of files) {
    const rel = path.relative(SRC_DIR, file).split(path.sep).join('/');
    if (rel in ALLOWLIST) continue;
    allProblems.push(...analyzeFile(file, rel));
  }

  it("useTranslation/t/i18n.t orqali chaqirilgan BARCHA literal kalitlar uz/ru/en resurslarida mavjud", () => {
    expect(allProblems).toEqual([]);
  });

  it('allowlist yozuvlari eskirmagan (hali mavjud fayllarga ishora qiladi)', () => {
    for (const rel of Object.keys(ALLOWLIST)) {
      expect(fs.existsSync(path.join(SRC_DIR, rel)), `allowlist: ${rel} topilmadi`).toBe(true);
    }
  });
});
