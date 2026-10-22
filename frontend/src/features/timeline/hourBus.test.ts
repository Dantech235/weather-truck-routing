import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createHourBus } from './hourBus';

describe('hourBus', () => {
  beforeEach(() => vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame'] }));
  afterEach(() => vi.useRealTimers());

  it('batches many sets into one listener call per frame and clamps', () => {
    const bus = createHourBus(0, 'p');
    const seen: number[] = [];
    bus.subscribe((h) => seen.push(h));
    expect(seen).toEqual([0]); // immediate call on subscribe
    bus.set(3);
    bus.set(7.5);
    bus.set(99);
    expect(seen).toEqual([0]);
    vi.advanceTimersToNextFrame();
    expect(seen).toEqual([0, 48]);
    bus.setNow(-4);
    expect(seen).toEqual([0, 48, 0]);
    expect(bus.get()).toBe(0);
  });

  it('unsubscribes', () => {
    const bus = createHourBus();
    const fn = vi.fn();
    const off = bus.subscribe(fn);
    off();
    bus.setNow(5);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
