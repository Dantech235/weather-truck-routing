import gsap from 'gsap';
import { useCallback, useEffect, useRef } from 'react';
import { useUIStore } from '../../store/ui';
import { MAX_HOUR, type HourBus } from './hourBus';

const SECONDS_PER_HOUR = 0.4;

/**
 * Play/pause the forecast: a GSAP tween on a proxy {hour} → 48 at 0.4 s per hour (ease none).
 * onUpdate writes to the hour bus synchronously (GSAP already runs inside rAF), so playback
 * paints the map without any React render. Only play/pause toggles touch React state.
 */
export function usePlayback(bus: HourBus) {
  const tweenRef = useRef<gsap.core.Tween | null>(null);
  const setPlaying = useUIStore((s) => s.setPlaying);
  const setSliderHour = useUIStore((s) => s.setSliderHour);

  const pause = useCallback(() => {
    if (!tweenRef.current) return;
    tweenRef.current.kill();
    tweenRef.current = null;
    setPlaying(false);
    setSliderHour(bus.get());
  }, [bus, setPlaying, setSliderHour]);

  const play = useCallback(() => {
    tweenRef.current?.kill();
    const from = bus.get() >= MAX_HOUR ? 0 : bus.get();
    const proxy = { hour: from };
    bus.setNow(from);
    tweenRef.current = gsap.to(proxy, {
      hour: MAX_HOUR,
      duration: (MAX_HOUR - from) * SECONDS_PER_HOUR,
      ease: 'none',
      onUpdate: () => bus.setNow(proxy.hour),
      onComplete: () => {
        tweenRef.current = null;
        setPlaying(false);
        setSliderHour(MAX_HOUR);
      },
    });
    setPlaying(true);
  }, [bus, setPlaying, setSliderHour]);

  const toggle = useCallback(() => {
    if (tweenRef.current) pause();
    else play();
  }, [pause, play]);

  // Kill the tween on unmount or when the bus (i.e. the plan) changes.
  useEffect(
    () => () => {
      tweenRef.current?.kill();
      tweenRef.current = null;
      useUIStore.getState().setPlaying(false);
    },
    [bus],
  );

  return { toggle, pause };
}
