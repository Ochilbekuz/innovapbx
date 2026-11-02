// "audit" namespace — AuditPage (audit jurnali).

export const uz = {
  title: 'Audit jurnali',
  action: {
    create: 'Yaratildi', update: 'Oʻzgartirildi', delete: 'Oʻchirildi', login: 'Kirildi', login_failed: 'Kirish xato',
    restore: 'Qaytarildi', restart: 'Qayta ishga tushirildi', override: 'Vaqtincha oʻzgartirildi', spy: 'Tinglash/kirish',
  },
  column: { at: 'Vaqt', user: 'Kim', action: 'Amal', entity: 'Obʼyekt', label: 'Nima', ip: 'IP' },
  systemUser: 'tizim',
  viewDiffAriaLabel: 'Farqni koʻrish',
  filter: { from: 'Boshlanishi', to: 'Tugashi', action: 'Amal', all: 'Hammasi', entity: 'Obʼyekt turi', entityPlaceholder: 'trunk, extension…', optional: 'ixtiyoriy', search: 'Qidirish', searchPlaceholder: 'login, obʼyekt nomi…' },
  caption: 'Audit jurnali',
  empty: { title: 'Bu filtrga mos yozuv topilmadi', body: 'Sana oraligʻini yoki filtrlarni oʻzgartirib koʻring.' },
  close: 'Yopish',
  diff: { empty: 'Oʻzgarish tafsiloti yoʻq.', field: 'Maydon', before: 'Eski', after: 'Yangi' },
};

export const ru = {
  title: 'Журнал аудита',
  action: {
    create: 'Создано', update: 'Изменено', delete: 'Удалено', login: 'Вход', login_failed: 'Ошибка входа',
    restore: 'Восстановлено', restart: 'Перезапущено', override: 'Временно изменено', spy: 'Прослушивание',
  },
  column: { at: 'Время', user: 'Кто', action: 'Действие', entity: 'Объект', label: 'Что', ip: 'IP' },
  systemUser: 'система',
  viewDiffAriaLabel: 'Посмотреть изменения',
  filter: { from: 'Начало', to: 'Конец', action: 'Действие', all: 'Все', entity: 'Тип объекта', entityPlaceholder: 'trunk, extension…', optional: 'необязательно', search: 'Поиск', searchPlaceholder: 'логин, имя объекта…' },
  caption: 'Журнал аудита',
  empty: { title: 'По этому фильтру записей не найдено', body: 'Попробуйте изменить диапазон дат или фильтры.' },
  close: 'Закрыть',
  diff: { empty: 'Нет деталей изменения.', field: 'Поле', before: 'Было', after: 'Стало' },
};

export const en = {
  title: 'Audit log',
  action: {
    create: 'Created', update: 'Updated', delete: 'Deleted', login: 'Signed in', login_failed: 'Sign-in failed',
    restore: 'Restored', restart: 'Restarted', override: 'Temporarily changed', spy: 'Listen/join',
  },
  column: { at: 'Time', user: 'Who', action: 'Action', entity: 'Entity', label: 'What', ip: 'IP' },
  systemUser: 'system',
  viewDiffAriaLabel: 'View diff',
  filter: { from: 'From', to: 'To', action: 'Action', all: 'All', entity: 'Entity type', entityPlaceholder: 'trunk, extension…', optional: 'optional', search: 'Search', searchPlaceholder: 'login, entity name…' },
  caption: 'Audit log',
  empty: { title: 'No entries match this filter', body: 'Try changing the date range or filters.' },
  close: 'Close',
  diff: { empty: 'No change details.', field: 'Field', before: 'Before', after: 'After' },
};
