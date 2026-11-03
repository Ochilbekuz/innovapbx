// "auth" namespace — LoginPage.

export const uz = {
  intro: 'Boshqaruv paneliga kirish uchun login va parolingizni kiriting.',
  login: 'Login',
  password: 'Parol',
  submit: 'Kirish',
  restoredNotice: 'Tizim zaxiradan tiklandi — qaytadan kiring.',
  changePassword: {
    title: 'Parolni oʻzgartirish', intro: 'Xavfsizlik uchun yangi parol oʻrnating — bu ekranni oʻtkazib yuborib boʻlmaydi.',
    current: 'Joriy parol', new: 'Yangi parol', newHint: 'Kamida 10 belgi',
    submit: 'Parolni oʻzgartirish va davom etish', success: 'Parol oʻzgartirildi',
  },
  // M10 B2 — kirishning 2-qadami (TOTP tasdiqlash).
  totp: {
    title: 'Ikki bosqichli tasdiqlash', intro: 'Ilovangizdagi 6 xonali kodni kiriting.',
    recoveryIntro: 'Zaxira kodlardan birini kiriting (xxxx-xxxx).',
    code: 'Tasdiqlash kodi', recoveryCode: 'Zaxira kod', submit: 'Tasdiqlash',
    back: 'Boshqa hisobdan kirish', useRecovery: 'Zaxira kod bilan kirish', useCode: 'Ilova kodi bilan kirish',
  },
  // M10 C B2 — 2FA ro'yxatdan o'tish (majburiy — Enroll2faPage, ixtiyoriy — MePage kartasi).
  enroll2fa: {
    title: 'Ikki bosqichli tasdiqlashni ulang', required: 'Administrator bu hisob uchun 2FA\'ni majburiy qildi — davom etishdan oldin ulang.',
    qrAlt: 'TOTP QR kodi', scanIntro: 'Google Authenticator, Authy yoki shunga oʻxshash ilovada QR kodni skanerlang — yoki kalitni qoʻlda kiriting:',
    copySecret: 'Kalitni nusxalash', manualHint: 'Ilova QR o\'qiy olmasa, shu kalitni qoʻlda kiriting.',
    codeLabel: 'Ilovadan 6 xonali kod', enable: 'Yoqish', copied: 'Nusxalandi',
    recoveryIntro: 'Zaxira kodlarni xavfsiz joyda saqlang — qurilma yoʻqolganda faqat shular bilan kirish mumkin. Bu kodlar faqat shu yerda koʻrsatiladi.',
    copyAll: 'Barchasini nusxalash', continue: 'Davom etish',
  },
};

export const ru = {
  intro: 'Введите логин и пароль для входа в панель управления.',
  login: 'Логин',
  password: 'Пароль',
  submit: 'Войти',
  restoredNotice: 'Система восстановлена из резервной копии — войдите снова.',
  changePassword: {
    title: 'Смена пароля', intro: 'В целях безопасности установите новый пароль — этот экран пропустить нельзя.',
    current: 'Текущий пароль', new: 'Новый пароль', newHint: 'Минимум 10 символов',
    submit: 'Сменить пароль и продолжить', success: 'Пароль изменён',
  },
  totp: {
    title: 'Двухфакторная проверка', intro: 'Введите 6-значный код из приложения.',
    recoveryIntro: 'Введите один из резервных кодов (xxxx-xxxx).',
    code: 'Код подтверждения', recoveryCode: 'Резервный код', submit: 'Подтвердить',
    back: 'Войти под другим аккаунтом', useRecovery: 'Войти по резервному коду', useCode: 'Войти по коду приложения',
  },
  enroll2fa: {
    title: 'Подключите двухфакторную проверку', required: 'Администратор сделал 2FA обязательной для этой учётной записи — подключите её, чтобы продолжить.',
    qrAlt: 'QR-код TOTP', scanIntro: 'Отсканируйте QR-код в Google Authenticator, Authy или похожем приложении — либо введите ключ вручную:',
    copySecret: 'Скопировать ключ', manualHint: 'Если приложение не может прочитать QR, введите этот ключ вручную.',
    codeLabel: '6-значный код из приложения', enable: 'Включить', copied: 'Скопировано',
    recoveryIntro: 'Сохраните резервные коды в надёжном месте — при утере устройства войти можно только по ним. Эти коды показываются только один раз.',
    copyAll: 'Скопировать все', continue: 'Продолжить',
  },
};

export const en = {
  intro: 'Enter your login and password to access the admin panel.',
  login: 'Login',
  password: 'Password',
  submit: 'Sign in',
  restoredNotice: 'The system was restored from a backup — sign in again.',
  changePassword: {
    title: 'Change password', intro: "For security, set a new password — you can't skip this screen.",
    current: 'Current password', new: 'New password', newHint: 'At least 10 characters',
    submit: 'Change password and continue', success: 'Password changed',
  },
  totp: {
    title: 'Two-factor verification', intro: 'Enter the 6-digit code from your app.',
    recoveryIntro: 'Enter one of your recovery codes (xxxx-xxxx).',
    code: 'Verification code', recoveryCode: 'Recovery code', submit: 'Verify',
    back: 'Sign in with a different account', useRecovery: 'Use a recovery code', useCode: 'Use app code',
  },
  enroll2fa: {
    title: 'Set up two-factor verification', required: 'Your administrator made 2FA mandatory for this account — set it up to continue.',
    qrAlt: 'TOTP QR code', scanIntro: 'Scan the QR code in Google Authenticator, Authy, or a similar app — or enter the key manually:',
    copySecret: 'Copy key', manualHint: "If your app can't scan the QR code, enter this key manually.",
    codeLabel: '6-digit code from your app', enable: 'Enable', copied: 'Copied',
    recoveryIntro: 'Store the recovery codes somewhere safe — if you lose your device, they are the only way back in. These codes are shown only once.',
    copyAll: 'Copy all', continue: 'Continue',
  },
};
