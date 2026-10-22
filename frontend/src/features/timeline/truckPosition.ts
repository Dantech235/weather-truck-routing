import type { Route } from '../../api/types';
import { cumulativeDistances, pointAtDistance, type LonLat } from '../../lib/geo';

export type TruckState = 'before' | 'moving' | 'arrived';

export interface TruckTrack {
  label: string;
  coords: LonLat[];
  cumulative: number[];
  /** Geometry miles per route mile (display geometry vs provider distance). */
  scale: number;
  times: number[]; // checkpoint ETAs, epoch ms, non-decreasing
  miles: number[]; // checkpoint route miles
  departMs: number;
  arriveMs: number;
}

export interface TruckPosition {
  label: string;
  position: LonLat;
  mile: number;
  state: TruckState;
}

/** Precompute once per plan. */
export function buildTrack(route: Route, coords: LonLat[]): TruckTrack {
  const cumulative = cumulativeDistances(coords);
  const geomLen = cumulative[cumulative.length - 1] ?? 0;
  const times = route.checkpoints.map((c) => Date.parse(c.eta_utc));
  const miles = route.checkpoints.map((c) => c.mile);
  return {
    label: route.label,
    coords,
    cumulative,
    scale: route.distance_mi > 0 ? geomLen / route.distance_mi : 1,
    times,
    miles,
    departMs: Date.parse(route.departure_utc),
    arriveMs: Date.parse(route.arrival_utc),
  };
}

/** Mile reached at time t by interpolating checkpoint (eta, mile) pairs. */
export function mileAt(track: TruckTrack, tMs: number): number {
  const { times, miles } = track;
  const n = times.length;
  if (n === 0) return 0;
  if (tMs <= (times[0] ?? 0)) return miles[0] ?? 0;
  if (tMs >= (times[n - 1] ?? 0)) return miles[n - 1] ?? 0;
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if ((times[mid] ?? 0) <= tMs) lo = mid;
    else hi = mid;
  }
  const t0 = times[lo] ?? 0;
  const t1 = times[hi] ?? t0;
  const m0 = miles[lo] ?? 0;
  const m1 = miles[hi] ?? m0;
  return t1 === t0 ? m1 : m0 + ((m1 - m0) * (tMs - t0)) / (t1 - t0);
}

export function truckPosition(track: TruckTrack, tMs: number): TruckPosition {
  const first = track.coords[0] ?? [0, 0];
  const last = track.coords[track.coords.length - 1] ?? first;
  if (tMs < track.departMs) {
    return { label: track.label, position: first, mile: 0, state: 'before' };
  }
  if (tMs >= track.arriveMs) {
    return {
      label: track.label,
      position: last,
      mile: track.miles[track.miles.length - 1] ?? 0,
      state: 'arrived',
    };
  }
  const mile = mileAt(track, tMs);
  return {
    label: track.label,
    position: pointAtDistance(track.coords, track.cumulative, mile * track.scale),
    mile,
    state: 'moving',
  };
}
