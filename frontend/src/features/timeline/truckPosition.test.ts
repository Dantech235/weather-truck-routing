import { describe, expect, it } from 'vitest';
import type { Route } from '../../api/types';
import { cumulativeDistances, type LonLat } from '../../lib/geo';
import { buildTrack, mileAt, truckPosition } from './truckPosition';

const coords: LonLat[] = [
  [0, 0],
  [1, 0],
  [2, 0],
];
const geomLen = cumulativeDistances(coords)[2] ?? 0;
const T0 = Date.parse('2026-10-22T13:00:00Z');
const H = 3_600_000;

const cp = (index: number, mile: number, hours: number) => ({
  index,
  mile,
  lat: 0,
  lon: 0,
  eta_utc: new Date(T0 + hours * H).toISOString(),
  elapsed_s: hours * 3600,
  eta_method: 'guidance' as const,
  weather: { wind_mph: 0, gust_mph: 0, rain_in_hr: 0, snow_in_hr: 0, forecast_hour_utc: null },
  risk: {
    level: 'LOW' as const,
    wind: null,
    rain: null,
    snow: null,
    drivers: [],
    load_rule_applied: null,
  },
});

const route = {
  label: 'A',
  distance_mi: 100,
  departure_utc: new Date(T0).toISOString(),
  arrival_utc: new Date(T0 + 4 * H).toISOString(),
  checkpoints: [cp(0, 0, 0), cp(1, 25, 1), cp(2, 50, 3), cp(3, 100, 4)],
} as unknown as Route;

const track = buildTrack(route, coords);

describe('truckPosition', () => {
  it('sits at the origin before departure', () => {
    const p = truckPosition(track, T0 - H);
    expect(p.state).toBe('before');
    expect(p.position).toEqual([0, 0]);
  });

  it('interpolates (eta, mile) pairs during the trip', () => {
    expect(mileAt(track, T0 + 0.5 * H)).toBeCloseTo(12.5);
    expect(mileAt(track, T0 + 2 * H)).toBeCloseTo(37.5); // slow stretch 25→50 over 2 h
    const p = truckPosition(track, T0 + 3.5 * H);
    expect(p.state).toBe('moving');
    expect(p.mile).toBeCloseTo(75);
    // 75 route miles → 75% of the geometry, scaled to geometry miles
    expect(p.position[0]).toBeCloseTo(1.5, 3);
    expect(track.scale).toBeCloseTo(geomLen / 100);
  });

  it('parks at the destination with an Arrived state', () => {
    const p = truckPosition(track, T0 + 10 * H);
    expect(p.state).toBe('arrived');
    expect(p.position).toEqual([2, 0]);
    expect(p.mile).toBe(100);
  });
});
