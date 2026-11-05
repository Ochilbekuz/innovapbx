// "devices" namespace — Qurilmalar sahifasi (S35): apparatlarni avtoprovizioning.
// Qarang ../../replica/m4a-contract.md §3-4.

export const uz = {
  title: 'Qurilmalar',
  readOnlyBanner: 'Faqat koʻrish — bu boʻlimni oʻzgartirish uchun maʼmur huquqi kerak.',
  tabs: { devices: 'Apparatlar', settings: 'Sozlamalar', log: 'Jurnal' },
  cancel: 'Bekor qilish', save: 'Saqlash', saved: 'Saqlandi.', close: 'Yopish', delete: 'Oʻchirish', copy: 'Nusxalash', copied: 'Nusxalandi',

  provisioning: {
    title: 'Provizioning manzili',
    desc: 'Apparat shu manzildan oʻz konfiguratsiyasini oladi — DHCP (option 66) orqali avtomatik yoki qoʻlda kiritiladi.',
    urlLabel: 'Provizioning URL',
    dhcpLabel: 'DHCP option 66', dhcpHint: 'Agar tarmoqda DHCP option 66 sozlangan bo‘lsa, apparat manzilni avtomatik oladi.',
    instructionsTitle: 'Qoʻlda kiritish (apparat veb-panelida)',
    steps: {
      yealink: '1) Apparat veb-panelida «Network → Advanced → Auto Provision» boʻlimiga oʻting. 2) «Server URL» maydoniga yuqoridagi manzilni kiriting. 3) «Auto Provision Now» tugmasini bosing — apparat qayta yuklanadi.',
      grandstream: '1) Apparat veb-panelida «Maintenance → Upgrade and Provisioning» boʻlimiga oʻting. 2) «Config Server Path» maydoniga yuqoridagi manzilni kiriting (XML Config). 3) «Apply» va «Reboot» bosing.',
      fanvil: '1) Apparat veb-panelida «Setting → Auto Provision» boʻlimiga oʻting. 2) «Server Address» maydoniga yuqoridagi manzilni kiriting. 3) «Provision Now» tugmasini bosing.',
    },
    rotateToken: 'Tokenni almashtirish',
    rotateConfirmTitle: 'Provizioning tokenini almashtirasizmi?',
    rotateConfirmBody: 'Eski manzil darhol ishlamay qoladi — barcha apparatlarda provizioning manzilini qoʻlda yangilash kerak boʻladi (DHCP orqali olganlar avtomatik yangilaydi).',
    rotateConfirm: 'Ha, almashtirish',
    rotated: 'Yangi token yaratildi — eski manzil endi ishlamaydi.',
  },

  discovered: {
    banner: 'Topilgan qurilmalar: {{count}} ta',
    desc: 'Tarmoqda roʻyxatda yoʻq MAC manzildan provizioning soʻrovi kelgan — ichki raqamga biriktiring yoki eʼtiborsiz qoldiring.',
    empty: 'Hozircha nomaʼlum apparat topilmadi.',
    column: { mac: 'MAC', model: 'Vendor / model', ip: 'IP', lastSeen: 'Oxirgi soʻrov', requests: 'Soʻrovlar' },
    assign: 'Raqamga biriktirish', ignore: 'Eʼtiborsiz qoldirish',
    assignModalTitle: 'Qurilmani ichki raqamga biriktirish',
    assignModalDesc: 'MAC {{mac}} — {{model}}',
    extensionLabel: 'Ichki raqam', extensionPlaceholder: 'Raqam tanlang',
    labelField: 'Yorliq', labelHint: 'Ixtiyoriy — jadvalda koʻrsatiladi (masalan "Qabulxona").',
    assigned: 'Qurilma biriktirildi.',
  },

  table: {
    caption: 'Apparatlar roʻyxati',
    column: {
      status: 'Holat', mac: 'MAC', model: 'Vendor / model', extension: 'Ichki raqam', ip: 'IP', firmware: 'Firmware', lastSeen: 'Oxirgi koʻrinish', actions: '',
    },
    noExtension: 'Biriktirilmagan',
    never: '—',
    empty: { title: 'Hali apparat qoʻshilmagan', body: 'Yangi apparat qoʻshing yoki tarmoqdan avtomatik topilganini biriktiring.' },
    create: 'Apparat qoʻshish',
    edit: 'Tahrirlash', keys: 'Tugmalar', resync: 'Qayta sozlash', viewConfig: 'Config',
  },

  status: { never: 'Hech soʻramagan', provisioned: 'Sozlandi', registered: 'Roʻyxatda', stale_config: 'Yangilanishi kerak' },

  form: {
    createTitle: 'Apparat qoʻshish', editTitle: 'Apparatni tahrirlash',
    mac: 'MAC manzil', macHint: '12 ta hex belgi — «:» yoki «-» bilan ham kiritish mumkin.',
    vendor: 'Vendor', model: 'Model',
    extension: 'Ichki raqam', extensionHint: 'Brauzer softfoni (WebRTC) yoqilgan raqamga apparat ulab boʻlmaydi.',
    label: 'Yorliq', labelHint: 'Ixtiyoriy — jadval va konfiguratsiyada koʻrinadi.',
    enabled: 'Yoqilgan', enabledDesc: 'Oʻchirilgan apparat konfiguratsiya olmaydi.',
    notes: 'Izoh',
  },

  keysModal: {
    title: 'Tugmalar — {{label}}', desc: 'Model {{limit}} ta dastur tugmasini qoʻllaydi.',
    column: { idx: '#', type: 'Turi', value: 'Qiymat', label: 'Yorliq' },
    typeOption: { blf: 'BLF (hamkasb)', speed_dial: 'Tezkor terish', line: 'Liniya', park: 'Parkovka', dnd: 'DND', none: 'Boʻsh' },
    valuePlaceholder: 'Raqam', labelPlaceholder: 'Yorliq',
    addKey: 'Tugma qoʻshish', removeKey: 'Oʻchirish',
  },

  configModal: {
    title: 'Konfiguratsiya — {{filename}}',
    maskedNotice: 'Parol va boshqa sirlar «***» bilan almashtirilgan — bu yerda hech qachon ochiq koʻrsatilmaydi.',
  },

  deleteModal: { title: 'Apparatni oʻchirasizmi?', body: '«{{label}}» (MAC {{mac}}) roʻyxatdan oʻchiriladi — apparat yana qayta provizion qilinishi kerak boʻladi.' },

  toast: {
    created: 'Apparat qoʻshildi.', deleted: 'Apparat oʻchirildi.', keysSaved: 'Tugmalar saqlandi.',
    resyncOk: 'Qayta sozlash soʻrovi yuborildi.', resyncFailed: 'Qayta sozlab boʻlmadi.',
  },

  settings: {
    title: 'Provizioning sozlamalari',
    language: 'Til', timezone: 'Vaqt zonasi',
    timezoneHint: 'Sukut boʻyicha tizim vaqt zonasiga bogʻlangan ("Sana va vaqt" sahifasi); bu yerda oʻzgartirsangiz — faqat apparatlar uchun oʻz holicha qoladi.',
    timezoneSearchPlaceholder: 'Shahar yoki UTC+05 boʻyicha qidirish', timezoneNoMatch: 'Mos zona topilmadi',
    ntpServer: 'NTP server',
    sipTransport: 'SIP transport', sipServerHost: 'SIP server hosti', sipServerHostHint: 'Boʻsh boʻlsa — ochiq (public) manzil hostidan olinadi.',
    allowedNetworks: 'Ruxsat etilgan tarmoqlar (CIDR)', allowedNetworksHint: 'Har qatorda bitta tarmoq, masalan 10.0.0.0/8. Boʻsh — hammasiga ruxsat.',
    adminPassword: 'Apparat admin paroli', adminPasswordHint: 'Bir martalik kiritish — saqlangandan keyin qayta koʻrsatilmaydi.',
    adminPasswordSet: 'Parol saqlangan — oʻzgartirish uchun qayta kiriting.',
    extraTitle: 'Qoʻshimcha qatorlar (ilg‘or)', extraHint: 'Har vendor uchun xom qatorlar — notoʻgʻri format saqlanmaydi.',
    extra: { yealink: 'Yealink (key = value)', grandstream: 'Grandstream (Pnnn=value)', fanvil: 'Fanvil (key = value)' },
  },

  log: {
    title: 'Provizioning jurnali',
    column: { at: 'Vaqt', ip: 'IP', mac: 'MAC', vendor: 'Vendor', path: 'Yoʻl', statusCode: 'Kod', reason: 'Sabab' },
    reason: {
      unknown_mac: 'Nomaʼlum MAC', bad_token: 'Notoʻgʻri token', network_denied: 'Tarmoq rad etildi',
      rate_limited: 'Limit oshdi', ok: 'Muvaffaqiyatli', legacy_binary: 'Eski firmware (binary soʻrov)',
    },
    empty: 'Hali provizioning soʻrovi yoʻq.',
  },
};

export const ru = {
  title: 'Устройства',
  readOnlyBanner: 'Только просмотр — для изменений нужны права администратора.',
  tabs: { devices: 'Аппараты', settings: 'Настройки', log: 'Журнал' },
  cancel: 'Отмена', save: 'Сохранить', saved: 'Сохранено.', close: 'Закрыть', delete: 'Удалить', copy: 'Копировать', copied: 'Скопировано',

  provisioning: {
    title: 'Адрес провижининга',
    desc: 'Аппарат получает конфигурацию с этого адреса — автоматически через DHCP (option 66) или вручную.',
    urlLabel: 'URL провижининга',
    dhcpLabel: 'DHCP option 66', dhcpHint: 'Если в сети настроен DHCP option 66, аппарат получит адрес автоматически.',
    instructionsTitle: 'Ввод вручную (в веб-панели аппарата)',
    steps: {
      yealink: '1) В веб-панели аппарата откройте «Network → Advanced → Auto Provision». 2) В поле «Server URL» укажите адрес выше. 3) Нажмите «Auto Provision Now» — аппарат перезагрузится.',
      grandstream: '1) В веб-панели аппарата откройте «Maintenance → Upgrade and Provisioning». 2) В поле «Config Server Path» укажите адрес выше (XML Config). 3) Нажмите «Apply» и «Reboot».',
      fanvil: '1) В веб-панели аппарата откройте «Setting → Auto Provision». 2) В поле «Server Address» укажите адрес выше. 3) Нажмите «Provision Now».',
    },
    rotateToken: 'Сменить токен',
    rotateConfirmTitle: 'Сменить токен провижининга?',
    rotateConfirmBody: 'Старый адрес сразу перестанет работать — на всех аппаратах нужно будет вручную обновить адрес (получившие через DHCP обновятся автоматически).',
    rotateConfirm: 'Да, сменить',
    rotated: 'Создан новый токен — старый адрес больше не работает.',
  },

  discovered: {
    banner: 'Найдено устройств: {{count}}',
    desc: 'В сети обнаружен запрос провижининга с MAC-адреса не из списка — привяжите к номеру или проигнорируйте.',
    empty: 'Пока нет найденных неизвестных аппаратов.',
    column: { mac: 'MAC', model: 'Вендор / модель', ip: 'IP', lastSeen: 'Последний запрос', requests: 'Запросы' },
    assign: 'Привязать к номеру', ignore: 'Проигнорировать',
    assignModalTitle: 'Привязать устройство к внутреннему номеру',
    assignModalDesc: 'MAC {{mac}} — {{model}}',
    extensionLabel: 'Внутренний номер', extensionPlaceholder: 'Выберите номер',
    labelField: 'Метка', labelHint: 'Необязательно — отображается в таблице (например «Ресепшн»).',
    assigned: 'Устройство привязано.',
  },

  table: {
    caption: 'Список аппаратов',
    column: {
      status: 'Статус', mac: 'MAC', model: 'Вендор / модель', extension: 'Внутренний номер', ip: 'IP', firmware: 'Прошивка', lastSeen: 'Последний раз онлайн', actions: '',
    },
    noExtension: 'Не привязан',
    never: '—',
    empty: { title: 'Пока нет добавленных аппаратов', body: 'Добавьте аппарат вручную или привяжите найденный автоматически.' },
    create: 'Добавить аппарат',
    edit: 'Редактировать', keys: 'Кнопки', resync: 'Пересинхронизация', viewConfig: 'Конфиг',
  },

  status: { never: 'Не обращался', provisioned: 'Настроен', registered: 'В сети', stale_config: 'Нужно обновить' },

  form: {
    createTitle: 'Добавить аппарат', editTitle: 'Редактирование аппарата',
    mac: 'MAC-адрес', macHint: '12 hex-символов — можно вводить с «:» или «-».',
    vendor: 'Вендор', model: 'Модель',
    extension: 'Внутренний номер', extensionHint: 'К номеру с включённым браузерным софтфоном (WebRTC) аппарат привязать нельзя.',
    label: 'Метка', labelHint: 'Необязательно — отображается в таблице и конфигурации.',
    enabled: 'Включён', enabledDesc: 'Отключённый аппарат не получает конфигурацию.',
    notes: 'Заметка',
  },

  keysModal: {
    title: 'Кнопки — {{label}}', desc: 'Модель поддерживает {{limit}} программируемых кнопок.',
    column: { idx: '№', type: 'Тип', value: 'Значение', label: 'Метка' },
    typeOption: { blf: 'BLF (коллега)', speed_dial: 'Быстрый вызов', line: 'Линия', park: 'Парковка', dnd: 'DND', none: 'Пусто' },
    valuePlaceholder: 'Номер', labelPlaceholder: 'Метка',
    addKey: 'Добавить кнопку', removeKey: 'Удалить',
  },

  configModal: {
    title: 'Конфигурация — {{filename}}',
    maskedNotice: 'Пароль и другие секреты заменены на «***» — здесь они никогда не показываются открыто.',
  },

  deleteModal: { title: 'Удалить аппарат?', body: '«{{label}}» (MAC {{mac}}) будет удалён из списка — аппарат придётся провижинить заново.' },

  toast: {
    created: 'Аппарат добавлен.', deleted: 'Аппарат удалён.', keysSaved: 'Кнопки сохранены.',
    resyncOk: 'Запрос на пересинхронизацию отправлен.', resyncFailed: 'Не удалось пересинхронизировать.',
  },

  settings: {
    title: 'Настройки провижининга',
    language: 'Язык', timezone: 'Часовой пояс',
    timezoneHint: 'По умолчанию привязан к системному часовому поясу (страница «Дата и время»); изменение здесь действует только для аппаратов.',
    timezoneSearchPlaceholder: 'Поиск по городу или UTC+05', timezoneNoMatch: 'Часовой пояс не найден',
    ntpServer: 'NTP-сервер',
    sipTransport: 'SIP транспорт', sipServerHost: 'Хост SIP-сервера', sipServerHostHint: 'Если пусто — берётся хост публичного адреса.',
    allowedNetworks: 'Разрешённые сети (CIDR)', allowedNetworksHint: 'По одной сети на строку, например 10.0.0.0/8. Пусто — разрешено всем.',
    adminPassword: 'Пароль администратора аппарата', adminPasswordHint: 'Вводится один раз — после сохранения не показывается повторно.',
    adminPasswordSet: 'Пароль сохранён — для изменения введите заново.',
    extraTitle: 'Дополнительные строки (для опытных)', extraHint: 'Сырые строки для каждого вендора — неверный формат не сохранится.',
    extra: { yealink: 'Yealink (key = value)', grandstream: 'Grandstream (Pnnn=value)', fanvil: 'Fanvil (key = value)' },
  },

  log: {
    title: 'Журнал провижининга',
    column: { at: 'Время', ip: 'IP', mac: 'MAC', vendor: 'Вендор', path: 'Путь', statusCode: 'Код', reason: 'Причина' },
    reason: {
      unknown_mac: 'Неизвестный MAC', bad_token: 'Неверный токен', network_denied: 'Сеть отклонена',
      rate_limited: 'Превышен лимит', ok: 'Успешно', legacy_binary: 'Старая прошивка (бинарный запрос)',
    },
    empty: 'Пока нет запросов провижининга.',
  },
};

export const en = {
  title: 'Devices',
  readOnlyBanner: 'Read-only — admin access is required to change this section.',
  tabs: { devices: 'Devices', settings: 'Settings', log: 'Log' },
  cancel: 'Cancel', save: 'Save', saved: 'Saved.', close: 'Close', delete: 'Delete', copy: 'Copy', copied: 'Copied',

  provisioning: {
    title: 'Provisioning address',
    desc: 'The device fetches its configuration from this address — automatically via DHCP (option 66) or entered manually.',
    urlLabel: 'Provisioning URL',
    dhcpLabel: 'DHCP option 66', dhcpHint: 'If DHCP option 66 is configured on the network, the device picks up the address automatically.',
    instructionsTitle: 'Manual entry (in the device web panel)',
    steps: {
      yealink: '1) In the device web panel open "Network → Advanced → Auto Provision". 2) Enter the address above into "Server URL". 3) Click "Auto Provision Now" — the device reboots.',
      grandstream: '1) In the device web panel open "Maintenance → Upgrade and Provisioning". 2) Enter the address above into "Config Server Path" (XML Config). 3) Click "Apply" and "Reboot".',
      fanvil: '1) In the device web panel open "Setting → Auto Provision". 2) Enter the address above into "Server Address". 3) Click "Provision Now".',
    },
    rotateToken: 'Rotate token',
    rotateConfirmTitle: 'Rotate the provisioning token?',
    rotateConfirmBody: 'The old address stops working immediately — every device will need its provisioning address updated manually (devices using DHCP will pick it up automatically).',
    rotateConfirm: 'Yes, rotate',
    rotated: 'A new token was created — the old address no longer works.',
  },

  discovered: {
    banner: 'Discovered devices: {{count}}',
    desc: 'A provisioning request came from a MAC address that is not in the list yet — attach it to an extension or ignore it.',
    empty: 'No unknown devices discovered yet.',
    column: { mac: 'MAC', model: 'Vendor / model', ip: 'IP', lastSeen: 'Last request', requests: 'Requests' },
    assign: 'Attach to extension', ignore: 'Ignore',
    assignModalTitle: 'Attach device to an extension',
    assignModalDesc: 'MAC {{mac}} — {{model}}',
    extensionLabel: 'Extension', extensionPlaceholder: 'Pick an extension',
    labelField: 'Label', labelHint: 'Optional — shown in the table (e.g. "Front desk").',
    assigned: 'Device attached.',
  },

  table: {
    caption: 'Devices list',
    column: {
      status: 'Status', mac: 'MAC', model: 'Vendor / model', extension: 'Extension', ip: 'IP', firmware: 'Firmware', lastSeen: 'Last seen', actions: '',
    },
    noExtension: 'Unassigned',
    never: '—',
    empty: { title: 'No devices added yet', body: 'Add a device manually or attach one that was discovered automatically.' },
    create: 'Add device',
    edit: 'Edit', keys: 'Keys', resync: 'Resync', viewConfig: 'Config',
  },

  status: { never: 'Never checked in', provisioned: 'Provisioned', registered: 'Registered', stale_config: 'Needs update' },

  form: {
    createTitle: 'Add device', editTitle: 'Edit device',
    mac: 'MAC address', macHint: '12 hex characters — can also be entered with ":" or "-".',
    vendor: 'Vendor', model: 'Model',
    extension: 'Extension', extensionHint: "Can't attach a device to an extension with the browser softphone (WebRTC) enabled.",
    label: 'Label', labelHint: 'Optional — shown in the table and in the config.',
    enabled: 'Enabled', enabledDesc: "A disabled device won't receive configuration.",
    notes: 'Notes',
  },

  keysModal: {
    title: 'Keys — {{label}}', desc: 'This model supports {{limit}} programmable keys.',
    column: { idx: '#', type: 'Type', value: 'Value', label: 'Label' },
    typeOption: { blf: 'BLF (colleague)', speed_dial: 'Speed dial', line: 'Line', park: 'Park', dnd: 'DND', none: 'Empty' },
    valuePlaceholder: 'Number', labelPlaceholder: 'Label',
    addKey: 'Add key', removeKey: 'Remove',
  },

  configModal: {
    title: 'Configuration — {{filename}}',
    maskedNotice: 'Passwords and other secrets are replaced with "***" — they are never shown here in the clear.',
  },

  deleteModal: { title: 'Delete this device?', body: '"{{label}}" (MAC {{mac}}) will be removed from the list — the device will need to be provisioned again.' },

  toast: {
    created: 'Device added.', deleted: 'Device deleted.', keysSaved: 'Keys saved.',
    resyncOk: 'Resync request sent.', resyncFailed: "Couldn't resync.",
  },

  settings: {
    title: 'Provisioning settings',
    language: 'Language', timezone: 'Timezone',
    timezoneHint: 'Bound to the system timezone by default ("Date & time" page); changing it here only affects devices.',
    timezoneSearchPlaceholder: 'Search by city or UTC+05', timezoneNoMatch: 'No matching timezone',
    ntpServer: 'NTP server',
    sipTransport: 'SIP transport', sipServerHost: 'SIP server host', sipServerHostHint: "Empty — uses the public base URL's host.",
    allowedNetworks: 'Allowed networks (CIDR)', allowedNetworksHint: 'One network per line, e.g. 10.0.0.0/8. Empty — allow everyone.',
    adminPassword: 'Device admin password', adminPasswordHint: 'Entered once — not shown again after it is saved.',
    adminPasswordSet: 'Password saved — re-enter to change it.',
    extraTitle: 'Extra lines (advanced)', extraHint: 'Raw lines per vendor — an invalid format is not saved.',
    extra: { yealink: 'Yealink (key = value)', grandstream: 'Grandstream (Pnnn=value)', fanvil: 'Fanvil (key = value)' },
  },

  log: {
    title: 'Provisioning log',
    column: { at: 'Time', ip: 'IP', mac: 'MAC', vendor: 'Vendor', path: 'Path', statusCode: 'Code', reason: 'Reason' },
    reason: {
      unknown_mac: 'Unknown MAC', bad_token: 'Bad token', network_denied: 'Network denied',
      rate_limited: 'Rate limited', ok: 'OK', legacy_binary: 'Legacy firmware (binary request)',
    },
    empty: 'No provisioning requests yet.',
  },
};
