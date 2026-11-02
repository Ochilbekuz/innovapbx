// "analytics" namespace — AnalyticsPage (S13: analitika).

export const uz = {
  title: 'Analitika',
  range: {
    label: 'Davr', today: 'Bugun', yesterday: 'Kecha', last7: 'Oxirgi 7 kun', last30: 'Oxirgi 30 kun', custom: 'Boshqa',
    fromLabel: 'Boshlanishi', toLabel: 'Tugashi', badRange: 'Sana oraligʻi notoʻgʻri — tartib yoki uzunlik (92 kungacha) shartiga mos emas.',
  },
  queueFilter: { label: 'Navbat', all: 'Barcha navbatlar' },
  kpi: {
    totalCalls: 'Jami qoʻngʻiroqlar', answered: 'Javob berilgan', missed: 'Oʻtkazib yuborilgan',
    avgWait: 'Oʻrtacha kutish', avgTalk: 'Oʻrtacha suhbat', slaLevel: 'SLA darajasi',
  },
  charts: {
    dailyTitle: 'Kunlar boʻyicha', dailyAriaLabel: 'Kunlar boʻyicha qoʻngʻiroqlar diagrammasi',
    hourlyTitle: 'Soatlar boʻyicha', hourlyAriaLabel: 'Soatlar boʻyicha qoʻngʻiroqlar diagrammasi',
    legendIn: 'Kiruvchi', legendOut: 'Chiquvchi', legendMissed: 'Oʻtkazib yuborilgan', empty: 'Bu davrda maʼlumot yoʻq.',
  },
  queuesTable: {
    title: 'Navbatlar boʻyicha', empty: 'Maʼlumot yoʻq',
    column: { name: 'Navbat', calls: 'Qoʻngʻiroqlar', answered: 'Javob berilgan', missed: 'Oʻtkazib yuborilgan', avgWait: 'Oʻrtacha kutish', sla: 'SLA' },
  },
  agentsTable: {
    title: 'Operatorlar boʻyicha', empty: 'Maʼlumot yoʻq',
    column: { name: 'Operator', calls: 'Qoʻngʻiroqlar', talkTime: 'Suhbat vaqti', avgTalk: 'Oʻrtacha suhbat' },
  },
};

export const ru = {
  title: 'Аналитика',
  range: {
    label: 'Период', today: 'Сегодня', yesterday: 'Вчера', last7: 'Последние 7 дней', last30: 'Последние 30 дней', custom: 'Другой',
    fromLabel: 'Начало', toLabel: 'Конец', badRange: 'Неверный диапазон дат — нарушен порядок или длина (до 92 дней).',
  },
  queueFilter: { label: 'Очередь', all: 'Все очереди' },
  kpi: {
    totalCalls: 'Всего звонков', answered: 'Отвечено', missed: 'Пропущено',
    avgWait: 'Среднее ожидание', avgTalk: 'Средний разговор', slaLevel: 'Уровень SLA',
  },
  charts: {
    dailyTitle: 'По дням', dailyAriaLabel: 'Диаграмма звонков по дням',
    hourlyTitle: 'По часам', hourlyAriaLabel: 'Диаграмма звонков по часам',
    legendIn: 'Входящие', legendOut: 'Исходящие', legendMissed: 'Пропущенные', empty: 'За этот период нет данных.',
  },
  queuesTable: {
    title: 'По очередям', empty: 'Нет данных',
    column: { name: 'Очередь', calls: 'Звонки', answered: 'Отвечено', missed: 'Пропущено', avgWait: 'Среднее ожидание', sla: 'SLA' },
  },
  agentsTable: {
    title: 'По операторам', empty: 'Нет данных',
    column: { name: 'Оператор', calls: 'Звонки', talkTime: 'Время разговора', avgTalk: 'Средний разговор' },
  },
};

export const en = {
  title: 'Analytics',
  range: {
    label: 'Range', today: 'Today', yesterday: 'Yesterday', last7: 'Last 7 days', last30: 'Last 30 days', custom: 'Custom',
    fromLabel: 'From', toLabel: 'To', badRange: 'Invalid date range — wrong order or too long (max 92 days).',
  },
  queueFilter: { label: 'Queue', all: 'All queues' },
  kpi: {
    totalCalls: 'Total calls', answered: 'Answered', missed: 'Missed',
    avgWait: 'Avg wait', avgTalk: 'Avg talk time', slaLevel: 'SLA level',
  },
  charts: {
    dailyTitle: 'By day', dailyAriaLabel: 'Calls by day chart',
    hourlyTitle: 'By hour', hourlyAriaLabel: 'Calls by hour chart',
    legendIn: 'Inbound', legendOut: 'Outbound', legendMissed: 'Missed', empty: 'No data for this period.',
  },
  queuesTable: {
    title: 'By queue', empty: 'No data',
    column: { name: 'Queue', calls: 'Calls', answered: 'Answered', missed: 'Missed', avgWait: 'Avg wait', sla: 'SLA' },
  },
  agentsTable: {
    title: 'By agent', empty: 'No data',
    column: { name: 'Agent', calls: 'Calls', talkTime: 'Talk time', avgTalk: 'Avg talk' },
  },
};
