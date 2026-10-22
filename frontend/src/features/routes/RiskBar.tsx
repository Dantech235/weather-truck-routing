import type { Metrics, RiskLevel } from '../../api/types';
import { formatMiles } from '../../lib/format';
import { colorOf, labelOf } from '../../lib/risk';

const BUCKETS: [RiskLevel, keyof Metrics][] = [
  ['LOW', 'low_miles'],
  ['MODERATE', 'moderate_miles'],
  ['HIGH', 'high_miles'],
  ['SEVERE', 'severe_miles'],
  ['NO_TRAVEL', 'no_travel_miles'],
  ['UNKNOWN', 'unknown_miles'],
];

export function riskBarParts(metrics: Metrics): { level: RiskLevel; miles: number; pct: number }[] {
  const parts = BUCKETS.map(([level, key]) => ({ level, miles: Number(metrics[key]) || 0 }));
  const total = parts.reduce((s, p) => s + p.miles, 0);
  return parts
    .filter((p) => p.miles > 0)
    .map((p) => ({ ...p, pct: total > 0 ? (p.miles / total) * 100 : 0 }));
}

export function RiskBar({ metrics }: { metrics: Metrics }) {
  const parts = riskBarParts(metrics);
  const summary = parts.map((p) => `${labelOf(p.level)} ${formatMiles(p.miles)}`).join(', ');
  return (
    <div>
      <div
        className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
        role="img"
        aria-label={`Miles by risk level: ${summary}`}
      >
        {parts.map((p) => (
          <div
            key={p.level}
            className="h-full"
            style={{ width: `${p.pct}%`, backgroundColor: colorOf(p.level) }}
            title={`${labelOf(p.level)}: ${formatMiles(p.miles)}`}
          />
        ))}
      </div>
    </div>
  );
}
