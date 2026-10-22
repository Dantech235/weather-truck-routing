import clsx from 'clsx';
import { formatInTimeZone } from 'date-fns-tz';
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { browserTimeZone } from '../../lib/format';
import { useUIStore } from '../../store/ui';
import { clampHour, MAX_HOUR, type HourBus } from './hourBus';
import { usePlayback } from './usePlayback';

const HOUR_MS = 3_600_000;
const TICK_EVERY = 6;
/** Room one tick label ("Thu 12 AM") needs, in px. */
const LABEL_PX = 70;
/** Arrival markers closer than this share one label. */
const ARRIVAL_MERGE_PX = 22;

/** Label every 6, 12 or 24 h: the densest step whose labels fit the track's real width. */
export function tickStep(trackPx: number): number {
  for (const step of [6, 12, 24]) {
    if ((MAX_HOUR / step + 1) * LABEL_PX <= trackPx) return step;
  }
  return 48;
}

export interface ArrivalCluster {
  labels: string[];
  hours: number[];
  /** Label position along the track, 0–1. */
  at: number;
}

/** Group arrivals whose markers would overlap at this track width. */
export function clusterArrivals(arrivals: ArrivalMarker[], trackPx: number): ArrivalCluster[] {
  const sorted = [...arrivals]
    .map((a) => ({ label: a.label, hour: clampHour(a.hour) }))
    .sort((a, b) => a.hour - b.hour);
  const pxPerHour = trackPx / MAX_HOUR;
  const out: ArrivalCluster[] = [];
  for (const a of sorted) {
    const last = out[out.length - 1];
    const prevHour = last?.hours[last.hours.length - 1];
    if (last && prevHour !== undefined && (a.hour - prevHour) * pxPerHour < ARRIVAL_MERGE_PX) {
      last.labels.push(a.label);
      last.hours.push(a.hour);
    } else {
      out.push({ labels: [a.label], hours: [a.hour], at: 0 });
    }
  }
  for (const c of out) {
    c.at = c.hours.reduce((t, h) => t + h, 0) / c.hours.length / MAX_HOUR;
  }
  return out;
}

/** Keep labels near the ends inside the track. */
function edgeAlign(at: number): string {
  if (at < 0.04) return 'translate-x-0';
  if (at > 0.96) return '-translate-x-full';
  return '-translate-x-1/2';
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
  // Track width drives label density. Updated on resize only, never while scrubbing.
  const [trackPx, setTrackPx] = useState(600);
  useEffect(() => {
    const el = trackRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(([entry]) => {
      if (entry) setTrackPx(Math.round(entry.contentRect.width));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const step = tickStep(trackPx);
  const clusters = useMemo(() => clusterArrivals(arrivals, trackPx), [arrivals, trackPx]);

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
      className="forecast-dock surface pointer-events-auto rounded-[20px] px-4 pb-2.5 pt-3"
      role="group"
      aria-label="Forecast timeline"
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={toggle}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-blue-600 text-white shadow-glow transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          aria-label={playing ? 'Pause forecast playback' : 'Play forecast'}
          aria-pressed={playing}
          data-testid="play-button"
        >
          <span aria-hidden>{playing ? '❚❚' : '▶'}</span>
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span
              className="min-w-0 truncate font-semibold tabular-nums"
              ref={clockRef}
              data-testid="slider-clock"
              aria-live="off"
            />
            <span className="hidden truncate text-slate-500 dark:text-slate-400 sm:inline">
              {status ?? 'Weather risk, next 48 h'}
            </span>
          </div>
          <div
            ref={trackRef}
            className="relative mt-4 h-6 cursor-pointer touch-none select-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
              <div
                ref={fillRef}
                className="h-full w-full origin-left bg-gradient-to-r from-accent to-sky-500"
                style={{ transform: 'scaleX(0)' }}
              />
            </div>
            {arrivals.map((a) => (
              <div
                key={a.label}
                className="absolute top-0.5 h-5 w-0.5 -translate-x-1/2 rounded-full bg-slate-900/70 dark:bg-white/70"
                style={{ left: `${(clampHour(a.hour) / MAX_HOUR) * 100}%` }}
                title={`Route ${a.label} arrives`}
                aria-hidden
              />
            ))}
            {clusters.map((c) => (
              <span
                key={c.labels.join('')}
                className={clsx(
                  'absolute -top-3.5 whitespace-nowrap text-[10px] font-bold leading-none',
                  edgeAlign(c.at),
                )}
                style={{ left: `${c.at * 100}%` }}
                aria-hidden
              >
                {c.labels.join(' ')}
              </span>
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
              className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-accent shadow-glow focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent dark:border-slate-900"
              style={{ left: '0%' }}
            />
          </div>
          <div className="relative mt-0.5 h-4 text-[10px] text-slate-500">
            {ticks.map((t) => (
              <span
                key={t.hour}
                className={clsx(
                  'absolute -translate-x-1/2 whitespace-nowrap tabular-nums first:translate-x-0 last:-translate-x-full',
                  t.hour % step !== 0 && 'hidden',
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
