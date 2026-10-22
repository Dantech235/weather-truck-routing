import { describe, expect, it } from 'vitest';
import {
  formatDuration,
  formatLocalTime,
  formatMiles,
  formatThousands,
  nextQuarterHour,
  parseThousands,
  toDateTimeLocalValue,
} from './format';

describe('formatDuration', () => {
  it('formats sub-hour durations in minutes', () => {
    expect(formatDuration(25 * 60)).toBe('25 min');
  });
  it('formats hours with zero-padded minutes', () => {
    expect(formatDuration(6 * 3600 + 5 * 60)).toBe('6h 05m');
  });
});

describe('local time with time zone', () => {
  it('shows the zone abbreviation', () => {
    expect(formatLocalTime('2026-10-22T19:39:00Z', 'America/Chicago')).toBe('Thu 2:39 PM CDT');
    expect(formatLocalTime('2026-12-22T19:39:00Z', 'America/Denver')).toBe('Tue 12:39 PM MST');
  });
});

describe('numbers', () => {
  it('miles and thousands', () => {
    expect(formatMiles(1234.56)).toBe('1,234.6 mi');
    expect(parseThousands('45,000 lb')).toBe(45000);
    expect(parseThousands('')).toBeNaN();
    expect(formatThousands('45000')).toBe('45,000');
    expect(formatThousands('abc')).toBe('');
  });
});

describe('departure default', () => {
  it('rounds up to the next quarter hour', () => {
    expect(nextQuarterHour(new Date(2026, 9, 22, 10, 7, 30)).getMinutes()).toBe(15);
    expect(nextQuarterHour(new Date(2026, 9, 22, 10, 45, 0, 0)).getMinutes()).toBe(45);
    expect(nextQuarterHour(new Date(2026, 9, 22, 10, 50)).getHours()).toBe(11);
  });
  it('formats datetime-local values', () => {
    expect(toDateTimeLocalValue(new Date(2026, 0, 5, 7, 3))).toBe('2026-01-05T07:03');
  });
});
