// "migration" namespace — Ko'chirish sahifasi (S36, /settings/migration): FreePBX'dan import.
// Qarang ../../replica/m5a-contract.md.

export const uz = {
  title: "Ko'chirish",
  readOnlyBanner: "Faqat koʻrish — bu boʻlimni oʻzgartirish uchun maʼmur huquqi kerak.",
  cancel: 'Bekor qilish', back: 'Orqaga', close: 'Yopish',

  steps: { source: 'Manba', analyze: 'Tahlil', review: "Ko'rib chiqish", apply: "Qo'llash", result: 'Natija' },

  source: {
    title: 'FreePBX serveridan manba tanlang',
    intro: "Eksport toʻplamini yuklang yoki SSH orqali avtomatik olib keling — ikkisi ham bir xil tahlilga oʻtadi.",
    uploadTab: "Toʻplam yuklash",
    sshTab: 'SSH orqali olish',
    exportScript: {
      title: 'Eksport skripti',
      body: "FreePBX serverda root sifatida ishga tushiring (faqat oʻqiydi, hech narsani oʻzgartirmaydi):",
      downloadButton: 'Skriptni yuklab olish',
      command: 'bash innova-fpbx-export.sh',
      copyButton: 'Nusxalash',
      copied: 'Nusxalandi.',
    },
    upload: {
      label: "Toʻplam fayli (fpbx-export-*.tar.gz)",
      hint: "SIP parollari toʻplamda bor — import tugagach fayl serverdan oʻchiriladi.",
      invalidFile: '.tar.gz yoki .tgz fayl tanlang.',
      submit: 'Yuklash va tahlilga oʻtish',
      uploading: 'Yuklanmoqda…',
      failedToast: "Toʻplam yuklanmadi: {{error}}",
    },
    ssh: {
      host: 'Host', port: 'Port', username: 'Foydalanuvchi',
      password: 'Parol', privateKey: 'Shaxsiy kalit (ixtiyoriy, parol oʻrniga)',
      test: 'Ulanishni tekshirish', testing: 'Tekshirilmoqda…',
      testOk: 'Ulanish muvaffaqiyatli — endi olib kelishni boshlang.',
      testFailed: 'Ulanmadi: {{error}}',
      fetch: 'Olib kelish va tahlilga oʻtish', fetching: 'Olib kelinmoqda…',
      fetchFailedToast: "Olib kelish muvaffaqiyatsiz: {{error}}",
      fingerprintModal: {
        title: 'Server barmoq izini tasdiqlang',
        body: "Birinchi marta ulanmoqdasiz. Barmoq izi: {{fp}} — toʻgʻri ekanini bilsangiz tasdiqlang.",
        cancel: 'Bekor qilish', confirm: 'Tasdiqlab olib kelish',
      },
    },
  },

  analyze: {
    title: "Toʻplam tahlil qilinmoqda",
    startButton: 'Tahlilni boshlash', starting: 'Boshlanmoqda…',
    autoStartHint: "Tahlil paytida Innova'da hech narsa oʻzgarmaydi — faqat reja tuziladi.",
    progressLabel: 'Tahlil jarayoni',
  },

  review: {
    title: 'Reja',
    summaryTitle: 'Turlar boʻyicha',
    conflictsBadge: '{{n}} toʻqnashuv',
    table: {
      caption: "Ko'chirish rejasi elementlari",
      column: { kind: 'Turi', name: 'Nomi', number: 'Raqami', action: 'Amal', reason: 'Sabab' },
      filterKindPlaceholder: 'Barcha turlar',
      filterActionPlaceholder: 'Barcha amallar',
      skipAction: "O'tkazib yuborish", replaceAction: 'Almashtirish', createAction: 'Yaratish',
      notReplaceable: "Qoʻlda yaratilgan obyektni almashtirib boʻlmaydi — faqat oʻtkazib yuborish.",
      patchFailedToast: 'Amal bajarilmadi: {{error}}',
    },
    weakSecrets: {
      title: 'Zaif sirlar',
      body: '{{n}} ichki raqam sirlari zaif (12 belgidan kam) — telefonlar qayta sozlanmasdan ishlashi uchun sukut boʻyicha oʻzgarmay koʻchadi.',
      rotateLabel: 'Zaif sirlarni yangi tasodifiy parolga almashtirish',
      rotateHint: "Yoqilsa, parol provizioning orqali telefonning oʻziga yetkaziladi.",
    },
    warningsTitle: 'Ogohlantirishlar',
    ignoredTitle: "Eʼtiborsiz qoldirilgan qatorlar",
    continueButton: "Qoʻllashga oʻtish",
  },

  apply: {
    title: "Ko'chirishni qoʻllash",
    preImportNotice: "Qoʻllashdan oldin joriy holat avtomatik zaxiralanadi — muvaffaqiyatsiz boʻlsa hech narsa oʻzgarmaydi.",
    backupNotReady: {
      body: "Zaxira paroli oʻrnatilmagan — import oldidan avtomatik zaxira olish uchun avval parol kerak.",
      link: 'Zaxira sozlamalariga oʻtish',
    },
    confirmLabel: 'Tasdiqlash uchun quyidagi soʻzni yozing',
    confirmPlaceholder: 'KOCHIRISH',
    submit: "Qoʻllash", submitting: "Qoʻllanmoqda…",
    progressLabel: "Qoʻllash jarayoni",
    planStale: {
      body: "Ish boshlanishidan oldin Innova'da holat oʻzgargan — qayta tahlil qilish kerak.",
      reanalyze: 'Qayta tahlil qilish',
    },
    jobRunning: "Hozir boshqa zaxira/koʻchirish ishi ketmoqda — tugashini kuting.",
  },

  result: {
    titleOk: "Koʻchirish yakunlandi",
    titleFailed: "Koʻchirish muvaffaqiyatsiz",
    created: 'Yaratildi', skipped: "Oʻtkazib yuborildi", warnings: 'Ogohlantirishlar',
    reportButton: 'Hisobotni yuklab olish (CSV)',
    rollbackLink: "Bekor qilish — import oldidagi zaxirani tiklash",
    newImportButton: 'Yangi import boshlash',
    errorLabel: 'Xato',
  },

  history: {
    title: "Koʻchirish tarixi",
    caption: "Oldingi koʻchirish ishlari",
    column: { created: 'Yaratilgan', source: 'Manba', status: 'Holat', summary: 'Natija', actions: '' },
    empty: { title: "Hali koʻchirish qilinmagan", body: 'Yuqoridagi sehrgar bilan birinchi importni boshlang.' },
    deleteConfirm: { title: "Toʻplamni oʻchirasizmi?", body: "Toʻplam fayli diskdan oʻchiriladi — import natijasi saqlanib qoladi." },
    deletedToast: "Toʻplam fayli oʻchirildi.",
    openButton: 'Ochish',
  },

  kind: {
    audio: 'Audio', moh: 'Kutish musiqasi', time_group: 'Vaqt guruhi', holiday: 'Bayram', extension: 'Ichki raqam',
    voicemail: 'Ovozli pochta', trunk: 'Trunk', ring_group: 'Qabul guruhi', queue: 'Navbat', conference: 'Konferensiya',
    announcement: 'Eʼlon', ivr: 'IVR', time_condition: 'Vaqt sharti', inbound_route: 'Kiruvchi marshrut',
    outbound_route: 'Chiquvchi marshrut', blacklist: "Qora roʻyxat", feature_code: 'Xususiyat kodi',
  },
  statusLabel: {
    uploaded: 'Yuklandi', analyzing: 'Tahlil qilinmoqda', analyzed: 'Tahlil qilindi',
    applying: "Qoʻllanmoqda", ok: 'Tayyor', failed: 'Muvaffaqiyatsiz',
  },
  actionLabel: { create: 'Yaratiladi', skip: "Oʻtkazib yuboriladi", conflict: 'Toʻqnashuv', unsupported: "Qoʻllanmaydi" },
  sourceLabel: { upload: "Toʻplam", ssh: 'SSH' },
};

export const ru = {
  title: 'Перенос',
  readOnlyBanner: 'Только просмотр — для изменения этого раздела нужны права администратора.',
  cancel: 'Отмена', back: 'Назад', close: 'Закрыть',

  steps: { source: 'Источник', analyze: 'Анализ', review: 'Проверка', apply: 'Применение', result: 'Результат' },

  source: {
    title: 'Выберите источник на сервере FreePBX',
    intro: 'Загрузите экспортный архив или получите его автоматически по SSH — оба пути ведут к одному анализу.',
    uploadTab: 'Загрузка архива',
    sshTab: 'Через SSH',
    exportScript: {
      title: 'Скрипт экспорта',
      body: 'Запустите на сервере FreePBX от root (только читает, ничего не меняет):',
      downloadButton: 'Скачать скрипт',
      command: 'bash innova-fpbx-export.sh',
      copyButton: 'Скопировать',
      copied: 'Скопировано.',
    },
    upload: {
      label: 'Файл архива (fpbx-export-*.tar.gz)',
      hint: 'В архиве есть SIP-пароли — после импорта файл удаляется с сервера.',
      invalidFile: 'Выберите файл .tar.gz или .tgz.',
      submit: 'Загрузить и перейти к анализу',
      uploading: 'Загружается…',
      failedToast: 'Не удалось загрузить архив: {{error}}',
    },
    ssh: {
      host: 'Хост', port: 'Порт', username: 'Пользователь',
      password: 'Пароль', privateKey: 'Приватный ключ (не обязателен, вместо пароля)',
      test: 'Проверить соединение', testing: 'Проверяется…',
      testOk: 'Соединение успешно — теперь начните получение.',
      testFailed: 'Не удалось подключиться: {{error}}',
      fetch: 'Получить и перейти к анализу', fetching: 'Получение…',
      fetchFailedToast: 'Не удалось получить архив: {{error}}',
      fingerprintModal: {
        title: 'Подтвердите отпечаток сервера',
        body: 'Вы подключаетесь впервые. Отпечаток: {{fp}} — подтвердите, если он верный.',
        cancel: 'Отмена', confirm: 'Подтвердить и получить',
      },
    },
  },

  analyze: {
    title: 'Анализ архива',
    startButton: 'Начать анализ', starting: 'Запускается…',
    autoStartHint: 'Во время анализа в Innova ничего не меняется — только строится план.',
    progressLabel: 'Ход анализа',
  },

  review: {
    title: 'План',
    summaryTitle: 'По типам',
    conflictsBadge: '{{n}} конфликт(ов)',
    table: {
      caption: 'Элементы плана переноса',
      column: { kind: 'Тип', name: 'Название', number: 'Номер', action: 'Действие', reason: 'Причина' },
      filterKindPlaceholder: 'Все типы',
      filterActionPlaceholder: 'Все действия',
      skipAction: 'Пропустить', replaceAction: 'Заменить', createAction: 'Создать',
      notReplaceable: 'Созданный вручную объект нельзя заменить — только пропустить.',
      patchFailedToast: 'Действие не выполнено: {{error}}',
    },
    weakSecrets: {
      title: 'Слабые пароли',
      body: 'У {{n}} внутренних номеров слабые пароли (менее 12 символов) — по умолчанию переносятся без изменений, чтобы телефоны не нужно было перенастраивать.',
      rotateLabel: 'Заменить слабые пароли на новые случайные',
      rotateHint: 'Если включено, новый пароль телефон получит автоматически через провижининг.',
    },
    warningsTitle: 'Предупреждения',
    ignoredTitle: 'Пропущенные строки',
    continueButton: 'Перейти к применению',
  },

  apply: {
    title: 'Применение переноса',
    preImportNotice: 'Перед применением текущее состояние будет автоматически сохранено — при неудаче ничего не изменится.',
    backupNotReady: {
      body: 'Пароль резервных копий не задан — он нужен для автоматической резервной копии перед импортом.',
      link: 'Перейти к настройкам резервных копий',
    },
    confirmLabel: 'Для подтверждения введите слово',
    confirmPlaceholder: 'KOCHIRISH',
    submit: 'Применить', submitting: 'Применяется…',
    progressLabel: 'Ход применения',
    planStale: {
      body: 'Состояние Innova изменилось с момента анализа — нужен повторный анализ.',
      reanalyze: 'Повторить анализ',
    },
    jobRunning: 'Сейчас выполняется другая задача резервного копирования/переноса — подождите её завершения.',
  },

  result: {
    titleOk: 'Перенос завершён',
    titleFailed: 'Перенос не удался',
    created: 'Создано', skipped: 'Пропущено', warnings: 'Предупреждения',
    reportButton: 'Скачать отчёт (CSV)',
    rollbackLink: 'Отменить — восстановить резервную копию до импорта',
    newImportButton: 'Начать новый импорт',
    errorLabel: 'Ошибка',
  },

  history: {
    title: 'История переносов',
    caption: 'Предыдущие задачи переноса',
    column: { created: 'Создано', source: 'Источник', status: 'Статус', summary: 'Результат', actions: '' },
    empty: { title: 'Переносов пока не было', body: 'Начните первый импорт с помощью мастера выше.' },
    deleteConfirm: { title: 'Удалить архив?', body: 'Файл архива будет удалён с диска — результат импорта сохранится.' },
    deletedToast: 'Файл архива удалён.',
    openButton: 'Открыть',
  },

  kind: {
    audio: 'Аудио', moh: 'Музыка ожидания', time_group: 'Группа времени', holiday: 'Праздник', extension: 'Внутренний номер',
    voicemail: 'Голосовая почта', trunk: 'Транк', ring_group: 'Группа приёма', queue: 'Очередь', conference: 'Конференция',
    announcement: 'Объявление', ivr: 'IVR', time_condition: 'Условие времени', inbound_route: 'Входящий маршрут',
    outbound_route: 'Исходящий маршрут', blacklist: 'Чёрный список', feature_code: 'Код функции',
  },
  statusLabel: {
    uploaded: 'Загружен', analyzing: 'Анализируется', analyzed: 'Проанализирован',
    applying: 'Применяется', ok: 'Готово', failed: 'Неудачно',
  },
  actionLabel: { create: 'Будет создано', skip: 'Будет пропущено', conflict: 'Конфликт', unsupported: 'Не поддерживается' },
  sourceLabel: { upload: 'Архив', ssh: 'SSH' },
};

export const en = {
  title: 'Migration',
  readOnlyBanner: 'Read-only — admin rights are required to change this section.',
  cancel: 'Cancel', back: 'Back', close: 'Close',

  steps: { source: 'Source', analyze: 'Analyze', review: 'Review', apply: 'Apply', result: 'Result' },

  source: {
    title: 'Choose a source on the FreePBX server',
    intro: 'Upload the export bundle or fetch it automatically over SSH — both paths lead to the same analysis.',
    uploadTab: 'Upload bundle',
    sshTab: 'Via SSH',
    exportScript: {
      title: 'Export script',
      body: 'Run on the FreePBX server as root (read-only, changes nothing):',
      downloadButton: 'Download script',
      command: 'bash innova-fpbx-export.sh',
      copyButton: 'Copy',
      copied: 'Copied.',
    },
    upload: {
      label: 'Bundle file (fpbx-export-*.tar.gz)',
      hint: 'The bundle contains SIP passwords — the file is deleted from the server once the import finishes.',
      invalidFile: 'Choose a .tar.gz or .tgz file.',
      submit: 'Upload and go to analysis',
      uploading: 'Uploading…',
      failedToast: "Couldn't upload the bundle: {{error}}",
    },
    ssh: {
      host: 'Host', port: 'Port', username: 'Username',
      password: 'Password', privateKey: 'Private key (optional, instead of password)',
      test: 'Test connection', testing: 'Testing…',
      testOk: 'Connection succeeded — you can now fetch the bundle.',
      testFailed: "Couldn't connect: {{error}}",
      fetch: 'Fetch and go to analysis', fetching: 'Fetching…',
      fetchFailedToast: "Couldn't fetch the bundle: {{error}}",
      fingerprintModal: {
        title: "Confirm the server's fingerprint",
        body: "You're connecting for the first time. Fingerprint: {{fp}} — confirm if it's correct.",
        cancel: 'Cancel', confirm: 'Confirm and fetch',
      },
    },
  },

  analyze: {
    title: 'Analyzing the bundle',
    startButton: 'Start analysis', starting: 'Starting…',
    autoStartHint: 'Nothing changes in Innova during analysis — only a plan is built.',
    progressLabel: 'Analysis progress',
  },

  review: {
    title: 'Plan',
    summaryTitle: 'By type',
    conflictsBadge: '{{n}} conflict(s)',
    table: {
      caption: 'Migration plan items',
      column: { kind: 'Type', name: 'Name', number: 'Number', action: 'Action', reason: 'Reason' },
      filterKindPlaceholder: 'All types',
      filterActionPlaceholder: 'All actions',
      skipAction: 'Skip', replaceAction: 'Replace', createAction: 'Create',
      notReplaceable: "A manually created object can't be replaced — only skipped.",
      patchFailedToast: "Action failed: {{error}}",
    },
    weakSecrets: {
      title: 'Weak secrets',
      body: '{{n}} extension(s) have weak secrets (under 12 characters) — by default they move over unchanged so phones keep working without reconfiguration.',
      rotateLabel: 'Replace weak secrets with a new random password',
      rotateHint: "If enabled, the phone picks up the new password automatically via provisioning.",
    },
    warningsTitle: 'Warnings',
    ignoredTitle: 'Ignored rows',
    continueButton: 'Continue to apply',
  },

  apply: {
    title: 'Apply the migration',
    preImportNotice: 'Before applying, the current state is backed up automatically — nothing changes if it fails.',
    backupNotReady: {
      body: 'No backup passphrase is set — one is required for the automatic pre-import backup.',
      link: 'Go to backup settings',
    },
    confirmLabel: 'Type the following word to confirm',
    confirmPlaceholder: 'KOCHIRISH',
    submit: 'Apply', submitting: 'Applying…',
    progressLabel: 'Apply progress',
    planStale: {
      body: "Innova's state changed since the analysis — a re-analysis is required.",
      reanalyze: 'Re-analyze',
    },
    jobRunning: 'Another backup/migration job is already running — wait for it to finish.',
  },

  result: {
    titleOk: 'Migration finished',
    titleFailed: 'Migration failed',
    created: 'Created', skipped: 'Skipped', warnings: 'Warnings',
    reportButton: 'Download report (CSV)',
    rollbackLink: 'Undo — restore the pre-import backup',
    newImportButton: 'Start a new import',
    errorLabel: 'Error',
  },

  history: {
    title: 'Migration history',
    caption: 'Previous migration jobs',
    column: { created: 'Created', source: 'Source', status: 'Status', summary: 'Result', actions: '' },
    empty: { title: 'No migrations yet', body: 'Start your first import with the wizard above.' },
    deleteConfirm: { title: 'Delete the bundle?', body: "The bundle file will be deleted from disk — the import result stays." },
    deletedToast: 'The bundle file was deleted.',
    openButton: 'Open',
  },

  kind: {
    audio: 'Audio', moh: 'Hold music', time_group: 'Time group', holiday: 'Holiday', extension: 'Extension',
    voicemail: 'Voicemail', trunk: 'Trunk', ring_group: 'Ring group', queue: 'Queue', conference: 'Conference',
    announcement: 'Announcement', ivr: 'IVR', time_condition: 'Time condition', inbound_route: 'Inbound route',
    outbound_route: 'Outbound route', blacklist: 'Blacklist', feature_code: 'Feature code',
  },
  statusLabel: {
    uploaded: 'Uploaded', analyzing: 'Analyzing', analyzed: 'Analyzed',
    applying: 'Applying', ok: 'Done', failed: 'Failed',
  },
  actionLabel: { create: 'Will create', skip: 'Will skip', conflict: 'Conflict', unsupported: 'Unsupported' },
  sourceLabel: { upload: 'Bundle', ssh: 'SSH' },
};
