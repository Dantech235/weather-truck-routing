import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreatePlan, useHeatmap, useRiskRules } from '../api/queries';
import type { ApiError } from '../api/client';
import type { Plan } from '../api/types';
import { ErrorBoundary } from '../components/ErrorBoundary';
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
    <div className="absolute inset-0 flex items-center justify-center bg-slate-100 p-6 dark:bg-slate-900">
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
        Copy plan link
      </button>
      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-card bg-slate-900 px-4 py-2 text-sm text-white shadow-lg dark:bg-slate-100 dark:text-slate-900"
        >
          {toast}
        </div>
      )}
    </>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="skeleton h-5 w-3/4 rounded" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="skeleton h-36 rounded-card" />
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
      <header className="mb-4 flex items-center justify-between gap-2">
        <h1 className="text-base font-semibold">Weather-aware truck routing</h1>
        {plan && <CopyLinkButton planId={plan.id} />}
      </header>
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
            className="rounded-card border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
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
          <div className="pointer-events-none absolute bottom-[104px] left-[416px] z-10">
            <Legend />
          </div>
          {slider && <div className="absolute bottom-4 left-[416px] right-4 z-20">{slider}</div>}
          <aside
            id="planner"
            className="absolute inset-y-0 left-0 z-20 flex w-[400px] flex-col overflow-hidden border-r border-slate-200 bg-slate-50/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95"
            aria-label="Trip planner"
          >
            <div className="flex-1 overflow-y-auto p-4">{panelContent}</div>
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
