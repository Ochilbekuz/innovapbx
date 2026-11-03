// "parking" namespace — ParkingPage (parkovka). Qarang ../../replica/m9-freepbx-gaps-contract.md §A3.

export const uz = {
  title: 'Parkovka',
  readOnlyNotice: 'Sizda parkovka sozlamalarini oʻzgartirish ruxsati yoʻq — faqat koʻrish mumkin.',
  settingsTitle: 'Sozlamalar',
  form: {
    lotNumberLabel: 'Parkovka kodi', lotHint: 'Qoʻngʻiroqni shu kodga oʻtkazib parklash mumkin',
    firstSlotLabel: 'Boshlanish raqami', slotCountLabel: 'Joylar soni',
    timeoutLabel: 'Kutish vaqti (soniya)',
    onTimeoutLabel: 'Vaqt tugaganda', onTimeoutOrigin: 'Parklaganga qaytarish', onTimeoutTarget: 'Boshqa manzilga yuborish',
    timeoutTargetLabel: 'Vaqt tugaganda manzil',
    mohLabel: 'Kutish ohangi klassi (ixtiyoriy)', mohHint: 'Boʻsh qoldirsangiz — standart ohang ishlatiladi',
    saveButton: 'Saqlash',
  },
  toast: { saved: 'Sozlamalar saqlandi' },
  liveTitle: 'Parklangan qoʻngʻiroqlar',
  liveHint: 'Har 5 soniyada avtomatik yangilanadi',
  liveEmpty: 'Hozir hech kim parklanmagan',
  column: { slot: 'Joy', caller: 'Chaqiruvchi', parkedBy: 'Kim parklagan', elapsed: 'Oʻtgan vaqt', timeout: 'Vaqt tugashi' },
  secondsShort: '{{count}}s',
};

export const ru = {
  title: 'Парковка',
  readOnlyNotice: 'У вас нет прав на изменение настроек парковки — доступен только просмотр.',
  settingsTitle: 'Настройки',
  form: {
    lotNumberLabel: 'Код парковки', lotHint: 'Переведя звонок на этот код, его можно поставить на парковку',
    firstSlotLabel: 'Начальный номер', slotCountLabel: 'Количество мест',
    timeoutLabel: 'Время ожидания (сек)',
    onTimeoutLabel: 'При истечении времени', onTimeoutOrigin: 'Вернуть парковавшему', onTimeoutTarget: 'Отправить на другой адрес',
    timeoutTargetLabel: 'Адрес при истечении времени',
    mohLabel: 'Класс музыки ожидания (необязательно)', mohHint: 'Оставьте пустым для стандартной мелодии',
    saveButton: 'Сохранить',
  },
  toast: { saved: 'Настройки сохранены' },
  liveTitle: 'Запаркованные звонки',
  liveHint: 'Автообновление каждые 5 секунд',
  liveEmpty: 'Сейчас никто не на парковке',
  column: { slot: 'Место', caller: 'Звонящий', parkedBy: 'Кто поставил', elapsed: 'Прошло времени', timeout: 'До истечения' },
  secondsShort: '{{count}}с',
};

export const en = {
  title: 'Parking',
  readOnlyNotice: "You don't have permission to change parking settings — view only.",
  settingsTitle: 'Settings',
  form: {
    lotNumberLabel: 'Parking lot code', lotHint: 'Transferring a call to this code parks it',
    firstSlotLabel: 'First slot number', slotCountLabel: 'Number of slots',
    timeoutLabel: 'Timeout (seconds)',
    onTimeoutLabel: 'On timeout', onTimeoutOrigin: 'Return to the parker', onTimeoutTarget: 'Send to another destination',
    timeoutTargetLabel: 'Destination on timeout',
    mohLabel: 'Hold music class (optional)', mohHint: 'Leave blank to use the default tone',
    saveButton: 'Save',
  },
  toast: { saved: 'Settings saved' },
  liveTitle: 'Parked calls',
  liveHint: 'Refreshes automatically every 5 seconds',
  liveEmpty: 'No one is parked right now',
  column: { slot: 'Slot', caller: 'Caller', parkedBy: 'Parked by', elapsed: 'Elapsed', timeout: 'Until timeout' },
  secondsShort: '{{count}}s',
};
