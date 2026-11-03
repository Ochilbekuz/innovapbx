// "misc" namespace — MiscPage (Boshqa manzillar / Maxsus kodlar). Qarang ../../replica/m9-freepbx-gaps-contract.md §A2.

export const uz = {
  title: 'Maxsus manzillar',
  readOnlyNotice: 'Sizda bu boʻlimni boshqarish ruxsati yoʻq — faqat koʻrish mumkin.',
  tabs: { destinations: 'Manzillar', applications: 'Maxsus kodlar' },
  tabsAriaLabel: 'Maxsus manzillar boʻlimlari',
  cancel: 'Bekor qilish', delete: 'Oʻchirish', save: 'Saqlash', add: 'Qoʻshish',
  destinations: {
    column: { name: 'Nom', dial: 'Terish' },
    caption: 'Boshqa manzillar',
    empty: { title: 'Hali manzil yoʻq', body: 'Boshqa manzil — ichki raqamlar jadvalidan tashqari terish kodiga yoʻnaltiradi (masalan faks).', action: 'Manzil qoʻshish' },
    newItem: 'Yangi manzil',
    toast: { added: 'Manzil qoʻshildi', saved: 'Manzil saqlandi', deleted: '{{name}} oʻchirildi', deleteFailed: 'Oʻchirib boʻlmadi' },
    deleteModal: { title: '{{name}}ni oʻchirish', body: '«{{name}}» butunlay oʻchiriladi.', usagePrefix: '«{{name}}» hali ishlatilmoqda — avval ulardan olib tashlang:' },
    editAriaLabel: '{{name}}ni tahrirlash', deleteAriaLabel: '{{name}}ni oʻchirish',
    form: {
      newTitle: 'Yangi manzil', editTitle: '{{name}}ni tahrirlash',
      nameLabel: 'Nom', dialLabel: 'Terish kodi', dialHint: 'Masalan: 0022 yoki boshqa ichki raqamlar toʻqnashmaydigan kod',
    },
  },
  applications: {
    column: { name: 'Nom', code: 'Kod', target: 'Manzil', enabled: 'Yoqilgan' },
    caption: 'Maxsus kodlar',
    empty: { title: 'Hali maxsus kod yoʻq', body: 'Maxsus kod (*501 kabi) bosilsa — belgilangan manzilga toʻgʻridan-toʻgʻri ulanadi.', action: 'Kod qoʻshish' },
    newItem: 'Yangi kod',
    toast: { added: 'Kod qoʻshildi', saved: 'Kod saqlandi', deleted: '{{name}} oʻchirildi', deleteFailed: 'Oʻchirib boʻlmadi' },
    deleteModal: { title: '{{name}}ni oʻchirish', body: '«{{name}}» butunlay oʻchiriladi.' },
    editAriaLabel: '{{name}}ni tahrirlash', deleteAriaLabel: '{{name}}ni oʻchirish',
    form: {
      newTitle: 'Yangi maxsus kod', editTitle: '{{name}}ni tahrirlash',
      nameLabel: 'Nom', codeLabel: 'Kod', codeHint: 'Masalan: *501 — yulduzcha bilan boshlanadi',
      targetLabel: 'Manzil', enabledLabel: 'Yoqilgan',
    },
  },
};

export const ru = {
  title: 'Прочие маршруты',
  readOnlyNotice: 'У вас нет прав на управление этим разделом — доступен только просмотр.',
  tabs: { destinations: 'Адреса', applications: 'Спец. коды' },
  tabsAriaLabel: 'Разделы прочих маршрутов',
  cancel: 'Отмена', delete: 'Удалить', save: 'Сохранить', add: 'Добавить',
  destinations: {
    column: { name: 'Имя', dial: 'Набор' },
    caption: 'Прочие адреса',
    empty: { title: 'Адресов пока нет', body: 'Прочий адрес направляет на код набора вне таблицы внутренних номеров (например, факс).', action: 'Добавить адрес' },
    newItem: 'Новый адрес',
    toast: { added: 'Адрес добавлен', saved: 'Адрес сохранён', deleted: '{{name}} удалён', deleteFailed: 'Не удалось удалить' },
    deleteModal: { title: 'Удаление {{name}}', body: '«{{name}}» будет удалён полностью.', usagePrefix: '«{{name}}» всё ещё используется — сначала удалите отсюда:' },
    editAriaLabel: 'Редактировать {{name}}', deleteAriaLabel: 'Удалить {{name}}',
    form: {
      newTitle: 'Новый адрес', editTitle: 'Редактирование {{name}}',
      nameLabel: 'Имя', dialLabel: 'Код набора', dialHint: 'Например: 0022 или другой код, не пересекающийся с номерами',
    },
  },
  applications: {
    column: { name: 'Имя', code: 'Код', target: 'Адрес', enabled: 'Включён' },
    caption: 'Спец. коды',
    empty: { title: 'Кодов пока нет', body: 'Спец. код (например *501) при наборе сразу соединяет с указанным адресом.', action: 'Добавить код' },
    newItem: 'Новый код',
    toast: { added: 'Код добавлен', saved: 'Код сохранён', deleted: '{{name}} удалён', deleteFailed: 'Не удалось удалить' },
    deleteModal: { title: 'Удаление {{name}}', body: '«{{name}}» будет удалён полностью.' },
    editAriaLabel: 'Редактировать {{name}}', deleteAriaLabel: 'Удалить {{name}}',
    form: {
      newTitle: 'Новый спец. код', editTitle: 'Редактирование {{name}}',
      nameLabel: 'Имя', codeLabel: 'Код', codeHint: 'Например: *501 — начинается со звёздочки',
      targetLabel: 'Адрес', enabledLabel: 'Включён',
    },
  },
};

export const en = {
  title: 'Misc destinations',
  readOnlyNotice: "You don't have permission to manage this section — view only.",
  tabs: { destinations: 'Destinations', applications: 'Feature codes' },
  tabsAriaLabel: 'Misc destination sections',
  cancel: 'Cancel', delete: 'Delete', save: 'Save', add: 'Add',
  destinations: {
    column: { name: 'Name', dial: 'Dial' },
    caption: 'Misc destinations',
    empty: { title: 'No destinations yet', body: 'A misc destination routes to a dial code outside the extensions table (e.g. a fax line).', action: 'Add destination' },
    newItem: 'New destination',
    toast: { added: 'Destination added', saved: 'Destination saved', deleted: '{{name}} deleted', deleteFailed: 'Could not delete' },
    deleteModal: { title: 'Delete {{name}}', body: '"{{name}}" will be permanently deleted.', usagePrefix: '"{{name}}" is still in use — remove it from these first:' },
    editAriaLabel: 'Edit {{name}}', deleteAriaLabel: 'Delete {{name}}',
    form: {
      newTitle: 'New destination', editTitle: 'Edit {{name}}',
      nameLabel: 'Name', dialLabel: 'Dial code', dialHint: 'E.g. 0022 — a code that does not clash with extension numbers',
    },
  },
  applications: {
    column: { name: 'Name', code: 'Code', target: 'Destination', enabled: 'Enabled' },
    caption: 'Feature codes',
    empty: { title: 'No feature codes yet', body: 'A feature code (like *501) connects directly to the assigned destination when dialed.', action: 'Add code' },
    newItem: 'New code',
    toast: { added: 'Code added', saved: 'Code saved', deleted: '{{name}} deleted', deleteFailed: 'Could not delete' },
    deleteModal: { title: 'Delete {{name}}', body: '"{{name}}" will be permanently deleted.' },
    editAriaLabel: 'Edit {{name}}', deleteAriaLabel: 'Delete {{name}}',
    form: {
      newTitle: 'New feature code', editTitle: 'Edit {{name}}',
      nameLabel: 'Name', codeLabel: 'Code', codeHint: 'E.g. *501 — starts with a star',
      targetLabel: 'Destination', enabledLabel: 'Enabled',
    },
  },
};
