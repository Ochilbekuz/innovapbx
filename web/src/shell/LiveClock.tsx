import { useEffect, useState } from 'react';
import { useSession } from '@/api/session';
import { clockParts, tenantTz, tzOffsetLabel } from '@/lib/time';

/** Har `ms` da yangilanadigan joriy lahza; unmount bo'lganda taymer to'xtaydi. */
function useNow(ms: number): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

/**
 * Yuqori paneldagi jonli soat — tizim (PBX) vaqt zonasida, brauzer zonasida emas.
 * Zona «Sana va vaqt» sahifasida o'zgarsa sessiya yangilanadi va soat darhol yangi zonaga o'tadi.
 */
export function LiveClock() {
  const tz = useSession((s) => s.user?.timezone) || tenantTz();
  const now = useNow(1000);
  const { date, time } = clockParts(now, tz);
  return (
    <time
      role="timer"
      dateTime={now.toISOString()}
      title={tz}
      className="num hidden h-ctl-md items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 text-sm lg:inline-flex"
    >
      <span className="text-muted">{date}</span>
      <span className="font-medium text-fg">{time}</span>
      <span className="text-muted">{tzOffsetLabel(now.toISOString(), tz)}</span>
    </time>
  );
}
