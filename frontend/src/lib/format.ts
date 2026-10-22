import { formatInTimeZone } from 'date-fns-tz';

/** Format a duration in seconds as "6h 40m" (or "25 min" under an hour). */
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  if (h === 0) return `${m} min`;
  return `${h}h ${String(m).padStart(2, '0')}m`;
}

export function formatMiles(miles: number, digits = 1): string {
  return `${miles.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} mi`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

/** Local time with time-zone abbreviation, e.g. "Thu 2:39 PM CDT". */
export function formatLocalTime(iso: string, timeZone: string = browserTimeZone()): string {
  return formatInTimeZone(new Date(iso), timeZone, 'EEE h:mm a zzz');
}

export function formatLocalDateTime(iso: string, timeZone: string = browserTimeZone()): string {
  return formatInTimeZone(new Date(iso), timeZone, 'EEE MMM d, h:mm a zzz');
}

/** Value for <input type="datetime-local"> (local wall time, minutes precision). */
export function toDateTimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

/** Now, rounded up to the next 15-minute boundary. */
export function nextQuarterHour(now: Date = new Date()): Date {
  const d = new Date(now);
  d.setSeconds(0, 0);
  const rem = d.getMinutes() % 15;
  if (rem !== 0 || now.getSeconds() > 0 || now.getMilliseconds() > 0) {
    d.setMinutes(d.getMinutes() + (15 - rem));
  }
  return d;
}

/** Parse "45,000" → 45000; returns NaN for empty/invalid input. */
export function parseThousands(value: string): number {
  const digits = value.replace(/[^\d]/g, '');
  return digits ? Number(digits) : Number.NaN;
}

export function formatThousands(value: string): string {
  const n = parseThousands(value);
  return Number.isNaN(n) ? '' : n.toLocaleString('en-US');
}
