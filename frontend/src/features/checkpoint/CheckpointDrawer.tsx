import { useEffect, useRef } from 'react';
import type { Checkpoint, Plan } from '../../api/types';
import { formatDuration, formatLocalDateTime, formatLocalTime } from '../../lib/format';
import { useUIStore } from '../../store/ui';
import { LevelChip } from '../routes/LevelChip';

export function findCheckpoint(plan: Plan, route: string, index: number): Checkpoint | undefined {
  return plan.routes.find((r) => r.label === route)?.checkpoints.find((c) => c.index === index);
}

const COMPONENT_LABELS = { wind: 'Wind', rain: 'Rain', snow: 'Snow' } as const;

const fmt = (v: number | null | undefined, digits: number, unit: string) =>
  v === null || v === undefined ? '—' : `${v.toFixed(digits)} ${unit}`;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

export function CheckpointDrawer({ plan }: { plan: Plan }) {
  const selected = useUIStore((s) => s.selectedCheckpoint);
  const close = useUIStore((s) => s.selectCheckpoint);
  const closeRef = useRef<HTMLButtonElement>(null);
  const cp = selected ? findCheckpoint(plan, selected.route, selected.index) : undefined;

  useEffect(() => {
    if (!cp) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cp, close]);

  if (!cp || !selected) return null;
  const w = cp.weather;
  const r = cp.risk;

  return (
    <aside
      role="dialog"
      aria-modal="false"
      aria-labelledby="cp-title"
      data-testid="checkpoint-drawer"
      className="checkpoint-drawer absolute inset-y-0 right-0 z-30 w-full max-w-sm overflow-y-auto border-l border-slate-200 bg-white p-5 shadow-lg dark:border-slate-800 dark:bg-slate-950"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-slate-500">Route {selected.route}</p>
          <h2 id="cp-title" className="text-lg font-semibold tabular-nums">
            Mile {cp.mile.toFixed(1)}
          </h2>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={() => close(null)}
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 focus-visible:outline-accent dark:hover:bg-slate-800"
          aria-label="Close checkpoint details"
        >
          ✕
        </button>
      </div>

      <div className="drawer-content">
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <LevelChip level={r.level} />
          {r.drivers.length > 0 && r.level !== 'UNKNOWN' && (
            <span className="text-sm text-slate-600 dark:text-slate-400">
              driven by {r.drivers.join(', ')}
            </span>
          )}
        </div>

        {r.load_rule_applied && (
          <p className="mt-3 rounded-card border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900">
            <span className="block text-xs font-medium text-slate-500">Load rule applied</span>
            {r.load_rule_applied}
          </p>
        )}

        <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Arrival
        </h3>
        <dl className="text-sm">
          <Row label="ETA">{formatLocalDateTime(cp.eta_utc)}</Row>
          <Row label="Elapsed">{formatDuration(cp.elapsed_s)}</Row>
          <Row label="ETA method">
            {cp.eta_method === 'guidance' ? 'Route guidance' : 'Proportional'}
          </Row>
        </dl>

        <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Weather at ETA
        </h3>
        <dl className="text-sm">
          <Row label="Wind (sustained)">{fmt(w.wind_mph, 1, 'mph')}</Row>
          <Row label="Gusts (shown, not scored)">{fmt(w.gust_mph, 1, 'mph')}</Row>
          <Row label="Rain">{fmt(w.rain_in_hr, 2, 'in/hr')}</Row>
          <Row label="Snow">{fmt(w.snow_in_hr, 2, 'in/hr')}</Row>
          <Row label="Forecast hour used">
            {w.forecast_hour_utc ? formatLocalTime(w.forecast_hour_utc) : '—'}
          </Row>
        </dl>

        <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Component levels
        </h3>
        <dl className="text-sm">
          {(['wind', 'rain', 'snow'] as const).map((k) => (
            <Row key={k} label={COMPONENT_LABELS[k]}>
              {r[k] ? <LevelChip level={r[k]} /> : '—'}
            </Row>
          ))}
        </dl>
        {r.level === 'UNKNOWN' && (
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
            No forecast is available for this checkpoint at its ETA. It is not treated as Low.
          </p>
        )}
      </div>
    </aside>
  );
}
