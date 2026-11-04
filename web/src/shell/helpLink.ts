/** Menyu ekrani bo'lmagan (yoki boshqa ekran ostidagi), lekin o'z qo'llanma bo'limi bor sahifalar — prefiks bo'yicha. */
const PATH_DOCS: [prefix: string, docId: string][] = [
  ['/settings/revisions', 'revisions'],
  ['/settings/integrations/widget', 'callback-widget'],
  ['/softphone', 'portal'],
];

/** Sarlavhadagi «?» havolasi: joriy sahifaning qo'llanma bo'limi (bo'lim id = ekran id), topilmasa — mundarija. */
export function helpPathFor(pathname: string, activeId: string | undefined): string {
  const special = PATH_DOCS.find(([prefix]) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  if (special) return `/docs/${special[1]}`;
  return activeId ? `/docs/${activeId}` : '/docs';
}
