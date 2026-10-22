import type { ExpressionSpecification } from 'maplibre-gl';
import type { RiskLevel } from '../../api/types';
import { colorOf } from '../../lib/risk';

export interface Seg {
  from_frac: number;
  level: RiskLevel;
}

const HIDDEN = 'rgba(0,0,0,0)';

/**
 * `line-gradient` step expression over `line-progress`, one stop per segment start.
 * `progress` < 1 hides the undrawn tail (used by the draw-in animation).
 * Stops are strictly ascending; duplicate or non-increasing stops are skipped.
 */
export function riskGradient(segments: Seg[], progress = 1): ExpressionSpecification {
  const first = segments[0];
  const expr: unknown[] = ['step', ['line-progress'], first ? colorOf(first.level) : HIDDEN];
  let lastStop = 0;
  for (const s of segments.slice(1)) {
    if (s.from_frac >= progress) break;
    if (s.from_frac > lastStop) {
      expr.push(s.from_frac, colorOf(s.level));
      lastStop = s.from_frac;
    }
  }
  if (progress < 1) {
    const stop = Math.max(progress, 1e-6);
    if (stop > lastStop) expr.push(stop, HIDDEN);
  }
  if (expr.length === 3) {
    // A step expression needs at least one stop; repeat the base colour at the end.
    expr.push(1, expr[2]);
  }
  return expr as ExpressionSpecification;
}

/** The stop values of a gradient expression (for tests). */
export function gradientStops(expr: ExpressionSpecification): number[] {
  const parts = expr as unknown[];
  const stops: number[] = [];
  for (let i = 3; i < parts.length; i += 2) stops.push(parts[i] as number);
  return stops;
}
