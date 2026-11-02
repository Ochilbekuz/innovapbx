// /design sahifasi uchun namunaviy ma'lumot. Ismlar va raqamlar to'qima.
import type { Catalog, Destination } from '@/domain/destination';
import type { HealthItem } from '@/ui/Health';
import type { Status } from '@/ui/Status';
import type { LogLine } from '@/pbx/LogViewer';

export const catalog: Catalog = {
  e101: { id: 'e101', kind: 'extension', name: 'Dilnoza Karimova', number: '101', next: [{ label: '20 s javobsiz', dest: { kind: 'voicemail', targetId: 'vm101' } }] },
  e102: { id: 'e102', kind: 'extension', name: 'Bekzod Rahimov', number: '102' },
  e115: { id: 'e115', kind: 'extension', name: 'Qabulxona', number: '115' },
  e204: { id: 'e204', kind: 'extension', name: 'Gʻayrat Toʻxtayev', number: '204' },
  rg1: { id: 'rg1', kind: 'ring_group', name: 'Buxgalteriya', number: '610', next: [{ label: 'javobsiz', dest: { kind: 'voicemail', targetId: 'vm101' } }] },
  q1: { id: 'q1', kind: 'queue', name: 'Sotuv boʻlimi', number: '600', next: [{ label: '3 daq kutish', dest: { kind: 'ring_group', targetId: 'rg1' } }] },
  q2: { id: 'q2', kind: 'queue', name: 'Texnik yordam', number: '601', next: [{ label: 'agent yoʻq', dest: { kind: 'extension', targetId: 'e1099' } }] },
  ivr1: {
    id: 'ivr1', kind: 'ivr', name: 'Asosiy menyu', number: '700',
    next: [
      { label: '1', dest: { kind: 'queue', targetId: 'q1' } },
      { label: '2', dest: { kind: 'queue', targetId: 'q2' } },
      { label: '0', dest: { kind: 'extension', targetId: 'e115' } },
      { label: 'vaqt tugadi', dest: { kind: 'ivr', targetId: 'ivr1' } },
    ],
  },
  tc1: {
    id: 'tc1', kind: 'time_condition', name: 'Ish vaqti (Du–Ju)',
    next: [
      { label: 'ochiq', dest: { kind: 'ivr', targetId: 'ivr1' } },
      { label: 'yopiq', dest: { kind: 'announcement', targetId: 'an1' } },
    ],
  },
  an1: { id: 'an1', kind: 'announcement', name: 'Tungi eʼlon', next: [{ label: 'keyin', dest: { kind: 'hangup', targetId: 'hu1' } }] },
  vm101: { id: 'vm101', kind: 'voicemail', name: 'Dilnoza — pochta', number: '*101' },
  hu1: { id: 'hu1', kind: 'hangup', name: 'Qoʻngʻiroqni yakunlash' },
};

/** Tuzatilgan oqim: IVR timeout → qabulxona, texnik yordam failover → ovozli pochta. */
export const catalogFixed: Catalog = {
  ...catalog,
  ivr1: { ...catalog.ivr1!, next: catalog.ivr1!.next!.map((e) => (e.label === 'vaqt tugadi' ? { ...e, dest: { kind: 'extension', targetId: 'e115' } } : e)) },
  q2: { ...catalog.q2!, next: [{ label: 'agent yoʻq', dest: { kind: 'voicemail', targetId: 'vm101' } }] },
};

export const flowRoot: Destination = { kind: 'time_condition', targetId: 'tc1' };

export const health: HealthItem[] = [
  { id: 'ast', label: 'Asterisk', level: 'ok', value: '14 kun', reason: 'Javob vaqti 3 ms, 18 ta faol kanal' },
  { id: 'trunk-uztel', label: 'Trunk: Uztelecom', level: 'ok', value: '30 / 30', reason: 'Registratsiya yangilandi 12:04' },
  { id: 'trunk-beeline', label: 'Trunk: Beeline SIP', level: 'warn', value: '182 ms', reason: 'Qualify kechikishi 150 ms dan oshdi' },
  { id: 'disk', label: 'Disk (yozuvlar)', level: 'crit', value: '94%', reason: '5,8 GB qoldi — taxminan 2 kunlik yozuv' },
];

export type ExtRow = { num: string; name: string; dept: string; status: Status; device: string; calls: number };
const people = [
  ['Dilnoza Karimova', 'Sotuv'], ['Bekzod Rahimov', 'Sotuv'], ['Shahzoda Usmonova', 'Texnik yordam'], ['Gʻayrat Toʻxtayev', 'Ombor'],
  ['Oʻlmasbek Yoqubov', 'Texnik yordam'], ['Malika Ergasheva', 'Buxgalteriya'], ['Javohir Qodirov', 'Sotuv'], ['Nodira Saidova', 'Kadrlar'],
  ['Sardor Nazarov', 'Texnik yordam'], ['Kamola Ahmedova', 'Buxgalteriya'], ['Akmal Murodov', 'Ombor'], ['Feruza Xolmatova', 'Sotuv'],
  ['Ravshan Aliyev', 'Rahbariyat'], ['Zilola Hamidova', 'Qabulxona'],
] as const;
const statuses: Status[] = ['online', 'online', 'offline', 'online', 'error', 'online', 'disabled', 'online', 'online', 'offline', 'online', 'online', 'online', 'online'];
const devices = ['Yealink T54W', 'Softfon (brauzer)', 'Grandstream GRP2612', 'Fanvil X4U', 'Zoiper · Android'];
export const extensions: ExtRow[] = people.map(([name, dept], i) => ({
  num: String(101 + i * (i > 6 ? 3 : 1)),
  name,
  dept,
  status: statuses[i] ?? 'online',
  device: devices[i % devices.length] ?? '',
  calls: (i * 37 + 11) % 64,
}));

export const trunks = [
  { id: 'uztel', name: 'Uztelecom', host: 'sip.uztelecom.uz', status: 'online' as Status, channels: '30' },
  { id: 'beeline', name: 'Beeline SIP', host: '10.40.2.11', status: 'online' as Status, channels: '20' },
  { id: 'ucell', name: 'Ucell zaxira', host: 'pbx.ucell.uz', status: 'offline' as Status, channels: '10' },
];

const LOG_SRC = [
  ['VERBOSE', 'pjsip/101-00000a3f', 'Executing [600@acme-from-internal:1] Queue("sotuv,t,,,180")'],
  ['NOTICE', 'res_pjsip_registrar', 'Contact 102/sip:102@192.168.10.24:5060 qualified, RTT 4.112 ms'],
  ['WARNING', 'res_pjsip_outbound', 'Trunk beeline: qualify RTT 182 ms (limit 150 ms)'],
  ['VERBOSE', 'app_queue', 'Agent PJSIP/acme-101 answered call on queue sotuv after 7 s'],
  ['ERROR', 'res_pjsip', "Failed to authenticate 'admin' from 185.243.5.18:5071 — 403 Forbidden"],
  ['DEBUG', 'chan_pjsip', 'Codec negotiation: offer [opus,g722,alaw], chosen opus/48000'],
  ['VERBOSE', 'pbx', 'Dialplan reloaded — revision r142, 1 286 extensions, 0 warnings'],
  ['NOTICE', 'cdr', 'CDR batch written: 24 records'],
] as const;

export function makeLog(i: number): LogLine {
  const s = LOG_SRC[i % LOG_SRC.length]!;
  const sec = 4 * 3600 + 12 * 60 + i * 3;
  const ts = `${String(10 + Math.floor(sec / 3600) % 24).padStart(2, '0')}:${String(Math.floor(sec / 60) % 60).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}.${String((i * 137) % 1000).padStart(3, '0')}`;
  return { id: i, ts, level: s[0], source: s[1], text: s[2] };
}

/** Brauzerda yaratilgan qisqa WAV (qo'ng'iroq ohangi) — tashqi fayl kerak emas. */
export function makeToneUrl(seconds = 9): string {
  const rate = 8000;
  const n = rate * seconds;
  const buf = new ArrayBuffer(44 + n * 2);
  const v = new DataView(buf);
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, 'data'); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const t = i / rate;
    const on = t % 3 < 1 ? 1 : 0; // 1 s ohang, 2 s jimlik — ringback ritmi
    const s = on * 0.25 * (Math.sin(2 * Math.PI * 425 * t) + 0.4 * Math.sin(2 * Math.PI * 850 * t));
    v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, s)) * 32767, true);
  }
  return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }));
}
