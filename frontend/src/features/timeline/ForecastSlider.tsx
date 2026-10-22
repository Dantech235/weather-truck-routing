import clsx from 'clsx';
import { formatInTimeZone } from 'date-fns-tz';
import { useEffect, useMemo, useRef, type KeyboardEvent, type PointerEvent } from 'react';
import { browserTimeZone } from '../../lib/format';
import { useUIStore } from '../../store/ui';
import { clampHour, MAX_HOUR, type HourBus } from './hourBus';
import { usePlayback } from './usePlayback';

const HOUR_MS = 3_600_000;
const TICK_EVERY = 6;

/** Every 24 h on phones, every 12 h on small tablets, every 6 h from md up. */
function tickVisibility(hour: number): string {
  if (hour % 24 === 0) return '';
  if (hour % 12 === 0) return 'hidden sm:inline';
  return 'hidden md:inline';
}

export interface ArrivalMarker {
  label: string;
  hour: number;
}

interface Props {
  bus: HourBus;
  startMs: number; // hour 0 (departure hour, UTC floor)
  arrivals: ArrivalMarker[];
  status?: string | null;
}

/**
 * Custom 0–48 h range. Scrubbing writes to the hour bus only; the thumb, fill, ARIA value and
 * clock label are updated directly in the DOM from the bus. React state (sliderHour) is
 * committed on pointer-up and per key press, never per pointer-move.
 */
export function ForecastSlider({ bus, startMs, arrivals, status }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const thumbRef = useRef<HTMLDivElement>(null);
  const fillRef = useRef<HTMLDivElement>(null);
  const clockRef = useRef<HTMLSpanElement>(null);
  const dragging = useRef(false);
  const playing = useUIStore((s) => s.playing);
  const commit = useUIStore((s) => s.setSliderHour);
  const { toggle, pause } = usePlayback(bus);
  const tz = useMemo(() => browserTimeZone(), []);

  const ticks = useMemo(
    () =>
      Array.from({ length: MAX_HOUR / TICK_EVERY + 1 }, (_, i) => {
        const hour = i * TICK_EVERY;
        return { hour, text: formatInTimeZone(new Date(startMs + hour * HOUR_MS), tz, 'EEE h a') };
      }),
    [startMs, tz],
  );

  // Bus → DOM (no React render).
  useEffect(
    () =>
      bus.subscribe((hour) => {
        const pct = (hour / MAX_HOUR) * 100;
        if (thumbRef.current) {
          thumbRef.current.style.left = `${pct}%`;
          thumbRef.current.setAttribute('aria-valuenow', hour.toFixed(1));
          const at = new Date(startMs + hour * HOUR_MS);
          thumbRef.current.setAttribute(
            'aria-valuetext',
            `+${Math.round(hour)} h, ${formatInTimeZone(at, tz, 'EEE h:mm a zzz')}`,
          );
        }
        if (fillRef.current) fillRef.current.style.transform = `scaleX(${hour / MAX_HOUR})`;
        if (clockRef.current) {
          const at = new Date(startMs + hour * HOUR_MS);
          clockRef.current.textContent = `${formatInTimeZone(at, tz, 'EEE h:mm a zzz')} · +${hour.toFixed(1)} h`;
        }
      }),
    [bus, startMs, tz],
  );

  const hourFromX = (clientX: number) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return bus.get();
    return clampHour(((clientX - rect.left) / rect.width) * MAX_HOUR);
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    pause();
    dragging.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    thumbRef.current?.focus({ preventScroll: true });
    bus.set(hourFromX(e.clientX));
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (dragging.current) bus.set(hourFromX(e.clientX));
  };
  const onPointerUp = (e: PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) return;
    dragging.current = false;
    e.currentTarget.releasePointerCapture(e.pointerId);
    commit(bus.get());
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 6 : 1;
    let next: number | null = null;
    const now = bus.get();
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') next = Math.floor(now) + step;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') next = Math.ceil(now) - step;
    else if (e.key === 'PageUp') next = now + 6;
    else if (e.key === 'PageDown') next = now - 6;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = MAX_HOUR;
    else if (e.key === ' ' || e.key === 'k') {
      e.preventDefault();
      toggle();
      return;
    }
    if (next === null) return;
    e.preventDefault();
    pause();
    const h = clampHour(next);
    bus.set(h);
    commit(h);
  };

  return (
    <div
      className="forecast-dock pointer-events-auto rounded-card border border-slate-200 bg-white/95 px-3 pb-2 pt-2 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/95"
      role="group"
      aria-label="Forecast timeline"
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={toggle}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-white hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          aria-label={playing ? 'Pause forecast playback' : 'Play forecast'}
          aria-pressed={playing}
          data-testid="play-button"
        >
          <span aria-hidden>{playing ? '❚❚' : '▶'}</span>
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span
              className="font-semibold tabular-nums"
              ref={clockRef}
              data-testid="slider-clock"
              aria-live="off"
            />
            <span className="hidden truncate text-slate-500 sm:inline">
              {status ?? 'Weather risk, next 48 h'}
            </span>
          </div>
          <div
            ref={trackRef}
            className="relative mt-2 h-6 cursor-pointer touch-none select-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
              <div
                ref={fillRef}
                className="h-full w-full origin-left bg-accent"
                style={{ transform: 'scaleX(0)' }}
              />
            </div>
            {arrivals.map((a) => (
              <div
                key={a.label}
                className="absolute top-0 h-6 w-0.5 -translate-x-1/2 bg-slate-900 dark:bg-slate-100"
                style={{ left: `${(clampHour(a.hour) / MAX_HOUR) * 100}%` }}
                title={`Route ${a.label} arrives`}
                aria-hidden
              >
                <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-[10px] font-bold">
                  {a.label}
                </span>
              </div>
            ))}
            <div
              ref={thumbRef}
              role="slider"
              tabIndex={0}
              aria-label="Forecast hour"
              aria-valuemin={0}
              aria-valuemax={MAX_HOUR}
              aria-valuenow={0}
              onKeyDown={onKeyDown}
              data-testid="forecast-slider"
              className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-accent shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              style={{ left: '0%' }}
            />
          </div>
          <div className="relative mt-0.5 h-4 text-[10px] text-slate-500">
            {ticks.map((t) => (
              <span
                key={t.hour}
                className={clsx(
                  'absolute -translate-x-1/2 whitespace-nowrap tabular-nums first:translate-x-0 last:-translate-x-full',
                  tickVisibility(t.hour),
                )}
                style={{ left: `${(t.hour / MAX_HOUR) * 100}%` }}
              >
                {t.text}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
