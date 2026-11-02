import { useTranslation } from 'react-i18next';
import { ComingSoonPage } from './ComingSoonPage';
import type { ScreenDef } from './screens';

/** `SCREENS` registridagi "full" bo'lmagan ekranlar uchun — nomi sidebar bilan bir xil manbadan (i18n). */
export function ScreenStub({ screen }: { screen: ScreenDef }) {
  const { t } = useTranslation();
  return <ComingSoonPage title={t(`nav.${screen.id}`)} reconId={screen.reconId} note={t('comingSoon.note')} icon={screen.icon} />;
}

/** `EXTRA_ROUTES` — sidebarda ko'rinmaydigan qo'shimcha marshrutlar. */
export function ExtraScreenStub({ reconId, titleKey }: { reconId: string; titleKey: string }) {
  const { t } = useTranslation();
  return <ComingSoonPage title={t(`extra.${titleKey}`)} reconId={reconId} note={t('comingSoon.note')} />;
}
