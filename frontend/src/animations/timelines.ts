import gsap from 'gsap';
import type { Map as MapLibreMap } from 'maplibre-gl';
import type { Route } from '../api/types';
import { paintCheckpointEmphasis } from '../features/map/layers/checkpoints';
import { setRouteProgress } from '../features/map/layers/routes';
import { useUIStore } from '../store/ui';
import { REDUCED_MOTION_QUERY } from './useReducedMotion';

/** Section 7.5 timings (seconds). Reduced motion collapses all of them to ~0. */
export const MOTION = {
  routeDraw: 0.9,
  routeStagger: 0.15,
  checkpoints: 0.3,
  card: 0.4,
  cardStagger: 0.08,
  countUp: 0.8,
  badge: 0.5,
  drawer: 0.35,
} as const;

/**
 * Run `build` under gsap.matchMedia so `prefers-reduced-motion: reduce` gets ~0 durations.
 * Returns the MatchMedia instance; call `.revert()` (or let useGSAP's context do it) to kill
 * every tween it created.
 */
export function withMotion(build: (reduce: boolean) => void): gsap.MatchMedia {
  const mm = gsap.matchMedia();
  mm.add({ reduce: REDUCED_MOTION_QUERY, motion: `not all and ${REDUCED_MOTION_QUERY}` }, (ctx) => {
    build(Boolean(ctx.conditions?.reduce));
  });
  return mm;
}

/**
 * Routes draw in A → B → C by tweening a proxy {p: 0 → 1} and rewriting `line-gradient` with a
 * hidden tail; checkpoints then fade in through `circle-opacity`. Paint properties only — the
 * camera is never animated with GSAP.
 */
export function routeDrawIn(
  map: MapLibreMap,
  routes: Route[],
  reduce: boolean,
): gsap.core.Timeline {
  const ordered = [...routes].sort((a, b) => a.label.localeCompare(b.label));
  const tl = gsap.timeline();
  if (reduce) {
    for (const r of ordered) setRouteProgress(map, r, 1);
    paintCheckpointEmphasis(map, useUIStore.getState().selectedRoute, 1);
    return tl;
  }
  ordered.forEach((route, i) => {
    const proxy = { p: 0 };
    tl.to(
      proxy,
      {
        p: 1,
        duration: MOTION.routeDraw,
        ease: 'power2.out',
        onUpdate: () => setRouteProgress(map, route, proxy.p),
      },
      i * MOTION.routeStagger,
    );
  });
  const fade = { o: 0 };
  tl.to(fade, {
    o: 1,
    duration: MOTION.checkpoints,
    ease: 'power1.out',
    onUpdate: () => paintCheckpointEmphasis(map, useUIStore.getState().selectedRoute, fade.o),
  });
  return tl;
}
