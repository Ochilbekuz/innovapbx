// "live" namespace — LivePage (S29: jonli monitoring).

import type { LiveExtensionState } from '@/api/types';

/** Har jonli holat (API `ExtensionLiveState`) uchun yorliq — yetishmasa `tsc` yiqiladi. */
type ExtStateLabels = Record<LiveExtensionState, string>;

export const uz = {
  title: 'Jonli monitoring',
  asteriskDown: { title: 'Asterisk bilan aloqa yoʻq', body: 'Jonli maʼlumotlar vaqtincha yangilanmayapti.' },
  activeCalls: {
    title: 'Faol qoʻngʻiroqlar', empty: 'Hozir faol qoʻngʻiroq yoʻq.',
    column: { from: 'Kimdan', to: 'Kimga', duration: 'Davomiyligi', status: 'Holat' },
  },
  status: { ringing: 'Chaqirilmoqda', talking: 'Suhbatda', hold: 'Kutishda' },
  queues: {
    title: 'Navbatlar', waiting: 'Navbatda', longestWait: 'Eng uzun kutish', agents: 'Operatorlar',
    agentsOnline: '{{online}}/{{total}} faol',
  },
  extensions: {
    title: 'Ichki raqamlar holati', empty: 'Ichki raqamlar topilmadi.',
    status: { idle: 'Boʻsh', ringing: 'Chaqirilmoqda', busy: 'Band', unavailable: 'Oflayn', dnd: 'Band qilmaslik' } satisfies ExtStateLabels,
  },
  spy: {
    listen: 'Tinglash', whisper: 'Shivirlash', barge: 'Qoʻshilish',
    started: 'Nazorat boshlandi', failed: 'Nazoratni boshlab boʻlmadi',
    noExtension: 'Sizning hisobingiz ichki raqamga bogʻlanmagan — nazorat qila olmaysiz.',
  },
};

export const ru = {
  title: 'Живой мониторинг',
  asteriskDown: { title: 'Нет связи с Asterisk', body: 'Данные временно не обновляются.' },
  activeCalls: {
    title: 'Активные звонки', empty: 'Сейчас нет активных звонков.',
    column: { from: 'От кого', to: 'Кому', duration: 'Длительность', status: 'Статус' },
  },
  status: { ringing: 'Звонит', talking: 'Разговор', hold: 'На удержании' },
  queues: {
    title: 'Очереди', waiting: 'В ожидании', longestWait: 'Макс. ожидание', agents: 'Операторы',
    agentsOnline: '{{online}}/{{total}} активны',
  },
  extensions: {
    title: 'Статус внутренних номеров', empty: 'Внутренние номера не найдены.',
    status: { idle: 'Свободен', ringing: 'Звонит', busy: 'Занят', unavailable: 'Офлайн', dnd: 'Не беспокоить' } satisfies ExtStateLabels,
  },
  spy: {
    listen: 'Прослушать', whisper: 'Подсказать', barge: 'Подключиться',
    started: 'Наблюдение начато', failed: 'Не удалось начать наблюдение',
    noExtension: 'Ваш аккаунт не привязан к номеру — наблюдение недоступно.',
  },
};

export const en = {
  title: 'Live monitoring',
  asteriskDown: { title: 'Asterisk connection lost', body: 'Live data is temporarily not updating.' },
  activeCalls: {
    title: 'Active calls', empty: 'No active calls right now.',
    column: { from: 'From', to: 'To', duration: 'Duration', status: 'Status' },
  },
  status: { ringing: 'Ringing', talking: 'Talking', hold: 'On hold' },
  queues: {
    title: 'Queues', waiting: 'Waiting', longestWait: 'Longest wait', agents: 'Agents',
    agentsOnline: '{{online}}/{{total}} online',
  },
  extensions: {
    title: 'Extension status', empty: 'No extensions found.',
    status: { idle: 'Idle', ringing: 'Ringing', busy: 'Busy', unavailable: 'Offline', dnd: 'Do not disturb' } satisfies ExtStateLabels,
  },
  spy: {
    listen: 'Listen', whisper: 'Whisper', barge: 'Barge in',
    started: 'Monitoring started', failed: 'Could not start monitoring',
    noExtension: "Your account isn't linked to an extension — you can't monitor calls.",
  },
};
