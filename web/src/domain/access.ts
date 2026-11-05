// Sof validatsiya mantiqi — Kirish (SSH va veb-panel), M12 B4. `src/api/fake.ts` (netd'ni simulyatsiya
// qiladi) va `src/screens/access/*` shu yerdan foydalanadi — qoida bitta joyda yashaydi (dryer),
// `domain/firewall.ts` bilan bir xil naqsh.
import { MAX_TIMEOUT_S, MIN_TIMEOUT_S } from '@/domain/firewall';
import type { AccessFieldError, AccessRootLogin, AccessSshApplyIn, AccessSshOut, AccessWebApplyIn } from '@/api/types';

const RESERVED_SINGLE_PORTS = new Set([5060, 5061, 5038, 8088, 5432, 8710, 8711, 8712]);
const RESERVED_RANGE = { min: 10000, max: 20000 };

/** `timeout_s` ko'rsatilmaganda — firewall sahifasidagi sukut qiymat bilan bir xil (`firewallDraft.ts::DEFAULT_TIMEOUT_S`). */
export const ACCESS_DEFAULT_TIMEOUT_S = 120;

/** Tasdiqlash muddati tanlagichidagi variantlar — `firewallDraft.ts::TIMEOUT_OPTIONS` bilan bir xil, lekin
 *  qasddan alohida (ekranlar orasida keraksiz bog'liqlikni oldini olish — `ConfirmApplyModal.tsx` izohi). */
export const ACCESS_TIMEOUT_OPTIONS = [60, 120, 300, 600] as const;

/** Boshqa xizmatlar uchun band portlar (SIP, RTP, Postgres va h.k.) — bu yerga veb-panel/SSH ni qo'yib bo'lmaydi. */
export function isReservedPort(port: number): boolean {
  return RESERVED_SINGLE_PORTS.has(port) || (port >= RESERVED_RANGE.min && port <= RESERVED_RANGE.max);
}

function validatePortField(field: string, port: number, errors: AccessFieldError[]): void {
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    errors.push({ field, message: "1..65535 oralig'ida butun son bo'lishi kerak" });
    return;
  }
  if (isReservedPort(port)) errors.push({ field, message: `Bu port boshqa xizmat uchun band: ${port}` });
}

function validateTimeout(timeoutS: number | undefined, errors: AccessFieldError[]): void {
  if (timeoutS === undefined) return;
  if (!Number.isInteger(timeoutS) || timeoutS < MIN_TIMEOUT_S || timeoutS > MAX_TIMEOUT_S) {
    errors.push({ field: 'timeout_s', message: `${MIN_TIMEOUT_S}..${MAX_TIMEOUT_S} oralig'ida butun son bo'lishi kerak` });
  }
}

/** Mijoz-tomoni tezkor tekshiruv — backend bilan bir xil qoidalar (serverga yuborishdan oldin tezkor fikr). */
export function validateSshApply(payload: AccessSshApplyIn): AccessFieldError[] {
  const errors: AccessFieldError[] = [];
  validatePortField('port', payload.port, errors);
  validateTimeout(payload.timeout_s, errors);
  return errors;
}

export function validateWebApply(payload: AccessWebApplyIn): AccessFieldError[] {
  const errors: AccessFieldError[] = [];
  validatePortField('http_port', payload.http_port, errors);
  validatePortField('https_port', payload.https_port, errors);
  if (payload.http_port === payload.https_port) {
    errors.push({ field: 'https_port', message: "HTTP va HTTPS port bir xil bo'lmasligi kerak" });
  }
  validateTimeout(payload.timeout_s, errors);
  return errors;
}

/** Kirish yo'riqnomasidagi nusxalanadigan buyruq — `ssh -p <port> <login>@<hostname>`. */
export function buildSshLoginCommand(port: number, user: string, hostname: string): string {
  return `ssh -p ${port} ${user}@${hostname}`;
}

/** Root bevosita kirish yopiq bo'lsa — "kirgach sudo -i" eslatmasini ko'rsatish kerak bo'lgan holatlar. */
export function showRootLoginNote(rootLogin: AccessRootLogin | null): boolean {
  return rootLogin === 'no' || rootLogin === 'prohibit-password';
}

/** SSH orqali kim bilan kirish kerak: oddiy foydalanuvchi (ISO: innova), bo'lmasa — root (Proxmox LXC shablonlari). */
export function sshLoginUser(ssh: AccessSshOut): string {
  return ssh.login_users[0] ?? 'root';
}

/**
 * Login buyrug'i ostidagi maslahat: `sudo` — oddiy foydalanuvchi bor, root yopiq (kirgach sudo -i);
 * `no-login` — oddiy foydalanuvchi yo'q va root parol bilan kira olmaydi (Debian/LXC sukuti `prohibit-password`;
 * `null` = sshd -T ishlamadi va sozlamada yo'q → OpenSSH sukuti ham shu) — konsoldan tuzatish kerak.
 */
export function sshLoginAdvice(ssh: AccessSshOut): 'sudo' | 'no-login' | null {
  if (ssh.login_users.length === 0) return ssh.root_login === 'yes' ? null : 'no-login';
  return showRootLoginNote(ssh.root_login) ? 'sudo' : null;
}

/** Proxmox konsolida (pct enter <ID>) root parol bilan kirishni yoqish — Debian 12 sshd_config.d ni boshida o'qiydi. */
export const ROOT_LOGIN_FIX_COMMAND =
  "echo 'PermitRootLogin yes' > /etc/ssh/sshd_config.d/10-innova-root.conf && systemctl restart ssh";

/** sshd ishlamayapti yoki e'lon qilingan port hech qaysi tinglanayotgan portda yo'q — aniq ogohlantirish kerak. */
export function sshNeedsAttention(ssh: AccessSshOut): boolean {
  return !ssh.active || !ssh.listening_ports.includes(ssh.port);
}

type WebAddressParams = { protocol: string; hostname: string; httpPort: number; httpsPort: number };

/** Veb-panel porti o'zgargandan keyin ishlatiladigan manzil (yo'lsiz) — joriy protokolga mos portni tanlaydi,
 *  standart 80/443 bo'lsa porti yozilmaydi. Tasdiqlash modalidagi ogohlantirishda (hali `pending_id` yo'q) va
 *  haqiqiy redirect URL'ida (`buildWebConfirmUrl`) qayta ishlatiladi (dryer). */
export function buildWebAddress(params: WebAddressParams): string {
  const isHttps = params.protocol.replace(':', '') === 'https';
  const scheme = isHttps ? 'https' : 'http';
  const port = isHttps ? params.httpsPort : params.httpPort;
  const standardPort = isHttps ? 443 : 80;
  const portPart = port === standardPort ? '' : `:${port}`;
  return `${scheme}://${params.hostname}${portPart}`;
}

/** Veb-panel porti o'zgargandan keyin brauzer ketadigan to'liq manzil (talab:
 *  `${protocol}//${hostname}:${port}/access-confirm#${id}`). */
export function buildWebConfirmUrl(params: WebAddressParams & { pendingId: string }): string {
  return `${buildWebAddress(params)}/access-confirm#${params.pendingId}`;
}
