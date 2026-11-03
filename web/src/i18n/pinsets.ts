// "pinsets" namespace — PinSetsPage (PIN toʻplamlari). Qarang ../../replica/m9-freepbx-gaps-contract.md §B1.

export const uz = {
  title: 'PIN toʻplamlari',
  readOnlyNotice: 'Sizda PIN toʻplamlarini boshqarish ruxsati yoʻq — faqat koʻrish mumkin.',
  column: { name: 'Nom', recordInCdr: 'CDRda yozilsin', pinCount: 'PIN soni', usedBy: 'Qayerda ishlatiladi' },
  caption: 'PIN toʻplamlari',
  empty: { title: 'Hali PIN toʻplami yoʻq', body: 'PIN toʻplami — chiquvchi marshrutda qoʻngʻiroq qilishdan oldin kod soʻraydi.', action: 'Toʻplam qoʻshish' },
  newSet: 'Yangi toʻplam',
  toast: { added: 'Toʻplam qoʻshildi', saved: 'Toʻplam saqlandi', deleted: '{{name}} oʻchirildi', deleteFailed: 'Oʻchirib boʻlmadi', pinsAdded: '{{count}} ta PIN qoʻshildi' },
  deleteModal: { title: '{{name}}ni oʻchirish', body: '«{{name}}» va undagi barcha PINlar butunlay oʻchiriladi.', usagePrefix: '«{{name}}» hali ishlatilmoqda — avval ulardan olib tashlang:' },
  cancel: 'Bekor qilish', delete: 'Oʻchirish', save: 'Saqlash', add: 'Qoʻshish', close: 'Yopish',
  editAriaLabel: '{{name}}ni tahrirlash', deleteAriaLabel: '{{name}}ni oʻchirish', openPinsAriaLabel: '{{name}}: PINlarni boshqarish',
  form: {
    newTitle: 'Yangi PIN toʻplami', editTitle: '{{name}}ni tahrirlash',
    nameLabel: 'Nom', recordInCdrLabel: 'CDRda yozilsin', recordInCdrDesc: 'Yoqilgan boʻlsa — qaysi PIN ishlatilgani qoʻngʻiroqlar tarixida saqlanadi',
  },
  pinsDrawer: {
    title: '{{name}}: PINlar',
    pinColumn: 'Yorliq', removeAriaLabel: '{{label}} PINini olib tashlash',
    empty: 'Bu toʻplamda hali PIN yoʻq',
    addLabel: 'Yangi PINlar qoʻshish', addHint: 'Har bir qatorga: pin;yorliq — masalan 1234;Direktor',
    addPlaceholder: '1234;Direktor\n5678;Buxgalteriya',
    addButton: 'Qoʻshish',
    pinFormatError: "{{row}}-qator notoʻgʻri — format «PIN;yorliq», PIN 4-12 raqam boʻlishi kerak",
    pinTakenError: '{{pin}} — bu PIN allaqachon band',
  },
};

export const ru = {
  title: 'Наборы PIN',
  readOnlyNotice: 'У вас нет прав на управление наборами PIN — доступен только просмотр.',
  column: { name: 'Имя', recordInCdr: 'Запись в CDR', pinCount: 'Кол-во PIN', usedBy: 'Где используется' },
  caption: 'Наборы PIN',
  empty: { title: 'Наборов PIN пока нет', body: 'Набор PIN запрашивает код перед исходящим звонком на маршруте.', action: 'Добавить набор' },
  newSet: 'Новый набор',
  toast: { added: 'Набор добавлен', saved: 'Набор сохранён', deleted: '{{name}} удалён', deleteFailed: 'Не удалось удалить', pinsAdded: 'Добавлено {{count}} PIN' },
  deleteModal: { title: 'Удаление {{name}}', body: '«{{name}}» и все его PIN будут удалены полностью.', usagePrefix: '«{{name}}» всё ещё используется — сначала удалите отсюда:' },
  cancel: 'Отмена', delete: 'Удалить', save: 'Сохранить', add: 'Добавить', close: 'Закрыть',
  editAriaLabel: 'Редактировать {{name}}', deleteAriaLabel: 'Удалить {{name}}', openPinsAriaLabel: '{{name}}: управление PIN',
  form: {
    newTitle: 'Новый набор PIN', editTitle: 'Редактирование {{name}}',
    nameLabel: 'Имя', recordInCdrLabel: 'Запись в CDR', recordInCdrDesc: 'Если включено — использованный PIN сохраняется в истории звонков',
  },
  pinsDrawer: {
    title: '{{name}}: PIN',
    pinColumn: 'Метка', removeAriaLabel: 'Удалить PIN {{label}}',
    empty: 'В этом наборе пока нет PIN',
    addLabel: 'Добавить новые PIN', addHint: 'По строке: pin;метка — например 1234;Директор',
    addPlaceholder: '1234;Директор\n5678;Бухгалтерия',
    addButton: 'Добавить',
    pinFormatError: 'Строка {{row}} неверна — формат «PIN;метка», PIN из 4–12 цифр',
    pinTakenError: '{{pin}} — этот PIN уже занят',
  },
};

export const en = {
  title: 'PIN sets',
  readOnlyNotice: "You don't have permission to manage PIN sets — view only.",
  column: { name: 'Name', recordInCdr: 'Record in CDR', pinCount: 'PIN count', usedBy: 'Used by' },
  caption: 'PIN sets',
  empty: { title: 'No PIN sets yet', body: 'A PIN set asks for a code before placing a call on an outbound route.', action: 'Add set' },
  newSet: 'New set',
  toast: { added: 'Set added', saved: 'Set saved', deleted: '{{name}} deleted', deleteFailed: 'Could not delete', pinsAdded: '{{count}} PIN(s) added' },
  deleteModal: { title: 'Delete {{name}}', body: '"{{name}}" and all its PINs will be permanently deleted.', usagePrefix: '"{{name}}" is still in use — remove it from these first:' },
  cancel: 'Cancel', delete: 'Delete', save: 'Save', add: 'Add', close: 'Close',
  editAriaLabel: 'Edit {{name}}', deleteAriaLabel: 'Delete {{name}}', openPinsAriaLabel: '{{name}}: manage PINs',
  form: {
    newTitle: 'New PIN set', editTitle: 'Edit {{name}}',
    nameLabel: 'Name', recordInCdrLabel: 'Record in CDR', recordInCdrDesc: 'When on, the PIN used is stored in call history',
  },
  pinsDrawer: {
    title: '{{name}}: PINs',
    pinColumn: 'Label', removeAriaLabel: 'Remove PIN {{label}}',
    empty: 'This set has no PINs yet',
    addLabel: 'Add new PINs', addHint: 'One per line: pin;label — e.g. 1234;Manager',
    addPlaceholder: '1234;Manager\n5678;Accounting',
    addButton: 'Add',
    pinFormatError: 'Row {{row}} is invalid — format is "PIN;label", PIN must be 4-12 digits',
    pinTakenError: '{{pin}} — this PIN is already taken',
  },
};
