/**
 * Imperative channel for the forecast hour (0–48). Writers call `set`; listeners run at most
 * once per animation frame. Nothing here touches React state, so scrubbing and playback never
 * cause React renders.
 */
export type HourListener = (hour: number) => void;

export const MAX_HOUR = 48;

export interface HourBus {
  /** Owner id (the plan), for debugging; a new plan gets a new bus. */
  readonly id: string | undefined;
  get: () => number;
  /** Store the hour and schedule one rAF that notifies listeners. */
  set: (hour: number) => void;
  /** Store the hour and notify listeners synchronously (already inside a frame, e.g. GSAP). */
  setNow: (hour: number) => void;
  subscribe: (listener: HourListener) => () => void;
}

export const clampHour = (h: number) => Math.min(MAX_HOUR, Math.max(0, h));

export function createHourBus(initial = 0, id?: string): HourBus {
  let hour = clampHour(initial);
  let frame = 0;
  const listeners = new Set<HourListener>();
  const notify = () => {
    frame = 0;
    for (const l of listeners) l(hour);
  };
  return {
    id,
    get: () => hour,
    set: (h) => {
      hour = clampHour(h);
      if (!frame) frame = requestAnimationFrame(notify);
    },
    setNow: (h) => {
      hour = clampHour(h);
      if (frame) {
        cancelAnimationFrame(frame);
        frame = 0;
      }
      notify();
    },
    subscribe: (listener) => {
      listeners.add(listener);
      listener(hour);
      return () => listeners.delete(listener);
    },
  };
}
