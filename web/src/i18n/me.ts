// "me" namespace — MePage (S30: mening kabinetim).

export const uz = {
  title: 'Mening kabinetim',
  noExtension: { title: 'Ichki raqam bogʻlanmagan', body: 'Hisobingiz hech qaysi ichki raqamga bogʻlanmagan — adminga murojaat qiling.' },
  dnd: {
    title: 'Band qilmaslik (DND)', description: 'Yoqilganda sizga qoʻngʻiroqlar yetib bormaydi.',
    forwardLabel: 'Qoʻngʻiroqlarni yoʻnaltirish', forwardNone: 'Yoʻnaltirilmagan', forwardTo: '{{number}}ga yoʻnaltirilgan',
    forwardPlaceholder: 'Ichki yoki tashqi raqam', save: 'Saqlash', saved: 'Saqlandi',
    conflict: 'Maʼlumot eskirgan — sahifa yangilandi, qaytadan urining.',
  },
  queues: {
    title: 'Mening navbatlarim', empty: 'Hech qaysi navbatga aʼzo emassiz.',
    loggedIn: 'Kirgan', loggedOut: 'Chiqgan', paused: 'Pauzada',
    login: 'Kirish', logout: 'Chiqish', pause: 'Pauza', resume: 'Davom etish',
    pauseReasonLabel: 'Sabab', pauseReasonPlaceholder: 'Masalan: tushlik',
    notDynamic: 'Statik aʼzolik — kirish/chiqish uchun adminga murojaat qiling.',
  },
  stats: {
    title: 'Bugungi statistika', calls: 'Qoʻngʻiroqlar', talkTime: 'Suhbat vaqti', missed: 'Oʻtkazib yuborilgan',
  },
  recentCalls: { title: 'Soʻnggi qoʻngʻiroqlar', empty: 'Bugun qoʻngʻiroq boʻlmagan.', column: { time: 'Vaqt', from: 'Kimdan', direction: 'Yoʻnalish', duration: 'Davomiyligi' } },
  direction: { in: 'Kiruvchi', out: 'Chiquvchi', internal: 'Ichki' },
  voicemail: {
    title: 'Ovozli xabarlar', empty: 'Ovozli xabarlar yoʻq', listen: 'Tinglash', delete: 'Oʻchirish', unread: 'Oʻqilmagan',
  },
  // M10 C B1 — operator oʻz baholarini koʻradi (kim baholaganini emas).
  evaluations: {
    title: 'Mening baholarim', empty: 'Hali baholanmagansiz.',
    column: { date: 'Sana', checklist: 'Varaqa', score: 'Ball', comment: 'Izoh' },
  },
  // M10 C B2 — ixtiyoriy 2FA: yoqish/oʻchirish/zaxira kodlarni qayta yaratish.
  twofa: {
    title: 'Ikki bosqichli tasdiqlash (2FA)', enabled: 'Yoqilgan', disabled: 'Oʻchirilgan',
    description: 'Yoqilganda kirishda ilovadan 6 xonali kod ham soʻraladi — hisobingiz xavfsizroq boʻladi.',
    enable: 'Yoqish', disable: 'Oʻchirish', regenerate: 'Zaxira kodlarni qayta yaratish', done: 'Tayyor',
    disableIntro: 'Oʻchirish uchun ilovadagi joriy kodni kiriting.',
    regenerateIntro: 'Eski zaxira kodlar ishdan chiqadi — yangilarini yaratish uchun ilovadagi joriy kodni kiriting.',
    codeLabel: 'Tasdiqlash kodi', toastDisabled: '2FA oʻchirildi',
  },
};

export const ru = {
  title: 'Мой кабинет',
  noExtension: { title: 'Внутренний номер не привязан', body: 'Ваша учётная запись не привязана ни к одному внутреннему номеру — обратитесь к администратору.' },
  dnd: {
    title: 'Не беспокоить (DND)', description: 'Когда включено, звонки не будут поступать вам.',
    forwardLabel: 'Переадресация звонков', forwardNone: 'Не настроена', forwardTo: 'Переадресована на {{number}}',
    forwardPlaceholder: 'Внутренний или внешний номер', save: 'Сохранить', saved: 'Сохранено',
    conflict: 'Данные устарели — страница обновлена, попробуйте снова.',
  },
  queues: {
    title: 'Мои очереди', empty: 'Вы не состоите ни в одной очереди.',
    loggedIn: 'В сети', loggedOut: 'Не в сети', paused: 'На паузе',
    login: 'Войти', logout: 'Выйти', pause: 'Пауза', resume: 'Продолжить',
    pauseReasonLabel: 'Причина', pauseReasonPlaceholder: 'Например: обед',
    notDynamic: 'Статическое членство — обратитесь к администратору для входа/выхода.',
  },
  stats: {
    title: 'Статистика за сегодня', calls: 'Звонки', talkTime: 'Время разговора', missed: 'Пропущено',
  },
  recentCalls: { title: 'Недавние звонки', empty: 'Сегодня звонков не было.', column: { time: 'Время', from: 'От кого', direction: 'Направление', duration: 'Длительность' } },
  direction: { in: 'Входящий', out: 'Исходящий', internal: 'Внутренний' },
  voicemail: {
    title: 'Голосовые сообщения', empty: 'Нет голосовых сообщений', listen: 'Прослушать', delete: 'Удалить', unread: 'Непрослушано',
  },
  evaluations: {
    title: 'Мои оценки', empty: 'Вас пока не оценивали.',
    column: { date: 'Дата', checklist: 'Чек-лист', score: 'Балл', comment: 'Комментарий' },
  },
  twofa: {
    title: 'Двухфакторная проверка (2FA)', enabled: 'Включена', disabled: 'Отключена',
    description: 'Когда включена, при входе дополнительно запрашивается 6-значный код из приложения — ваша учётная запись защищена лучше.',
    enable: 'Включить', disable: 'Отключить', regenerate: 'Создать новые резервные коды', done: 'Готово',
    disableIntro: 'Чтобы отключить, введите текущий код из приложения.',
    regenerateIntro: 'Старые резервные коды перестанут работать — чтобы создать новые, введите текущий код из приложения.',
    codeLabel: 'Код подтверждения', toastDisabled: '2FA отключена',
  },
};

export const en = {
  title: 'My cabinet',
  noExtension: { title: 'No extension linked', body: "Your account isn't linked to any extension — contact your admin." },
  dnd: {
    title: 'Do not disturb (DND)', description: "When on, calls won't reach you.",
    forwardLabel: 'Call forwarding', forwardNone: 'Not set', forwardTo: 'Forwarded to {{number}}',
    forwardPlaceholder: 'Internal or external number', save: 'Save', saved: 'Saved',
    conflict: 'Data is stale — the page was refreshed, try again.',
  },
  queues: {
    title: 'My queues', empty: "You aren't a member of any queue.",
    loggedIn: 'Logged in', loggedOut: 'Logged out', paused: 'Paused',
    login: 'Log in', logout: 'Log out', pause: 'Pause', resume: 'Resume',
    pauseReasonLabel: 'Reason', pauseReasonPlaceholder: 'E.g. lunch break',
    notDynamic: 'Static membership — ask your admin to log in/out for you.',
  },
  stats: {
    title: "Today's stats", calls: 'Calls', talkTime: 'Talk time', missed: 'Missed',
  },
  recentCalls: { title: 'Recent calls', empty: 'No calls today.', column: { time: 'Time', from: 'From', direction: 'Direction', duration: 'Duration' } },
  direction: { in: 'Inbound', out: 'Outbound', internal: 'Internal' },
  voicemail: {
    title: 'Voicemail', empty: 'No voicemail', listen: 'Listen', delete: 'Delete', unread: 'Unread',
  },
  evaluations: {
    title: 'My evaluations', empty: "You haven't been evaluated yet.",
    column: { date: 'Date', checklist: 'Checklist', score: 'Score', comment: 'Comment' },
  },
  twofa: {
    title: 'Two-factor verification (2FA)', enabled: 'Enabled', disabled: 'Disabled',
    description: 'When enabled, sign-in also requires a 6-digit code from your app — your account is better protected.',
    enable: 'Enable', disable: 'Disable', regenerate: 'Regenerate recovery codes', done: 'Done',
    disableIntro: 'To disable, enter the current code from your app.',
    regenerateIntro: 'Your old recovery codes will stop working — enter the current code from your app to create new ones.',
    codeLabel: 'Verification code', toastDisabled: '2FA disabled',
  },
};
