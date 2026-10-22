import { lazy, Suspense, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreatePlan, useRiskRules } from '../api/queries';
import type { ApiError } from '../api/client';
import type { Plan } from '../api/types';
import { CheckpointDrawer } from '../features/checkpoint/CheckpointDrawer';
import { Legend } from '../features/map/Legend';
import { PlanBanners } from '../features/routes/NoSafeRouteBanner';
import { RouteList } from '../features/routes/RouteList';
import { TripForm } from '../features/trip-form/TripForm';
import { applyRiskRules } from '../lib/risk';
import { useUIStore } from '../store/ui';

const MapView = lazy(() => import('../features/map/MapView'));

interface Props {
  plan: Plan | null;
  loading?: boolean;
  loadError?: ApiError | null;
}

function MapSkeleton() {
  return (
    <div className="absolute inset-0 animate-pulse bg-slate-200 dark:bg-slate-900" aria-hidden />
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
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-36 animate-pulse rounded-card bg-slate-200 dark:bg-slate-800" />
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

  return (
    <div className="relative h-full w-full overflow-hidden">
      {busy && (
        <div className="progress-bar fixed inset-x-0 top-0 z-50 h-0.5 bg-accent" aria-hidden />
      )}
      <Suspense fallback={<MapSkeleton />}>
        <MapView plan={plan} />
      </Suspense>

      <div className="pointer-events-none absolute bottom-4 left-[416px] z-10 hidden min-[900px]:block">
        <Legend />
      </div>

      <aside
        className="panel absolute z-20 flex flex-col overflow-hidden border-slate-200 bg-slate-50/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95"
        aria-label="Trip planner"
      >
        <div className="flex-1 overflow-y-auto p-4">
          <header className="mb-4 flex items-center justify-between gap-2">
            <h1 className="text-base font-semibold">Weather-aware truck routing</h1>
            {plan && <CopyLinkButton planId={plan.id} />}
          </header>
          <TripForm
            key={plan?.id ?? 'new'}
            initial={plan?.inputs}
            submitting={create.isPending}
            error={create.error}
            onSubmit={(body) =>
              create.mutate(body, { onSuccess: (p) => navigate(`/plan/${p.id}`) })
            }
          />
          <div className="mt-5 space-y-3">
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
            <div className="min-[900px]:hidden">
              <Legend />
            </div>
          </div>
        </div>
      </aside>

      {plan && <CheckpointDrawer plan={plan} />}
    </div>
  );
}
