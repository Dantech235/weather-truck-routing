import { useSyncExternalStore } from 'react';

/** Side-panel layout: wide screens, plus short landscape screens (phones turned sideways). */
export const DESKTOP_QUERY =
  '(min-width: 900px), (min-width: 640px) and (max-height: 520px) and (orientation: landscape)';

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
