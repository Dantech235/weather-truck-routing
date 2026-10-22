import { create } from 'zustand';

/** Light by default; dark or "follow the system" only when the user picks it. */
export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'truck-theme';
const DARK_QUERY = '(prefers-color-scheme: dark)';

function readStored(): ThemeMode {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === 'dark' || v === 'system' || v === 'light' ? v : 'light';
  } catch {
    return 'light';
  }
}

function systemDark(): boolean {
  return window.matchMedia?.(DARK_QUERY).matches ?? false;
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === 'system') return systemDark() ? 'dark' : 'light';
  return mode;
}

function apply(resolved: ResolvedTheme): void {
  const root = document.documentElement;
  root.classList.toggle('dark', resolved === 'dark');
  root.style.colorScheme = resolved;
}

interface ThemeState {
  mode: ThemeMode;
  resolved: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
}

export const useTheme = create<ThemeState>()((set) => {
  const mode = typeof window === 'undefined' ? 'light' : readStored();
  const resolved = typeof window === 'undefined' ? 'light' : resolveTheme(mode);
  return {
    mode,
    resolved,
    setMode: (next) => {
      try {
        window.localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* storage unavailable: the choice lasts for this visit only */
      }
      const r = resolveTheme(next);
      apply(r);
      set({ mode: next, resolved: r });
    },
  };
});

/** Apply the stored theme and keep "system" in sync with OS changes. Call once at startup. */
export function initTheme(): void {
  apply(useTheme.getState().resolved);
  window.matchMedia?.(DARK_QUERY).addEventListener?.('change', () => {
    const { mode } = useTheme.getState();
    if (mode !== 'system') return;
    const r = resolveTheme(mode);
    apply(r);
    useTheme.setState({ resolved: r });
  });
}
