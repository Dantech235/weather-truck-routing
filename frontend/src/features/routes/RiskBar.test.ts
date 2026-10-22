import { describe, expect, it } from 'vitest';
import type { Metrics } from '../../api/types';
import { riskBarParts } from './RiskBar';

describe('riskBarParts', () => {
  it('drops empty buckets and sums to 100%', () => {
    const m: Metrics = {
      no_travel_miles: 0,
      severe_miles: 12.5,
      high_miles: 25,
      moderate_miles: 0,
      low_miles: 62.5,
      unknown_miles: 0,
      avg_risk: 0.9,
      max_level: 'SEVERE',
    };
    const parts = riskBarParts(m);
    expect(parts.map((p) => p.level)).toEqual(['LOW', 'HIGH', 'SEVERE']);
    expect(parts.reduce((s, p) => s + p.pct, 0)).toBeCloseTo(100);
  });
});
