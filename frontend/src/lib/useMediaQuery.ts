import { useSyncExternalStore } from 'react';

export const DESKTOP_QUERY = '(min-width: 900px)';

/** Live media-query match (re-renders only when the match flips). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia?.(query);
      mql?.addEventListener('change', onChange);
      return () => mql?.removeEventListener('change', onChange);
    },
    () => window.matchMedia?.(query).matches ?? true,
    () => true,
  );
}
