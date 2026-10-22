import { describe, expect, it } from 'vitest';
import { boundsOf, cumulativeDistances, haversineMi, pointAtDistance, type LonLat } from './geo';

const LINE: LonLat[] = [
  [0, 0],
  [1, 0],
  [2, 0],
];

describe('geo', () => {
  it('haversine ≈ 69.1 mi per degree at the equator', () => {
    expect(haversineMi([0, 0], [1, 0])).toBeCloseTo(69.09, 1);
  });
  it('pointAtDistance interpolates and clamps', () => {
    const cum = cumulativeDistances(LINE);
    expect(cum[0]).toBe(0);
    const p = pointAtDistance(LINE, cum, (cum[2] ?? 0) * 0.75);
    expect(p[0]).toBeCloseTo(1.5, 6);
    expect(pointAtDistance(LINE, cum, -3)).toEqual([0, 0]);
    expect(pointAtDistance(LINE, cum, 1e6)).toEqual([2, 0]);
    expect(() => pointAtDistance([], [], 1)).toThrow();
  });
  it('boundsOf', () => {
    expect(boundsOf([LINE, [[-1, 3]]])).toEqual([
      [-1, 0],
      [2, 3],
    ]);
    expect(boundsOf([])).toBeNull();
  });
});
