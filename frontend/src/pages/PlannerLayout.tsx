import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreatePlan, useHeatmap, useRiskRules } from '../api/queries';
import type { ApiError } from '../api/client';
import type { Plan } from '../api/types';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { ThemeToggle } from '../components/ThemeToggle';
import { CheckpointDrawer } from '../features/checkpoint/CheckpointDrawer';
import { BottomSheet } from '../features/layout/BottomSheet';
import { Legend } from '../features/map/Legend';
import { PlanBanners } from '../features/routes/NoSafeRouteBanner';
import { RouteList } from '../features/routes/RouteList';
import { ForecastSlider, type ArrivalMarker } from '../features/timeline/ForecastSlider';
import { createHourBus } from '../features/timeline/hourBus';
import { TripForm } from '../features/trip-form/TripForm';
import { applyRiskRules } from '../lib/risk';
import { DESKTOP_QUERY, useMediaQuery } from '../lib/useMediaQuery';
import { useUIStore } from '../store/ui';

const MapView = lazy(() => import('../features/map/MapView'));
const HOUR_MS = 3_600_000;

/** Slider hour 0 = departure hour (UTC floor), matching the heatmap's first hour. */
function departureHourMs(plan: Plan | null): number {
  if (!plan) return 0;
  const t = Date.parse(plan.inputs.departure_utc);
  return Math.floor(t / HOUR_MS) * HOUR_MS;
}

interface Props {
  plan: Plan | null;
  loading?: boolean;
  loadError?: ApiError | null;
}

function MapSkeleton() {
  return <div className="skeleton absolute inset-0" aria-hidden />;
}

function MapError({ retry }: { retry: () => void }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-slate-100 p-6 dark:bg-[#0b0f1a]">
      <div role="alert" className="max-w-sm text-center text-sm">
        <p className="font-semibold">The map could not be loaded.</p>
        <p className="mt-1 text-slate-600 dark:text-slate-400">
          Route cards and details still work. Check your connection and try again.
        </p>
        <button type="button" className="btn-secondary mt-3" onClick={retry}>
          Retry map
        </button>
      </div>
    </div>
  );
}

function CopyLinkButton({ planId }: { planId: string }) {
  const [toast, setToast] = useState<string | null>(null);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2200);
    return () => window.clearTimeout(t);
  }, [toast]);
  const copy = async () => {
    const url = `${window.location.origin}/plan/${planId}`;
    try {
      await navigator.clipboard.writeText(url);
      setToast('Plan link copied');
    } catch {
      setToast(url);
    }
  };
  return (
    <>
      <button type="button" onClick={() => void copy()} className="btn-secondary">
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.8}
          className="h-3.5 w-3.5"
          aria-hidden
        >
          <path
            strokeLinecap="round"
            d="M8.5 11.5a3 3 0 0 0 4.2 0l2.6-2.6a3 3 0 0 0-4.2-4.2l-.9.9M11.5 8.5a3 3 0 0 0-4.2 0l-2.6 2.6a3 3 0 0 0 4.2 4.2l.9-.9"
          />
        </svg>
        Copy plan link
      </button>
      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-float dark:bg-white dark:text-slate-900"
        >
          {toast}
        </div>
      )}
    </>
  );
}

function BrandMark() {
  return (
    <span
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-sky-500 text-white shadow-glow"
      aria-hidden
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        className="h-5 w-5"
      >
        <path strokeLinejoin="round" d="M2.5 6.5h11v9h-11zM13.5 10h4l3 3v2.5h-7z" />
        <circle cx="6.5" cy="17" r="1.8" fill="currentColor" stroke="none" />
        <circle cx="17" cy="17" r="1.8" fill="currentColor" stroke="none" />
      </svg>
    </span>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="skeleton h-5 w-3/4 rounded" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="skeleton h-40 rounded-card" />
      ))}
    </div>
  );
}

export function PlannerLayout({ plan, loading = false, loadError = null }: Props) {
  const navigate = useNavigate();
  const create = useCreatePlan();
  const rules = useRiskRules();
  const reset = useUIStore((s) => s.reset);
  const [, setRulesVersion] = useState(0);

  useEffect(() => {
    if (rules.data) {
      applyRiskRules(rules.data);
      setRulesVersion((v) => v + 1);
    }
  }, [rules.data]);

  useEffect(() => {
    reset(plan ? (plan.recommended ?? plan.routes[0]?.label ?? null) : null);
  }, [plan, reset]);

  const busy = create.isPending || loading;
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const [mapKey, setMapKey] = useState(0);
  const heat = useHeatmap(plan?.id);
  const planId = plan?.id;
  // One imperative hour channel per plan (scrubbing never goes through React state).
  const bus = useMemo(() => createHourBus(0, planId), [planId]);
  const startMs = departureHourMs(plan);
  const arrivals: ArrivalMarker[] = useMemo(
    () =>
      plan?.routes.map((r) => ({
        label: r.label,
        hour: (Date.parse(r.arrival_utc) - startMs) / HOUR_MS,
      })) ?? [],
    [plan, startMs],
  );
  const heatStatus = heat.isLoading
    ? 'Loading forecast heatmap…'
    : heat.isError
      ? 'Heatmap unavailable; trucks still move with the slider.'
      : null;

  const slider = plan ? (
    <ForecastSlider bus={bus} startMs={startMs} arrivals={arrivals} status={heatStatus} />
  ) : null;

  const panelContent = (
    <>
      <header className="mb-5 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <BrandMark />
          <div className="min-w-0">
            <h1 className="truncate text-[15px] font-semibold leading-tight tracking-tight">
              Truck Weather Routing
            </h1>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">
              Safest route by forecast at arrival
            </p>
          </div>
        </div>
        <ThemeToggle />
      </header>
      {plan && (
        <div className="mb-4 flex justify-end">
          <CopyLinkButton planId={plan.id} />
        </div>
      )}
      <TripForm
        key={plan?.id ?? 'new'}
        initial={plan?.inputs}
        submitting={create.isPending}
        error={create.error}
        onSubmit={(body) => create.mutate(body, { onSuccess: (p) => navigate(`/plan/${p.id}`) })}
      />
      <div className="mt-5 space-y-3" aria-live="polite" aria-busy={busy}>
        {loadError && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300"
          >
            {loadError.code === 'PLAN_NOT_FOUND'
              ? 'This plan link has expired or does not exist. Plan a new trip above.'
              : loadError.message}
          </div>
        )}
        {busy && !plan && <ResultsSkeleton />}
        {plan && (
          <>
            <PlanBanners plan={plan} />
            <RouteList plan={plan} />
          </>
        )}
        {!isDesktop && <Legend />}
      </div>
    </>
  );

  return (
    <div className="relative h-full w-full overflow-hidden">
      <a
        href="#planner"
        className="sr-only z-50 rounded-lg bg-white px-3 py-2 text-sm font-medium text-accent focus:not-sr-only focus:absolute focus:left-2 focus:top-2"
      >
        Skip to trip planner
      </a>
      {busy && (
        <div
          className="progress-track fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden"
          aria-hidden
        >
          <div className="progress-bar h-full w-1/3 bg-accent" />
        </div>
      )}
      <main className="absolute inset-0" aria-label="Route map">
        <ErrorBoundary
          key={mapKey}
          fallback={() => <MapError retry={() => setMapKey((k) => k + 1)} />}
        >
          <Suspense fallback={<MapSkeleton />}>
            <MapView plan={plan} heatmap={heat.data ?? null} bus={bus} startMs={startMs} />
          </Suspense>
        </ErrorBoundary>
      </main>

      {isDesktop ? (
        <>
          <div className="pointer-events-none absolute left-[428px] top-4 z-10">
            <Legend />
          </div>
          {slider && <div className="absolute bottom-4 left-[428px] right-4 z-20">{slider}</div>}
          <aside
            id="planner"
            className="surface absolute bottom-3 left-3 top-3 z-20 flex w-[400px] flex-col overflow-hidden rounded-[20px]"
            aria-label="Trip planner"
          >
            <div className="scroll-thin flex-1 overflow-y-auto p-5">{panelContent}</div>
          </aside>
        </>
      ) : (
        <div id="planner">
          <BottomSheet label="Trip planner" above={slider}>
            {panelContent}
          </BottomSheet>
        </div>
      )}

      {plan && <CheckpointDrawer plan={plan} />}
    </div>
  );
}
