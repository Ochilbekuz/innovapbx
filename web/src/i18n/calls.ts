// "calls" namespace — CallsPage (qoʻngʻiroqlar tarixi).

export const uz = {
  title: 'Qoʻngʻiroqlar tarixi',
  direction: { in: 'Kiruvchi', out: 'Chiquvchi', internal: 'Ichki' },
  disposition: { answered: 'Javob berildi', no_answer: 'Javobsiz', busy: 'Band', failed: 'Muvaffaqiyatsiz' },
  column: { startedAt: 'Vaqt', direction: 'Yoʻnalish', src: 'Kimdan', dst: 'Kimga', did: 'DID', disposition: 'Natija', duration: 'Davomiyligi', trunk: 'Trunk', recording: 'Yozuv', actions: '' },
  filter: { from: 'Boshlanishi', to: 'Tugashi', direction: 'Yoʻnalish', all: 'Hammasi' },
  caption: 'Qoʻngʻiroqlar tarixi',
  empty: { title: 'Bu oraliqda qoʻngʻiroq topilmadi', body: 'Sana oraligʻini yoki yoʻnalishni oʻzgartirib koʻring.' },
  block: {
    action: 'Bloklash', ariaLabel: '{{number}}ni qora roʻyxatga qoʻshish',
    modalTitle: '{{number}}ni qora roʻyxatga qoʻshish',
    numberLabel: 'Raqam', reasonLabel: 'Sabab', reasonAside: 'ixtiyoriy', reasonPlaceholder: 'Masalan: spam',
    add: 'Qoʻshish', cancel: 'Bekor qilish',
    toast: { added: '{{number}} qora roʻyxatga qoʻshildi', failed: 'Qoʻshib boʻlmadi' },
  },
};

export const ru = {
  title: 'История звонков',
  direction: { in: 'Входящий', out: 'Исходящий', internal: 'Внутренний' },
  disposition: { answered: 'Отвечено', no_answer: 'Без ответа', busy: 'Занято', failed: 'Неуспешно' },
  column: { startedAt: 'Время', direction: 'Направление', src: 'От кого', dst: 'Кому', did: 'DID', disposition: 'Результат', duration: 'Длительность', trunk: 'Транк', recording: 'Запись', actions: '' },
  filter: { from: 'Начало', to: 'Конец', direction: 'Направление', all: 'Все' },
  caption: 'История звонков',
  empty: { title: 'За этот период звонков не найдено', body: 'Попробуйте изменить диапазон дат или направление.' },
  block: {
    action: 'Блокировать', ariaLabel: 'Добавить {{number}} в чёрный список',
    modalTitle: 'Добавить {{number}} в чёрный список',
    numberLabel: 'Номер', reasonLabel: 'Причина', reasonAside: 'необязательно', reasonPlaceholder: 'Например: спам',
    add: 'Добавить', cancel: 'Отмена',
    toast: { added: '{{number}} добавлен в чёрный список', failed: 'Не удалось добавить' },
  },
};

export const en = {
  title: 'Call history',
  direction: { in: 'Inbound', out: 'Outbound', internal: 'Internal' },
  disposition: { answered: 'Answered', no_answer: 'No answer', busy: 'Busy', failed: 'Failed' },
  column: { startedAt: 'Time', direction: 'Direction', src: 'From', dst: 'To', did: 'DID', disposition: 'Outcome', duration: 'Duration', trunk: 'Trunk', recording: 'Recording', actions: '' },
  filter: { from: 'From', to: 'To', direction: 'Direction', all: 'All' },
  caption: 'Call history',
  empty: { title: 'No calls found in this range', body: 'Try changing the date range or direction.' },
  block: {
    action: 'Block', ariaLabel: 'Add {{number}} to the blacklist',
    modalTitle: 'Add {{number}} to the blacklist',
    numberLabel: 'Number', reasonLabel: 'Reason', reasonAside: 'optional', reasonPlaceholder: 'E.g. spam',
    add: 'Add', cancel: 'Cancel',
    toast: { added: '{{number}} added to the blacklist', failed: 'Could not add' },
  },
};
