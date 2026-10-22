import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { useEffect, useRef } from 'react';
import { MOTION, withMotion } from '../../animations/timelines';
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
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

export function CheckpointDrawer({ plan }: { plan: Plan }) {
  const selected = useUIStore((s) => s.selectedCheckpoint);
  const close = useUIStore((s) => s.selectCheckpoint);
  const closeRef = useRef<HTMLButtonElement>(null);
  const cp = selected ? findCheckpoint(plan, selected.route, selected.index) : undefined;
  const asideRef = useRef<HTMLElement>(null);
  const wasOpen = useRef(false);
  const openKey = cp && selected ? `${selected.route}:${selected.index}` : null;

  // Slide in from the right when opening; re-stagger the content when the checkpoint changes.
  useGSAP(
    () => {
      const el = asideRef.current;
      if (!openKey || !el) {
        wasOpen.current = false;
        return;
      }
      const opening = !wasOpen.current;
      wasOpen.current = true;
      const mm = withMotion((reduce) => {
        if (reduce) return;
        if (opening) {
          gsap.from(el, {
            xPercent: 100,
            duration: MOTION.drawer,
            ease: 'power3.out',
            clearProps: 'transform',
          });
        }
        gsap.from(el.querySelectorAll('.drawer-content > *'), {
          opacity: 0,
          y: 8,
          duration: MOTION.drawer,
          stagger: 0.04,
          delay: opening ? 0.1 : 0,
          ease: 'power3.out',
          clearProps: 'transform,opacity',
        });
      });
      return () => mm.revert();
    },
    { dependencies: [openKey] },
  );

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
      ref={asideRef}
      role="dialog"
      aria-modal="false"
      aria-labelledby="cp-title"
      data-testid="checkpoint-drawer"
      className="checkpoint-drawer surface scroll-thin fixed inset-0 z-40 w-full overflow-y-auto overscroll-contain !bg-white p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] dark:!bg-slate-900 sm:absolute sm:inset-auto sm:bottom-3 sm:right-3 sm:top-3 sm:max-w-sm sm:rounded-[20px] sm:!bg-white/90 sm:dark:!bg-slate-900/90"
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
          className="rounded-full p-1.5 text-slate-500 transition hover:bg-slate-900/5 focus-visible:outline-accent dark:hover:bg-white/10"
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
          <p className="mt-3 rounded-xl border border-accent/20 bg-accent/5 px-3 py-2 text-sm dark:border-accent-soft/30 dark:bg-accent-soft/10">
            <span className="block text-xs font-medium text-slate-500">Load rule applied</span>
            {r.load_rule_applied}
          </p>
        )}

        <h3 className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Arrival
        </h3>
        <dl className="mt-1 divide-y divide-slate-900/5 text-sm dark:divide-white/5">
          <Row label="ETA">{formatLocalDateTime(cp.eta_utc)}</Row>
          <Row label="Elapsed">{formatDuration(cp.elapsed_s)}</Row>
          <Row label="ETA method">
            {cp.eta_method === 'guidance' ? 'Route guidance' : 'Proportional'}
          </Row>
        </dl>

        <h3 className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Weather at ETA
        </h3>
        <dl className="mt-1 divide-y divide-slate-900/5 text-sm dark:divide-white/5">
          <Row label="Wind (sustained)">{fmt(w.wind_mph, 1, 'mph')}</Row>
          <Row label="Gusts (shown, not scored)">{fmt(w.gust_mph, 1, 'mph')}</Row>
          <Row label="Rain">{fmt(w.rain_in_hr, 2, 'in/hr')}</Row>
          <Row label="Snow">{fmt(w.snow_in_hr, 2, 'in/hr')}</Row>
          <Row label="Forecast hour used">
            {w.forecast_hour_utc ? formatLocalTime(w.forecast_hour_utc) : '—'}
          </Row>
        </dl>

        <h3 className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Component levels
        </h3>
        <dl className="mt-1 divide-y divide-slate-900/5 text-sm dark:divide-white/5">
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
