import type { Plan } from '../../api/types';
import { RouteCard } from './RouteCard';

export function RouteList({ plan }: { plan: Plan }) {
  return (
    <section aria-label="Route options" className="space-y-3">
      <p className="text-sm text-slate-700 dark:text-slate-300">
        {plan.recommended ? (
          <>
            <strong className="font-semibold">Route {plan.recommended} recommended.</strong>{' '}
            {plan.recommendation_reason}
          </>
        ) : (
          plan.recommendation_reason
        )}
      </p>
      <ul className="space-y-3">
        {plan.routes.map((route) => (
          <li key={route.label}>
            <RouteCard route={route} recommended={plan.recommended === route.label} />
          </li>
        ))}
      </ul>
    </section>
  );
}
