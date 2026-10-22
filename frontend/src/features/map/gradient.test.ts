import { describe, expect, it } from 'vitest';
import { DEFAULT_COLORS } from '../../lib/risk';
import { gradientStops, riskGradient, type Seg } from './gradient';

const SEGS: Seg[] = [
  { from_frac: 0, level: 'LOW' },
  { from_frac: 0.25, level: 'HIGH' },
  { from_frac: 0.25, level: 'SEVERE' }, // duplicate stop → skipped
  { from_frac: 0.6, level: 'MODERATE' },
  { from_frac: 0.9, level: 'UNKNOWN' },
];

const ascending = (xs: number[]) => xs.every((x, i) => i === 0 || x > (xs[i - 1] ?? -1));

describe('riskGradient', () => {
  it('full progress: one stop per segment start, strictly ascending', () => {
    const expr = riskGradient(SEGS, 1);
    expect(expr.slice(0, 3)).toEqual(['step', ['line-progress'], DEFAULT_COLORS.LOW]);
    expect(gradientStops(expr)).toEqual([0.25, 0.6, 0.9]);
    expect(ascending(gradientStops(expr))).toBe(true);
    expect(expr).toContain(DEFAULT_COLORS.HIGH);
    expect(expr).not.toContain(DEFAULT_COLORS.SEVERE);
  });

  it('half progress hides the undrawn tail', () => {
    const expr = riskGradient(SEGS, 0.5);
    expect(gradientStops(expr)).toEqual([0.25, 0.5]);
    expect(expr[expr.length - 1]).toBe('rgba(0,0,0,0)');
  });

  it('zero progress hides everything after a tiny epsilon', () => {
    const expr = riskGradient(SEGS, 0);
    expect(gradientStops(expr)).toEqual([1e-6]);
    expect(ascending(gradientStops(expr))).toBe(true);
  });

  it('single segment still yields a valid step expression', () => {
    const expr = riskGradient([{ from_frac: 0, level: 'SEVERE' }], 1);
    expect(expr).toEqual([
      'step',
      ['line-progress'],
      DEFAULT_COLORS.SEVERE,
      1,
      DEFAULT_COLORS.SEVERE,
    ]);
  });
});
