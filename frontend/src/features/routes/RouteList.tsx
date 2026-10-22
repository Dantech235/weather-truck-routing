import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { useRef } from 'react';
import { MOTION, withMotion } from '../../animations/timelines';
import type { Plan } from '../../api/types';
import { RouteCard } from './RouteCard';

export function RouteList({ plan }: { plan: Plan }) {
  const scope = useRef<HTMLElement>(null);

  // Cards rise in, then the Recommended badge pops with one soft glow. Transform/opacity only.
  useGSAP(
    () => {
      const mm = withMotion((reduce) => {
        if (reduce) return;
        gsap.from('.route-card', {
          y: 16,
          opacity: 0,
          duration: MOTION.card,
          stagger: MOTION.cardStagger,
          ease: 'power3.out',
          clearProps: 'transform,opacity',
        });
        const delay = MOTION.card + MOTION.cardStagger * plan.routes.length;
        gsap.from('.recommended-badge', {
          scale: 0.8,
          duration: MOTION.badge,
          ease: 'back.out(1.7)',
          delay,
          clearProps: 'transform',
        });
        gsap.fromTo(
          '.badge-glow',
          { opacity: 0, scale: 1 },
          {
            opacity: 0.55,
            scale: 1.35,
            duration: MOTION.badge / 2,
            ease: 'sine.out',
            yoyo: true,
            repeat: 1,
            delay,
          },
        );
      });
      return () => mm.revert();
    },
    { scope, dependencies: [plan.id] },
  );

  return (
    <section ref={scope} aria-label="Route options" className="space-y-3">
      <p className="rounded-xl bg-gradient-to-br from-accent/10 to-sky-500/10 px-3.5 py-3 text-sm leading-relaxed text-slate-700 dark:from-accent-soft/15 dark:to-sky-400/10 dark:text-slate-200">
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
