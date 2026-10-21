import { describe, expect, it } from 'vitest';
import { formatDuration } from './format';

describe('formatDuration', () => {
  it('formats sub-hour durations in minutes', () => {
    expect(formatDuration(25 * 60)).toBe('25 min');
  });
  it('formats hours with zero-padded minutes', () => {
    expect(formatDuration(6 * 3600 + 5 * 60)).toBe('6h 05m');
  });
});
