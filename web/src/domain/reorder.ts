/** Ro'yxatda elementni ko'chiradi (yangi massiv). Chegaradan tashqari indeks — o'zgarishsiz nusxa. */
export function moveItem<T>(list: readonly T[], from: number, to: number): T[] {
  const copy = [...list];
  if (from < 0 || from >= list.length || to < 0 || to >= list.length) return copy;
  const [item] = copy.splice(from, 1) as [T];
  copy.splice(to, 0, item);
  return copy;
}
