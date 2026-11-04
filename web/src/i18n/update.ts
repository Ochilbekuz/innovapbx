// "update" namespace — Paneldan yangilash sahifasi (S45, guruh `system`, faqat `*`).
// Shartnoma: ../../replica/m11-update-contract.md

export const uz = {
  title: 'Yangilanish',
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',

  noAgent: {
    title: "Paneldan yangilash o'rnatilmagan",
    body: "Bu serverda yangilash agenti topilmadi (odatda ishlab chiqish muhitida shunday). Terminaldan yangilash mumkin:",
    cliHint: 'sudo innova-update',
  },

  version: {
    currentLabel: 'Joriy versiya',
    checkedAtLabel: 'Oxirgi tekshiruv',
    neverChecked: 'Hali tekshirilmagan',
    checkButton: 'Tekshirish',
    checking: 'Tekshirilmoqda…',
    upToDate: 'Siz eng so‘nggi versiyadasiz.',
    newVersionTitle: 'Yangi versiya: {{version}}',
  },

  changelog: { title: "O'zgarishlar" },

  confirm: {
    updateButton: 'Yangilash',
    modalTitle: '{{version}} ga yangilash',
    warningBackup: "Yangilashdan oldin avtomatik zaxira olinadi.",
    warningDuration: 'Jarayon odatda 5–15 daqiqa davom etadi.',
    warningCalls: "Bu vaqtda qo'ng'iroqlar ~1 daqiqaga uzilishi mumkin.",
    typeLabel: "Tasdiqlash uchun versiya raqamini yozing: {{version}}",
    typePlaceholder: '0.0.0',
    typeMismatch: "Versiya raqami mos kelmadi.",
    confirmButton: 'Boshlash',
    cancelButton: 'Bekor qilish',
    stale: 'Sahifa eskirgan edi — holat yangilandi, qaytadan tekshirib ko‘ring.',
  },

  progress: {
    title: 'Yangilanish jarayoni',
    phase: { backup: 'Zaxira olinmoqda', code: 'Kod yuklanmoqda', install: "O'rnatilmoqda", restart: 'Qayta ishga tushirilmoqda' },
    restarting: "Tizim qayta ishga tushmoqda — bu normal holat, kuting…",
    logTitle: 'Jurnal',
    logPaused: "Pastga aylantiring — jonli kuzatish davom etadi",
    logResume: 'Oxiriga oʻtish',
  },

  done: {
    title: 'Yangilandi',
    body: "{{version}} versiyasiga muvaffaqiyatli yangilandi.",
    reloadButton: 'Sahifani yangilash',
  },

  failed: {
    title: 'Yangilanmadi',
    backupLabel: 'Zaxira fayli',
    viewLogButton: 'Jurnalni ko‘rish',
  },

  error: {
    no_source: { title: "Manba sozlanmagan", body: "Git repozitoriysi topilmadi yoki `upstream` ulanmagan. Terminalda `innova-update --check` ishga tushirib sababini ko'ring." },
    fetch_failed: { title: "Yuklab bo'lmadi", body: "Yangi kodni serverdan olishda xatolik (tarmoq yoki ruxsat). Internet aloqasini tekshirib qayta urinib ko'ring." },
    git_dirty: { title: "Kodda saqlanmagan o'zgarish bor", body: "Hostda qo'lda kiritilgan o'zgarishlar bor — avtomatik yangilash xavfli. Administratorga murojaat qiling." },
    backup_failed: { title: "Zaxira olinmadi", body: "Yangilash zaxira bosqichida to'xtadi — kod o'zgarmagan, tizim avvalgidek ishlayapti. Disk joyini tekshiring va qayta urinib ko'ring." },
    install_failed: { title: "O'rnatishda xatolik", body: "Zaxira olingan, lekin o'rnatish bosqichi muvaffaqiyatsiz tugadi. Quyidagi zaxiradan qo'lda tiklash kerak bo'lishi mumkin — administratorga murojaat qiling." },
    interrupted: { title: "Jarayon uzildi", body: "Oldingi yangilanish tugamay tizim qayta ishga tushgan (masalan, elektr uzilishi). Holatni tekshirib qaytadan urinib ko'ring." },
    bad_request: { title: "Noto'g'ri so'rov", body: "Versiya formati yoki so'rov noto'g'ri edi. Sahifani yangilab qaytadan urinib ko'ring." },
  },
};

export const ru = {
  title: 'Обновление',
  loadFailed: 'Не удалось загрузить.',
  retry: 'Повторить',

  noAgent: {
    title: 'Обновление из панели не настроено',
    body: 'На этом сервере не найден агент обновления (обычно это так в среде разработки). Обновить можно из терминала:',
    cliHint: 'sudo innova-update',
  },

  version: {
    currentLabel: 'Текущая версия',
    checkedAtLabel: 'Последняя проверка',
    neverChecked: 'Ещё не проверялось',
    checkButton: 'Проверить',
    checking: 'Проверка…',
    upToDate: 'У вас последняя версия.',
    newVersionTitle: 'Новая версия: {{version}}',
  },

  changelog: { title: 'Изменения' },

  confirm: {
    updateButton: 'Обновить',
    modalTitle: 'Обновление до {{version}}',
    warningBackup: 'Перед обновлением будет сделана автоматическая резервная копия.',
    warningDuration: 'Процесс обычно занимает 5–15 минут.',
    warningCalls: 'В это время звонки могут прерваться примерно на 1 минуту.',
    typeLabel: 'Для подтверждения введите номер версии: {{version}}',
    typePlaceholder: '0.0.0',
    typeMismatch: 'Номер версии не совпадает.',
    confirmButton: 'Начать',
    cancelButton: 'Отмена',
    stale: 'Страница была устаревшей — статус обновлён, проверьте ещё раз.',
  },

  progress: {
    title: 'Процесс обновления',
    phase: { backup: 'Резервное копирование', code: 'Загрузка кода', install: 'Установка', restart: 'Перезапуск' },
    restarting: 'Система перезапускается — это нормально, подождите…',
    logTitle: 'Журнал',
    logPaused: 'Прокрутите вниз — живое наблюдение продолжится',
    logResume: 'К концу',
  },

  done: {
    title: 'Обновлено',
    body: 'Успешно обновлено до версии {{version}}.',
    reloadButton: 'Обновить страницу',
  },

  failed: {
    title: 'Не удалось обновить',
    backupLabel: 'Файл резервной копии',
    viewLogButton: 'Показать журнал',
  },

  error: {
    no_source: { title: 'Источник не настроен', body: 'Git-репозиторий не найден или не подключён upstream. Запустите `innova-update --check` в терминале, чтобы увидеть причину.' },
    fetch_failed: { title: 'Не удалось загрузить', body: 'Ошибка при получении нового кода с сервера (сеть или права доступа). Проверьте подключение и повторите попытку.' },
    git_dirty: { title: 'Есть несохранённые изменения в коде', body: 'На хосте внесены изменения вручную — автоматическое обновление рискованно. Обратитесь к администратору.' },
    backup_failed: { title: 'Не удалось создать резервную копию', body: 'Обновление остановилось на этапе резервного копирования — код не изменён, система работает как прежде. Проверьте место на диске и повторите попытку.' },
    install_failed: { title: 'Ошибка установки', body: 'Резервная копия создана, но этап установки завершился неудачно. Возможно потребуется восстановление из копии — обратитесь к администратору.' },
    interrupted: { title: 'Процесс был прерван', body: 'Предыдущее обновление не завершилось из-за перезапуска системы (например, сбой питания). Проверьте статус и повторите попытку.' },
    bad_request: { title: 'Неверный запрос', body: 'Неверный формат версии или запроса. Обновите страницу и попробуйте снова.' },
  },
};

export const en = {
  title: 'Update',
  loadFailed: 'Could not load.',
  retry: 'Retry',

  noAgent: {
    title: 'Panel updates are not set up',
    body: 'No update agent was found on this server (usually the case in development environments). You can still update from the terminal:',
    cliHint: 'sudo innova-update',
  },

  version: {
    currentLabel: 'Current version',
    checkedAtLabel: 'Last checked',
    neverChecked: 'Not checked yet',
    checkButton: 'Check for updates',
    checking: 'Checking…',
    upToDate: "You're on the latest version.",
    newVersionTitle: 'New version: {{version}}',
  },

  changelog: { title: "What's new" },

  confirm: {
    updateButton: 'Update',
    modalTitle: 'Update to {{version}}',
    warningBackup: 'An automatic backup will be taken before updating.',
    warningDuration: 'The process usually takes 5–15 minutes.',
    warningCalls: 'Calls may be interrupted for about 1 minute during this time.',
    typeLabel: 'Type the version number to confirm: {{version}}',
    typePlaceholder: '0.0.0',
    typeMismatch: "Version number doesn't match.",
    confirmButton: 'Start',
    cancelButton: 'Cancel',
    stale: 'This page was stale — status refreshed, please check again.',
  },

  progress: {
    title: 'Update in progress',
    phase: { backup: 'Taking backup', code: 'Fetching code', install: 'Installing', restart: 'Restarting' },
    restarting: 'The system is restarting — this is normal, please wait…',
    logTitle: 'Log',
    logPaused: 'Scroll down to resume live tracking',
    logResume: 'Jump to latest',
  },

  done: {
    title: 'Updated',
    body: 'Successfully updated to {{version}}.',
    reloadButton: 'Reload page',
  },

  failed: {
    title: 'Update failed',
    backupLabel: 'Backup file',
    viewLogButton: 'View log',
  },

  error: {
    no_source: { title: 'Source not configured', body: 'No git repository was found, or no upstream is connected. Run `innova-update --check` in a terminal to see why.' },
    fetch_failed: { title: 'Could not fetch update', body: 'Fetching the new code from the server failed (network or permissions). Check connectivity and try again.' },
    git_dirty: { title: 'Uncommitted local changes', body: 'The host has manual changes that were never committed — an automatic update would be risky. Contact your administrator.' },
    backup_failed: { title: 'Backup failed', body: 'The update stopped at the backup step — nothing changed, the system is running as before. Check available disk space and try again.' },
    install_failed: { title: 'Install failed', body: 'A backup was taken, but the install step failed. A manual restore from the backup may be needed — contact your administrator.' },
    interrupted: { title: 'Update was interrupted', body: 'A previous update did not finish because the system restarted (e.g. a power loss). Check the status and try again.' },
    bad_request: { title: 'Bad request', body: 'The version format or request was invalid. Reload the page and try again.' },
  },
};
