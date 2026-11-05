// "license" namespace — Litsenziya sahifasi (/settings/license): Bitrix24 OAuth litsenziyasi holati
// va tariflar. Qarang bitrix-oauth-shartnoma.md §1 ("litsenziya" obyekti).

export const uz = {
  title: 'Litsenziya',
  card: {
    title: 'Bitrix24 integratsiyasi',
    notConnectedTitle: 'Bitrix24 ulanmagan',
    notConnectedDesc: 'Litsenziya holatini koʻrish uchun avval Bitrix24ʼni ulang.',
    goToIntegrations: 'Integratsiyalarga oʻtish',
    loadError: 'Litsenziya holatini yuklab boʻlmadi.',
    retry: 'Qayta yuklash',
    domain: 'Portal: {{domain}}',
    state: {
      sinov: 'Sinov — {{days}} kun qoldi',
      faol: 'Faol — {{date}} gacha',
      imtiyoz: 'Imtiyoz kuni',
      tugagan: 'Tugagan',
      bloklangan: 'Bloklangan',
    },
    progressLabel: 'Muddat tugashiga qoldi',
    trialStarted: 'Sinov boshlangan: {{date}}',
    trialEndsAt: 'Sinov tugaydi: {{date}}',
    paidUntil: 'Toʻlov muddati: {{date}}',
    paidNone: 'Toʻlov qilinmagan',
    tariffsTitle: 'Tariflar',
    tariff: { sinov: '14 kun bepul sinov', '1oy': '1 oy', '3oy': '3 oy', '6oy': '6 oy', '1yil': '1 yil' },
    contactInnova: 'Litsenziyani uzaytirish uchun Innova bilan bogʻlaning.',
  },
};

export const ru = {
  title: 'Лицензия',
  card: {
    title: 'Интеграция Bitrix24',
    notConnectedTitle: 'Bitrix24 не подключён',
    notConnectedDesc: 'Чтобы увидеть статус лицензии, сначала подключите Bitrix24.',
    goToIntegrations: 'Перейти в интеграции',
    loadError: 'Не удалось загрузить статус лицензии.',
    retry: 'Загрузить снова',
    domain: 'Портал: {{domain}}',
    state: {
      sinov: 'Пробный период — осталось {{days}} дн.',
      faol: 'Активна — до {{date}}',
      imtiyoz: 'Льготный день',
      tugagan: 'Истекла',
      bloklangan: 'Заблокирована',
    },
    progressLabel: 'Осталось до окончания срока',
    trialStarted: 'Пробный период начат: {{date}}',
    trialEndsAt: 'Пробный период закончится: {{date}}',
    paidUntil: 'Оплачено до: {{date}}',
    paidNone: 'Оплата не произведена',
    tariffsTitle: 'Тарифы',
    tariff: { sinov: '14 дней бесплатно', '1oy': '1 месяц', '3oy': '3 месяца', '6oy': '6 месяцев', '1yil': '1 год' },
    contactInnova: 'Чтобы продлить лицензию, свяжитесь с Innova.',
  },
};

export const en = {
  title: 'License',
  card: {
    title: 'Bitrix24 integration',
    notConnectedTitle: 'Bitrix24 is not connected',
    notConnectedDesc: 'Connect Bitrix24 first to see the license status.',
    goToIntegrations: 'Go to Integrations',
    loadError: 'Could not load the license status.',
    retry: 'Reload',
    domain: 'Portal: {{domain}}',
    state: {
      sinov: 'Trial — {{days}} days left',
      faol: 'Active — until {{date}}',
      imtiyoz: 'Grace day',
      tugagan: 'Expired',
      bloklangan: 'Blocked',
    },
    progressLabel: 'Time left until expiry',
    trialStarted: 'Trial started: {{date}}',
    trialEndsAt: 'Trial ends: {{date}}',
    paidUntil: 'Paid until: {{date}}',
    paidNone: 'No payment made',
    tariffsTitle: 'Plans',
    tariff: { sinov: '14-day free trial', '1oy': '1 month', '3oy': '3 months', '6oy': '6 months', '1yil': '1 year' },
    contactInnova: 'Contact Innova to extend the license.',
  },
};
