import { useSyncExternalStore } from 'react';

export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' && (window.matchMedia?.(REDUCED_MOTION_QUERY).matches ?? false)
  );
}

function subscribe(onChange: () => void): () => void {
  const mql = window.matchMedia?.(REDUCED_MOTION_QUERY);
  mql?.addEventListener('change', onChange);
  return () => mql?.removeEventListener('change', onChange);
}

/** Live `prefers-reduced-motion: reduce` flag. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, prefersReducedMotion, () => false);
}
