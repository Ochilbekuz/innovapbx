// "paging" namespace — PagingPage (Paging / Intercom guruhlari). Qarang ../../replica/m9-freepbx-gaps-contract.md §A4.

export const uz = {
  title: 'Paging / Intercom',
  readOnlyNotice: 'Sizda paging guruhlarini boshqarish ruxsati yoʻq — faqat koʻrish mumkin.',
  column: { name: 'Nom', number: 'Raqam', members: 'Aʼzolar', duplex: 'Ikki tomonlama' },
  caption: 'Paging guruhlari',
  empty: { title: 'Hali paging guruhi yoʻq', body: 'Paging guruhi — bir vaqtning oʻzida bir nechta ichki raqamga ovozli xabar eshittiradi.', action: 'Guruh qoʻshish' },
  newGroup: 'Yangi guruh',
  toast: { added: 'Guruh qoʻshildi', saved: 'Guruh saqlandi', deleted: '{{name}} oʻchirildi', deleteFailed: 'Oʻchirib boʻlmadi' },
  deleteModal: { title: '{{name}}ni oʻchirish', body: '«{{name}}» butunlay oʻchiriladi.' },
  cancel: 'Bekor qilish', delete: 'Oʻchirish', save: 'Saqlash', add: 'Qoʻshish',
  editAriaLabel: '{{name}}ni tahrirlash', deleteAriaLabel: '{{name}}ni oʻchirish',
  form: {
    newTitle: 'Yangi paging guruhi', editTitle: '{{name}}ni tahrirlash',
    nameLabel: 'Nom', numberLabel: 'Raqam', numberHint: 'Shu raqam terilsa — barcha aʼzolarga bir vaqtda ulanadi',
    duplexLabel: 'Ikki tomonlama', duplexDesc: 'Yoqilgan boʻlsa — aʼzolar ham javob berib gapirishi mumkin',
    skipBusyLabel: 'Band boʻlsa oʻtkazib yuborish', skipBusyDesc: 'Band aʼzoga xabar yuborilmaydi',
    beepLabel: 'Signal ohangi', beepDesc: 'Xabar boshlanishidan oldin qisqa signal eshittiriladi',
    membersLabel: 'Aʼzolar', membersHint: 'Xabar eshittiriladigan ichki raqamlar',
    memberCheckboxAriaLabel: '{{number}} {{name}}',
  },
};

export const ru = {
  title: 'Пейджинг / Интерком',
  readOnlyNotice: 'У вас нет прав на управление группами пейджинга — доступен только просмотр.',
  column: { name: 'Имя', number: 'Номер', members: 'Участники', duplex: 'Двусторонний' },
  caption: 'Группы пейджинга',
  empty: { title: 'Групп пейджинга пока нет', body: 'Группа пейджинга одновременно транслирует сообщение на несколько внутренних номеров.', action: 'Добавить группу' },
  newGroup: 'Новая группа',
  toast: { added: 'Группа добавлена', saved: 'Группа сохранена', deleted: '{{name}} удалена', deleteFailed: 'Не удалось удалить' },
  deleteModal: { title: 'Удаление {{name}}', body: '«{{name}}» будет удалена полностью.' },
  cancel: 'Отмена', delete: 'Удалить', save: 'Сохранить', add: 'Добавить',
  editAriaLabel: 'Редактировать {{name}}', deleteAriaLabel: 'Удалить {{name}}',
  form: {
    newTitle: 'Новая группа пейджинга', editTitle: 'Редактирование {{name}}',
    nameLabel: 'Имя', numberLabel: 'Номер', numberHint: 'При наборе этого номера соединение идёт со всеми участниками одновременно',
    duplexLabel: 'Двусторонний', duplexDesc: 'Если включено — участники тоже могут отвечать и говорить',
    skipBusyLabel: 'Пропускать занятых', skipBusyDesc: 'Занятому участнику сообщение не отправляется',
    beepLabel: 'Сигнал', beepDesc: 'Перед сообщением проигрывается короткий сигнал',
    membersLabel: 'Участники', membersHint: 'Внутренние номера, на которые транслируется сообщение',
    memberCheckboxAriaLabel: '{{number}} {{name}}',
  },
};

export const en = {
  title: 'Paging / Intercom',
  readOnlyNotice: "You don't have permission to manage paging groups — view only.",
  column: { name: 'Name', number: 'Number', members: 'Members', duplex: 'Two-way' },
  caption: 'Paging groups',
  empty: { title: 'No paging groups yet', body: 'A paging group broadcasts an announcement to several extensions at once.', action: 'Add group' },
  newGroup: 'New group',
  toast: { added: 'Group added', saved: 'Group saved', deleted: '{{name}} deleted', deleteFailed: 'Could not delete' },
  deleteModal: { title: 'Delete {{name}}', body: '"{{name}}" will be permanently deleted.' },
  cancel: 'Cancel', delete: 'Delete', save: 'Save', add: 'Add',
  editAriaLabel: 'Edit {{name}}', deleteAriaLabel: 'Delete {{name}}',
  form: {
    newTitle: 'New paging group', editTitle: 'Edit {{name}}',
    nameLabel: 'Name', numberLabel: 'Number', numberHint: 'Dialing this number connects to all members at once',
    duplexLabel: 'Two-way', duplexDesc: 'When on, members can answer back and speak',
    skipBusyLabel: 'Skip busy members', skipBusyDesc: 'A busy member will not receive the announcement',
    beepLabel: 'Beep', beepDesc: 'A short tone plays before the announcement starts',
    membersLabel: 'Members', membersHint: 'Extensions that will hear the announcement',
    memberCheckboxAriaLabel: '{{number}} {{name}}',
  },
};
