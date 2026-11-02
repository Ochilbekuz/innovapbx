// "revisions" namespace — RevisionsPage (konfiguratsiya reviziyalari tarixi).

export const uz = {
  title: 'Reviziyalar tarixi',
  listAriaLabel: 'Reviziyalar roʻyxati',
  status: { applied: 'Qoʻllandi', rolledBack: 'Qaytarildi', applying: 'Qoʻllanmoqda' },
  loading: 'Yuklanmoqda…',
  errorBody: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',
  defaultSummary: 'Oʻzgarish',
  systemUser: 'tizim',
  revisionLabel: 'Reviziya r{{id}}',
  restore: 'Shu holatga qaytarish',
  compareWithPrevious: 'Avvalgisi bilan solishtirish',
  compareWithCurrent: 'Joriy holat bilan solishtirish',
  restoreModal: {
    title: '{{id}} holatiga qaytarish',
    body: 'Bu amal joriy sozlamalarni tanlangan reviziya holatiga qaytaradi va PBXʼga yangi reviziya sifatida qoʻllaydi. Davom etasizmi?',
    cancel: 'Bekor qilish',
    confirm: 'Qaytarish',
  },
  toast: {
    restoredTitle: 'Qaytarildi',
    restoreFailedTitle: 'Qaytarib boʻlmadi',
  },
  diff: {
    loading: 'Yuklanmoqda…',
    empty: 'Farq topilmadi — bu birinchi reviziya boʻlishi mumkin.',
  },
};

export const ru = {
  title: 'История ревизий',
  listAriaLabel: 'Список ревизий',
  status: { applied: 'Применена', rolledBack: 'Откат', applying: 'Применяется' },
  loading: 'Загрузка…',
  errorBody: 'Не удалось загрузить.',
  retry: 'Повторить',
  defaultSummary: 'Изменение',
  systemUser: 'система',
  revisionLabel: 'Ревизия r{{id}}',
  restore: 'Вернуться к этому состоянию',
  compareWithPrevious: 'Сравнить с предыдущей',
  compareWithCurrent: 'Сравнить с текущим состоянием',
  restoreModal: {
    title: 'Откат к {{id}}',
    body: 'Это действие вернёт текущие настройки к состоянию выбранной ревизии и применит их к PBX как новую ревизию. Продолжить?',
    cancel: 'Отмена',
    confirm: 'Откатить',
  },
  toast: {
    restoredTitle: 'Откат выполнен',
    restoreFailedTitle: 'Не удалось выполнить откат',
  },
  diff: {
    loading: 'Загрузка…',
    empty: 'Различий не найдено — возможно, это первая ревизия.',
  },
};

export const en = {
  title: 'Revision history',
  listAriaLabel: 'Revision list',
  status: { applied: 'Applied', rolledBack: 'Rolled back', applying: 'Applying' },
  loading: 'Loading…',
  errorBody: "Couldn't load.",
  retry: 'Retry',
  defaultSummary: 'Change',
  systemUser: 'system',
  revisionLabel: 'Revision r{{id}}',
  restore: 'Restore this state',
  compareWithPrevious: 'Compare with previous',
  compareWithCurrent: 'Compare with current state',
  restoreModal: {
    title: 'Restore to {{id}}',
    body: 'This will revert the current settings to the selected revision and apply it to the PBX as a new revision. Continue?',
    cancel: 'Cancel',
    confirm: 'Restore',
  },
  toast: {
    restoredTitle: 'Restored',
    restoreFailedTitle: 'Restore failed',
  },
  diff: {
    loading: 'Loading…',
    empty: 'No differences found — this might be the first revision.',
  },
};
