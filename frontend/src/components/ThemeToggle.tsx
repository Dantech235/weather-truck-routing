import clsx from 'clsx';
import { useTheme, type ThemeMode } from '../lib/theme';

const ICONS: Record<ThemeMode, JSX.Element> = {
  light: (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      className="h-4 w-4"
    >
      <circle cx="10" cy="10" r="3.5" />
      <path
        strokeLinecap="round"
        d="M10 2v1.5M10 16.5V18M2 10h1.5M16.5 10H18M4.3 4.3l1.1 1.1M14.6 14.6l1.1 1.1M4.3 15.7l1.1-1.1M14.6 5.4l1.1-1.1"
      />
    </svg>
  ),
  dark: (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      className="h-4 w-4"
    >
      <path strokeLinejoin="round" d="M16.5 12.2A6.8 6.8 0 0 1 7.8 3.5a6.8 6.8 0 1 0 8.7 8.7Z" />
    </svg>
  ),
  system: (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      className="h-4 w-4"
    >
      <rect x="2.5" y="3.5" width="15" height="10" rx="2" />
      <path strokeLinecap="round" d="M7 17h6M10 13.5V17" />
    </svg>
  ),
};

const LABELS: Record<ThemeMode, string> = { light: 'Light', dark: 'Dark', system: 'System' };
const ORDER: ThemeMode[] = ['light', 'dark', 'system'];

/** Segmented light / dark / system switch. */
export function ThemeToggle() {
  const mode = useTheme((s) => s.mode);
  const setMode = useTheme((s) => s.setMode);
  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className="inline-flex rounded-full border border-slate-200/80 bg-slate-100/80 p-0.5 dark:border-white/10 dark:bg-white/5"
    >
      {ORDER.map((m) => (
        <button
          key={m}
          type="button"
          role="radio"
          aria-checked={mode === m}
          aria-label={`${LABELS[m]} theme`}
          title={`${LABELS[m]} theme`}
          onClick={() => setMode(m)}
          className={clsx(
            'flex h-7 w-7 items-center justify-center rounded-full transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent',
            mode === m
              ? 'bg-white text-slate-900 shadow-sm dark:bg-white/15 dark:text-white'
              : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
          )}
        >
          {ICONS[m]}
        </button>
      ))}
    </div>
  );
}
