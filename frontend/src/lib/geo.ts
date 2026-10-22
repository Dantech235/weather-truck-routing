/** Geometry helpers on [lon, lat] coordinates. Distances in miles. */
export type LonLat = [number, number];

const EARTH_RADIUS_MI = 3958.7613;
const toRad = (d: number) => (d * Math.PI) / 180;

export function haversineMi(a: LonLat, b: LonLat): number {
  const dLat = toRad(b[1] - a[1]);
  const dLon = toRad(b[0] - a[0]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function cumulativeDistances(coords: LonLat[]): number[] {
  const out: number[] = [];
  let total = 0;
  let prev: LonLat | undefined;
  for (const c of coords) {
    if (prev) total += haversineMi(prev, c);
    out.push(total);
    prev = c;
  }
  return out;
}

/** Point `d` miles along the line, using precomputed cumulative distances. */
export function pointAtDistance(coords: LonLat[], cumulative: number[], d: number): LonLat {
  const first = coords[0];
  const last = coords[coords.length - 1];
  if (!first || !last) throw new Error('empty line');
  const total = cumulative[cumulative.length - 1] ?? 0;
  if (d <= 0 || coords.length === 1) return first;
  if (d >= total) return last;
  let lo = 0;
  let hi = cumulative.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if ((cumulative[mid] ?? 0) <= d) lo = mid;
    else hi = mid;
  }
  const a = coords[lo] ?? first;
  const b = coords[hi] ?? last;
  const d0 = cumulative[lo] ?? 0;
  const span = (cumulative[hi] ?? d0) - d0;
  const t = span === 0 ? 0 : (d - d0) / span;
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

export type Bounds = [[number, number], [number, number]];

export function boundsOf(lines: LonLat[][]): Bounds | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const line of lines) {
    for (const [x, y] of line) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  return Number.isFinite(minX)
    ? [
        [minX, minY],
        [maxX, maxY],
      ]
    : null;
}
