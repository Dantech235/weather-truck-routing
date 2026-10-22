import { describe, expect, it } from 'vitest';
import type { Heatmap } from '../../../api/types';
import { heatFeatureCollection, heatRadius, heatWeight } from './heatmap';

describe('heatmap layer helpers', () => {
  it('cross-fades between floor(hour) and the next hour', () => {
    expect(heatWeight(2.25)).toEqual([
      '/',
      ['+', ['*', ['get', 'h2'], 0.75], ['*', ['get', 'h3'], 0.25]],
      4,
    ]);
    expect(heatWeight(48)).toEqual([
      '/',
      ['+', ['*', ['get', 'h48'], 1], ['*', ['get', 'h48'], 0]],
      4,
    ]);
  });

  it('builds one feature per point with h0…h48 and an unknown flag', () => {
    const heat = {
      points: [
        [-97, 33],
        [-98, 34],
      ],
      hours: [],
      spacing_mi: 12,
      risk: [Array(49).fill(2), [-1, ...Array(48).fill(1)]],
      wind: [],
      rain: [],
      snow: [],
    } as unknown as Heatmap;
    const fc = heatFeatureCollection(heat);
    expect(fc.features).toHaveLength(2);
    expect(fc.features[0]?.properties).toMatchObject({ h0: 2, h48: 2, unk: false });
    expect(fc.features[1]?.properties).toMatchObject({ h0: 0, h1: 1, unk: true });
  });

  it('scales radius with zoom at base 2', () => {
    const expr = heatRadius(12, 0) as unknown[];
    const r0 = expr[4] as number;
    expect(expr[expr.length - 1]).toBeCloseTo(r0 * 2 ** 22);
    expect(r0).toBeGreaterThan(0);
  });
});
