// "blacklist" namespace — BlacklistPage (S27, qora roʻyxat). Qarang ../../replica/m2a-contract.md §5.

export const uz = {
  title: 'Qora roʻyxat',
  readOnlyNotice: 'Sizda qora roʻyxatni boshqarish ruxsati yoʻq — faqat koʻrish mumkin.',
  caption: 'Qora roʻyxat',
  searchPlaceholder: 'Raqam yoki sabab boʻyicha qidirish…',
  column: { number: 'Raqam', reason: 'Sabab', createdAt: 'Qoʻshilgan' },
  anonymousLabel: 'Yashirin raqam',
  anonymousToggle: { label: 'Yashirin/anonim raqamlarni bloklash', desc: 'Callerʼid koʻrsatilmagan barcha qoʻngʻiroqlar rad etiladi' },
  deleteAriaLabel: '{{number}}ni qora roʻyxatdan olib tashlash',
  empty: { title: 'Qora roʻyxat boʻsh', body: 'Bu yerga qoʻshilgan raqamlardan qoʻngʻiroqlar avtomatik rad etiladi.' },
  addForm: { numberLabel: 'Raqam', numberPlaceholder: '+998901234567', reasonLabel: 'Sabab', reasonAside: 'ixtiyoriy', reasonPlaceholder: 'Masalan: spam', add: 'Qoʻshish' },
  toast: { added: '{{number}} qora roʻyxatga qoʻshildi', deleted: '{{number}} olib tashlandi', addFailed: 'Qoʻshib boʻlmadi', deleteFailed: 'Olib tashlab boʻlmadi' },
  deleteModal: { title: '{{number}}ni olib tashlash', body: '«{{number}}» qora roʻyxatdan olib tashlanadi — bu raqamdan qoʻngʻiroqlar yana qabul qilinadi.' },
  cancel: 'Bekor qilish', delete: 'Olib tashlash',
  error: { badNumber: 'Raqam notoʻgʻri — 3-15 ta raqam', exists: 'Bu raqam allaqachon qora roʻyxatda' },
};

export const ru = {
  title: 'Чёрный список',
  readOnlyNotice: 'У вас нет прав на управление чёрным списком — доступен только просмотр.',
  caption: 'Чёрный список',
  searchPlaceholder: 'Поиск по номеру или причине…',
  column: { number: 'Номер', reason: 'Причина', createdAt: 'Добавлен' },
  anonymousLabel: 'Скрытый номер',
  anonymousToggle: { label: 'Блокировать скрытые/анонимные номера', desc: 'Все звонки без показанного CallerID будут отклонены' },
  deleteAriaLabel: 'Удалить {{number}} из чёрного списка',
  empty: { title: 'Чёрный список пуст', body: 'Звонки с номеров из этого списка будут автоматически отклоняться.' },
  addForm: { numberLabel: 'Номер', numberPlaceholder: '+998901234567', reasonLabel: 'Причина', reasonAside: 'необязательно', reasonPlaceholder: 'Например: спам', add: 'Добавить' },
  toast: { added: '{{number}} добавлен в чёрный список', deleted: '{{number}} удалён', addFailed: 'Не удалось добавить', deleteFailed: 'Не удалось удалить' },
  deleteModal: { title: 'Удаление {{number}}', body: '«{{number}}» будет удалён из чёрного списка — звонки с этого номера снова будут приниматься.' },
  cancel: 'Отмена', delete: 'Удалить',
  error: { badNumber: 'Неверный номер — 3-15 цифр', exists: 'Этот номер уже в чёрном списке' },
};

export const en = {
  title: 'Blacklist',
  readOnlyNotice: "You don't have permission to manage the blacklist — view only.",
  caption: 'Blacklist',
  searchPlaceholder: 'Search by number or reason…',
  column: { number: 'Number', reason: 'Reason', createdAt: 'Added' },
  anonymousLabel: 'Hidden number',
  anonymousToggle: { label: 'Block hidden/anonymous numbers', desc: 'Any call without a shown caller ID will be rejected' },
  deleteAriaLabel: 'Remove {{number}} from the blacklist',
  empty: { title: 'The blacklist is empty', body: 'Calls from numbers added here will be rejected automatically.' },
  addForm: { numberLabel: 'Number', numberPlaceholder: '+998901234567', reasonLabel: 'Reason', reasonAside: 'optional', reasonPlaceholder: 'E.g. spam', add: 'Add' },
  toast: { added: '{{number}} added to the blacklist', deleted: '{{number}} removed', addFailed: 'Could not add', deleteFailed: 'Could not remove' },
  deleteModal: { title: 'Remove {{number}}', body: '"{{number}}" will be removed from the blacklist — calls from this number will be accepted again.' },
  cancel: 'Cancel', delete: 'Remove',
  error: { badNumber: 'Invalid number — 3-15 digits', exists: 'This number is already blacklisted' },
};
