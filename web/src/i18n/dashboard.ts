// "dashboard" namespace — DashboardPage (bosh panel).

export const uz = {
  title: 'Boshqaruv paneli',
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',
  direction: { in: 'Kiruvchi', out: 'Chiquvchi', internal: 'Ichki' },
  registration: { registered: 'Reg.', rejected: 'Rad etildi', unregistered: 'Kutilmoqda' },
  health: {
    asterisk: 'Asterisk', database: 'Maʼlumotlar bazasi', disk: 'Disk',
    asteriskDown: 'Asterisk prosessi javob bermayapti', dbDown: 'PostgreSQLga ulanmadi',
    freeSpace: 'Boʻsh joy: {{gb}} GB', trunk: 'Trunk: {{name}}', viewDetails: 'Batafsil',
  },
  alertView: 'Koʻrish',
  kpi: {
    activeCalls: 'Faol qoʻngʻiroqlar', todayTotal: 'Bugungi jami', answered: 'Javob berildi',
    missed: 'Oʻtkazib yuborilgan', avgWait: 'Oʻrtacha kutish', unit: 'ta', noCallsYet: 'Hali qoʻngʻiroq yoʻq',
  },
  hourly: {
    ariaLabel: 'Bugungi soatlik hajm', title: 'Soatlik hajm',
    legendIn: 'Kiruvchi', legendOut: 'Chiquvchi', legendMissed: 'Oʻtkazib yuborilgan',
    empty: 'Bugun hali qoʻngʻiroq boʻlmagan.',
  },
  live: { ariaLabel: 'Jonli qoʻngʻiroqlar', title: 'Jonli qoʻngʻiroqlar', empty: 'Hozir faol qoʻngʻiroq yoʻq.' },
  queues: { ariaLabel: 'Navbatlar', title: 'Navbatlar', empty: 'Navbatlar sozlanmagan.', online: 'onlayn', waiting: 'kutmoqda' },
  missedCalls: {
    ariaLabel: 'Oʻtkazib yuborilgan qoʻngʻiroqlar', title: 'Oʻtkazib yuborilgan qoʻngʻiroqlar',
    empty: 'Bugun oʻtkazib yuborilgan qoʻngʻiroq yoʻq.', calledBack: 'Qaytarilgan', notCalledBack: 'Qaytarilmagan',
    callBack: 'Qaytarib chaqirish',
  },
  parking: {
    ariaLabel: 'Kutish xonasidagi qoʻngʻiroqlar', title: 'Kutish xonasi (park)',
    loading: 'Yuklanmoqda…', loadFailed: 'Yuklab boʻlmadi.', empty: 'Hozir kutib turgan qoʻngʻiroq yoʻq.',
    parkedBy: '{{who}} qoʻydi',
  },
};

export const ru = {
  title: 'Панель управления',
  loadFailed: 'Не удалось загрузить.',
  retry: 'Повторить',
  direction: { in: 'Входящий', out: 'Исходящий', internal: 'Внутренний' },
  registration: { registered: 'Рег.', rejected: 'Отклонено', unregistered: 'Ожидание' },
  health: {
    asterisk: 'Asterisk', database: 'База данных', disk: 'Диск',
    asteriskDown: 'Процесс Asterisk не отвечает', dbDown: 'Нет соединения с PostgreSQL',
    freeSpace: 'Свободно: {{gb}} ГБ', trunk: 'Транк: {{name}}', viewDetails: 'Подробнее',
  },
  alertView: 'Открыть',
  kpi: {
    activeCalls: 'Активные звонки', todayTotal: 'Всего сегодня', answered: 'Отвечено',
    missed: 'Пропущено', avgWait: 'Среднее ожидание', unit: '', noCallsYet: 'Звонков пока нет',
  },
  hourly: {
    ariaLabel: 'Почасовой объём за сегодня', title: 'Почасовой объём',
    legendIn: 'Входящие', legendOut: 'Исходящие', legendMissed: 'Пропущенные',
    empty: 'Сегодня звонков пока не было.',
  },
  live: { ariaLabel: 'Текущие звонки', title: 'Текущие звонки', empty: 'Сейчас нет активных звонков.' },
  queues: { ariaLabel: 'Очереди', title: 'Очереди', empty: 'Очереди не настроены.', online: 'онлайн', waiting: 'в ожидании' },
  missedCalls: {
    ariaLabel: 'Пропущенные звонки', title: 'Пропущенные звонки',
    empty: 'Сегодня пропущенных звонков нет.', calledBack: 'Перезвонили', notCalledBack: 'Не перезвонили',
    callBack: 'Перезвонить',
  },
  parking: {
    ariaLabel: 'Звонки на парковке', title: 'Парковка вызовов',
    loading: 'Загрузка…', loadFailed: 'Не удалось загрузить.', empty: 'Сейчас на парковке нет звонков.',
    parkedBy: 'Поставил: {{who}}',
  },
};

export const en = {
  title: 'Dashboard',
  loadFailed: "Couldn't load.",
  retry: 'Retry',
  direction: { in: 'Inbound', out: 'Outbound', internal: 'Internal' },
  registration: { registered: 'Reg.', rejected: 'Rejected', unregistered: 'Pending' },
  health: {
    asterisk: 'Asterisk', database: 'Database', disk: 'Disk',
    asteriskDown: 'The Asterisk process is not responding', dbDown: 'Could not connect to PostgreSQL',
    freeSpace: 'Free space: {{gb}} GB', trunk: 'Trunk: {{name}}', viewDetails: 'Details',
  },
  alertView: 'View',
  kpi: {
    activeCalls: 'Active calls', todayTotal: "Today's total", answered: 'Answered',
    missed: 'Missed', avgWait: 'Avg. wait', unit: '', noCallsYet: 'No calls yet',
  },
  hourly: {
    ariaLabel: "Today's hourly volume", title: 'Hourly volume',
    legendIn: 'Inbound', legendOut: 'Outbound', legendMissed: 'Missed',
    empty: 'No calls yet today.',
  },
  live: { ariaLabel: 'Live calls', title: 'Live calls', empty: 'No active calls right now.' },
  queues: { ariaLabel: 'Queues', title: 'Queues', empty: 'No queues configured.', online: 'online', waiting: 'waiting' },
  missedCalls: {
    ariaLabel: 'Missed calls', title: 'Missed calls',
    empty: 'No missed calls today.', calledBack: 'Called back', notCalledBack: 'Not called back',
    callBack: 'Call back',
  },
  parking: {
    ariaLabel: 'Parked calls', title: 'Parking lot',
    loading: 'Loading…', loadFailed: 'Could not load.', empty: 'No calls parked right now.',
    parkedBy: 'Parked by {{who}}',
  },
};
