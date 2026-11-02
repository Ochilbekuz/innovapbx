import { useEffect, useRef, useState } from 'react';
import { apiClient, useSession } from '@/api';
import type { User } from '@/api/types';
import { getRefreshToken } from '@/api/session';
import { useSetupState } from '@/api/queries';

type SetupInfo = { needed?: boolean } | undefined;

type SessionActions = {
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: User) => void;
  clear: () => void;
};

/**
 * Saqlangan refresh token bilan sessiyani tiklashga urinadi (ko'p bosqichli tarmoq oqimi —
 * `useAuthBootstrap`dan ALOHIDA chiqarilgan, shunda hook'ning o'z murakkabligi past qoladi
 * va bu funksiya alohida sinaladi/o'qiladi — crapper: CC<10 talabi).
 */
async function restoreSession(
  refreshToken: string,
  actions: SessionActions,
  isStillMounted: () => boolean,
): Promise<void> {
  try {
    const tokens = await apiClient.refresh(refreshToken);
    actions.setTokens(tokens.access, tokens.refresh);
    const me = await apiClient.me();
    if (isStillMounted()) actions.setUser(me);
  } catch {
    actions.clear();
  }
}

/** `ready` bayrog'ini hisoblaydi — qaytarish ifodasini hook tanasidan ajratib, CCni kamaytiradi. */
function computeReady(checked: boolean, user: User | null, setup: SetupInfo, setupLoading: boolean, setupError: boolean): boolean {
  if (setupLoading || setupError) return false;
  return checked || !!user || !!setup?.needed;
}

/** Sessiyani tiklashga hojat yo'qligini bildiradi (sehrgar kerak YOKI foydalanuvchi allaqachon bor). */
function sessionAlreadySettled(setup: SetupInfo, user: User | null): boolean {
  return !!setup?.needed || !!user;
}

/**
 * Ilova ochilganda: 1) sehrgar kerakmi tekshiradi, 2) agar saqlangan refresh token bo'lsa — sessiyani tiklaydi.
 * `ready=false` bo'lguncha marshrutlar hech narsa ko'rsatmaydi (pastdan tepaga sakrash bo'lmasin uchun).
 *
 * DIQQAT (sinovda topilgan haqiqiy xato): `refresh` tokenni (zustand reaktiv maydon) effekt
 * bog'liqliklar ro'yxatiga qo'yish CHEKSIZ tsiklga olib kelgan edi — `apiClient.refresh()`
 * HAR safar YANGI (aylantirilgan) refresh token qaytaradi, `setTokens` uni saqlaydi, bu esa
 * `refresh` qiymatini o'zgartiradi -> effekt QAYTA ishga tushadi -> yana `refresh()` chaqiradi...
 * (to'liq sahifa yuklanishida — masalan URL orqali to'g'ridan-to'g'ri o'tishda — cheksiz
 * `/auth/refresh`+`/auth/me` so'rov oqimi, ekran abadiy "yuklanmoqda" holatida qoladi).
 * Tuzatish: boshlang'ich token `getRefreshToken()` (reaktiv BO'LMAGAN getter, xuddi
 * `http.ts`dagidek) bilan BIR MARTA o'qiladi, effekt esa `attempted` ref bilan faqat bir marta
 * ishga tushishi kafolatlanadi.
 *
 * DIQQAT #2 (regressiya testida topilgan): avval "ishlab turgan" promisni bekor qilish uchun
 * effekt ICHIDA e'lon qilingan `let alive = true` + shu EFFEKTNING cleanup'i ishlatilgan edi.
 * Lekin bu cleanup har safar bog'liqliklar RO'YXATIDAGI biror qiymat (masalan `setup` — so'rov
 * natijasi) identifikatori o'zgarganda ham ishga tushadi — real tiklanish davom etayotganida
 * oraliq render yuz bersa, cleanup o'zib ketib `alive`ni erta `false` qilib qo'yadi va
 * `finally` blokidagi `setChecked(true)` BUTUNLAY chaqirilmay qoladi (UI abadiy "tayyor emas"
 * holatida qotib qoladi). Tuzatish: bekor qilish holatini FAQAT komponent HAQIQIY
 * unmount bo'lganda ishga tushadigan alohida, bog'liqliksiz effekt orqali kuzatamiz
 * (`mounted` ref) — ishga tushirish effekti esa endi hech narsani bekor qilmaydi.
 */
export function useAuthBootstrap() {
  const { data: setup, isLoading: setupLoading, isError: setupError } = useSetupState();
  const { user, setTokens, setUser, clear } = useSession();
  const [checked, setChecked] = useState(false);
  const attempted = useRef(false);
  const mounted = useRef(true);

  // DIQQAT (StrictMode'da topilgan): faqat `useRef(true)` boshlang'ich qiymatiga tayanib,
  // effekt TANASIDA qayta `true` qilib qo'ymasak — React StrictMode (dev) effektni
  // "mount -> cleanup -> qayta mount" deb simulyatsiya qilganda cleanup ishga tushib
  // `mounted.current`ni abadiy `false` qilib qo'yadi (garchi komponent HAQIQATDA
  // montaj qilingan bo'lsa ham) — shu sabab bootstrap natijasi hech qachon qo'llanmaydi.
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (setupLoading || setupError) return;
    if (attempted.current) return;
    attempted.current = true;
    if (sessionAlreadySettled(setup, user)) { setChecked(true); return; }
    const initialRefresh = getRefreshToken();
    if (!initialRefresh) { setChecked(true); return; }
    restoreSession(initialRefresh, { setTokens, setUser, clear }, () => mounted.current)
      .finally(() => { if (mounted.current) setChecked(true); });
  }, [setupLoading, setupError, setup, user, setTokens, setUser, clear]);

  return {
    ready: computeReady(checked, user, setup, setupLoading, setupError),
    setupNeeded: !!setup?.needed,
    setupError,
  };
}
