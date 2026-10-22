import clsx from 'clsx';
import type { ReactNode } from 'react';
import type { Plan } from '../../api/types';

type Tone = 'danger' | 'warning' | 'info';

const TONES: Record<Tone, string> = {
  danger:
    'border-red-200 bg-red-50 text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200',
  warning:
    'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200',
  info: 'border-indigo-200 bg-indigo-50 text-indigo-900 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-200',
};

export function Banner({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={clsx('rounded-xl border px-3 py-2.5 text-sm', TONES[tone])}
    >
      {children}
    </div>
  );
}

/** No-safe-route (red), partial weather (amber), fewer than 3 routes (blue), heavy load. */
export function PlanBanners({ plan }: { plan: Plan }) {
  return (
    <div className="space-y-2">
      {plan.recommended === null && (
        <Banner tone="danger">
          <strong className="font-semibold">No safe route.</strong> {plan.recommendation_reason} Try
          a later departure.
        </Banner>
      )}
      {plan.status === 'partial' && (
        <Banner tone="warning">
          Weather could not be fetched for some checkpoints. They are marked Unknown and are not
          counted as Low.
        </Banner>
      )}
      {plan.routes_found < 3 && (
        <Banner tone="info">
          Only {plan.routes_found} distinct route{plan.routes_found === 1 ? '' : 's'} found for this
          trip.
        </Banner>
      )}
      {plan.warnings.includes('LOAD_ABOVE_80000_LB') && (
        <Banner tone="warning">
          Load is above 80,000 lb, which typically needs an oversize permit.
        </Banner>
      )}
    </div>
  );
}
