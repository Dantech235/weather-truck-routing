import { describe, expect, it } from 'vitest';
import { clusterArrivals, tickStep } from './ForecastSlider';

describe('tickStep', () => {
  it('labels every 6 h only when nine labels fit', () => {
    expect(tickStep(900)).toBe(6);
    expect(tickStep(600)).toBe(12);
    expect(tickStep(300)).toBe(24);
    expect(tickStep(150)).toBe(48);
  });
});

describe('clusterArrivals', () => {
  it('merges arrivals whose markers would overlap', () => {
    const arrivals = [
      { label: 'B', hour: 12.3 },
      { label: 'A', hour: 12.0 },
      { label: 'C', hour: 12.8 },
    ];
    const narrow = clusterArrivals(arrivals, 240); // 5 px per hour
    expect(narrow).toHaveLength(1);
    expect(narrow[0]?.labels).toEqual(['A', 'B', 'C']);
    const wide = clusterArrivals(arrivals, 4800); // 100 px per hour
    expect(wide.map((c) => c.labels)).toEqual([['A'], ['B'], ['C']]);
  });

  it('places the label at the mean arrival and clamps hours to the track', () => {
    const [c] = clusterArrivals([{ label: 'A', hour: 60 }], 500);
    expect(c?.at).toBe(1);
  });
});
