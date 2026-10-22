import clsx from 'clsx';
import type { Route } from '../../api/types';
import { CountUp } from '../../animations/CountUp';
import { formatDuration, formatLocalTime, formatMiles } from '../../lib/format';
import { useUIStore } from '../../store/ui';
import { LevelChip } from './LevelChip';
import { RiskBar } from './RiskBar';

const WARNING_TEXT: Record<string, string> = {
  LOW_FORECAST_COVERAGE: 'Forecast covers less than 80% of this route.',
};

interface Props {
  route: Route;
  recommended: boolean;
}

export function RouteCard({ route, recommended }: Props) {
  const selected = useUIStore((s) => s.selectedRoute === route.label);
  const selectRoute = useUIStore((s) => s.selectRoute);
  const hoverRoute = useUIStore((s) => s.hoverRoute);
  const m = route.metrics;
  const sentence = route.reason ?? route.lost_because;

  return (
    <button
      type="button"
      data-route-card={route.label}
      aria-pressed={selected}
      onClick={() => selectRoute(route.label)}
      onMouseEnter={() => hoverRoute(route.label)}
      onMouseLeave={() => hoverRoute(null)}
      onFocus={() => hoverRoute(route.label)}
      onBlur={() => hoverRoute(null)}
      className={clsx(
        'route-card w-full rounded-card border p-4 text-left shadow-card transition-[border-color,box-shadow,background-color] duration-200',
        selected
          ? 'border-accent/60 bg-white ring-2 ring-accent/25 dark:border-accent-soft/60 dark:bg-white/[0.07] dark:ring-accent-soft/25'
          : 'border-slate-200/80 bg-white hover:border-slate-300 hover:shadow-float dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-white/20',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-900 text-sm font-bold text-white dark:bg-white dark:text-slate-900">
            {route.label}
          </span>
          <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Rank {route.rank}
          </span>
          {recommended && (
            <span
              className="recommended-badge relative inline-block rounded-full bg-gradient-to-r from-accent to-blue-600 px-2.5 py-0.5 text-xs font-semibold text-white shadow-glow"
              data-testid="recommended-badge"
            >
              <span
                className="badge-glow pointer-events-none absolute inset-0 rounded-full bg-accent opacity-0"
                aria-hidden
              />
              <span className="relative">✓ Recommended</span>
            </span>
          )}
        </div>
        <LevelChip level={m.max_level} />
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-2 text-sm tabular-nums">
        <div>
          <dt className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Distance
          </dt>
          <dd className="text-[15px] font-semibold tracking-tight">
            <CountUp value={route.distance_mi} format={(n) => formatMiles(n)} />
          </dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Duration
          </dt>
          <dd className="text-[15px] font-semibold tracking-tight">
            <CountUp value={route.travel_time_s} format={formatDuration} />
          </dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Arrives
          </dt>
          <dd className="text-[15px] font-semibold tracking-tight">
            {formatLocalTime(route.arrival_utc)}
          </dd>
        </div>
      </dl>

      <div className="mt-3">
        <RiskBar metrics={m} />
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-600 tabular-nums dark:text-slate-400">
          <span>Severe {m.severe_miles.toFixed(1)} mi</span>
          <span>High {m.high_miles.toFixed(1)} mi</span>
          {m.no_travel_miles > 0 && <span>No Travel {m.no_travel_miles.toFixed(1)} mi</span>}
          <span>
            Avg risk{' '}
            {m.avg_risk === null ? (
              'n/a'
            ) : (
              <CountUp value={m.avg_risk} format={(n) => n.toFixed(2)} />
            )}
          </span>
        </div>
      </div>

      {sentence && (
        <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
          {route.reason ? '' : 'Lost: '}
          {sentence}
        </p>
      )}
      {route.warnings.map((w) => (
        <p key={w} className="mt-2 text-xs font-medium text-amber-700 dark:text-amber-400">
          ⚠ {WARNING_TEXT[w] ?? w}
        </p>
      ))}
    </button>
  );
}
