import gsap from 'gsap';
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { prefersReducedMotion } from '../../animations/useReducedMotion';
import { setMapBottomInset } from '../../lib/layoutMetrics';

export type Snap = 'peek' | 'half' | 'full';
const ORDER: Snap[] = ['peek', 'half', 'full'];
const SNAP_LABEL: Record<Snap, string> = {
  peek: 'collapsed',
  half: 'half height',
  full: 'expanded',
};
const PEEK_PX = 148;
const SHEET_VH = 0.92;
const FLICK_PX_PER_MS = 0.5;
/** Height of the slider riding on top of the sheet, so the map camera can avoid it. */
const ABOVE_SHEET_PX = 84;

function snapHeight(snap: Snap, vh: number): number {
  if (snap === 'peek') return PEEK_PX;
  if (snap === 'half') return Math.round(vh * 0.5);
  return Math.round(vh * SHEET_VH);
}

/** translateY that shows `snap` of a sheet that is SHEET_VH tall. */
function offsetFor(snap: Snap): number {
  return Math.round(window.innerHeight * SHEET_VH) - snapHeight(snap, window.innerHeight);
}

interface Props {
  children: ReactNode;
  /** Rendered just above the sheet and moves with it (the forecast slider). */
  above?: ReactNode;
  label: string;
}

/**
 * Mobile panel: a draggable sheet with three snap points. Dragging writes the transform
 * directly (no React state per move); snapping is a short GSAP tween. The handle is a button,
 * so keyboard and screen-reader users can cycle the snap points.
 */
export function BottomSheet({ children, above, label }: Props) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const [snap, setSnap] = useState<Snap>('half');
  const drag = useRef<{ startY: number; startOffset: number; lastY: number; lastT: number } | null>(
    null,
  );

  const animateTo = useCallback((s: Snap, instant = false) => {
    const el = sheetRef.current;
    if (!el) return;
    const y = offsetFor(s);
    setMapBottomInset(snapHeight(s, window.innerHeight) + ABOVE_SHEET_PX);
    if (instant || prefersReducedMotion()) gsap.set(el, { y });
    else gsap.to(el, { y, duration: 0.3, ease: 'power3.out', overwrite: true });
  }, []);

  // Place the sheet at its initial snap before first paint; later snaps animate.
  const initialSnap = useRef(snap);
  useLayoutEffect(() => animateTo(initialSnap.current, true), [animateTo]);

  // Keep the current snap on resize/rotation.
  useEffect(() => {
    const onResize = () => animateTo(snap, true);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [snap, animateTo]);

  // Unmount only: stop any snap tween and give the map its full height back. (Running this on
  // every snap change would kill the tween that the change just started.)
  useEffect(() => {
    const el = sheetRef.current;
    return () => {
      if (el) gsap.killTweensOf(el);
      setMapBottomInset(0);
    };
  }, []);

  const choose = (s: Snap) => {
    setSnap(s);
    animateTo(s);
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = sheetRef.current;
    if (!el) return;
    gsap.killTweensOf(el);
    e.currentTarget.setPointerCapture(e.pointerId);
    const current = Number(gsap.getProperty(el, 'y')) || 0;
    drag.current = {
      startY: e.clientY,
      startOffset: current,
      lastY: e.clientY,
      lastT: e.timeStamp,
    };
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    const el = sheetRef.current;
    if (!d || !el) return;
    const max = offsetFor('peek');
    const y = Math.min(max, Math.max(0, d.startOffset + (e.clientY - d.startY)));
    gsap.set(el, { y });
    d.lastY = e.clientY;
    d.lastT = e.timeStamp;
  };

  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    const el = sheetRef.current;
    drag.current = null;
    if (!d || !el) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    const moved = e.clientY - d.startY;
    if (Math.abs(moved) < 4) {
      // A tap on the handle cycles snap points, like the keyboard.
      choose(ORDER[(ORDER.indexOf(snap) + 1) % ORDER.length] ?? 'half');
      return;
    }
    const velocity = (e.clientY - d.lastY) / Math.max(1, e.timeStamp - d.lastT);
    const y = Number(gsap.getProperty(el, 'y')) || 0;
    let target: Snap;
    if (velocity > FLICK_PX_PER_MS) target = snap === 'full' ? 'half' : 'peek';
    else if (velocity < -FLICK_PX_PER_MS) target = snap === 'peek' ? 'half' : 'full';
    else {
      target = ORDER.reduce((best, s) =>
        Math.abs(offsetFor(s) - y) < Math.abs(offsetFor(best) - y) ? s : best,
      );
    }
    choose(target);
  };

  return (
    <div
      ref={sheetRef}
      className="fixed inset-x-0 bottom-0 z-20 flex flex-col rounded-t-[24px] border-t border-white/60 bg-white/95 shadow-[0_-8px_32px_-8px_rgba(15,23,42,0.2)] backdrop-blur-xl backdrop-saturate-150 dark:border-white/10 dark:bg-slate-900/95"
      style={{ height: `${SHEET_VH * 100}dvh` }}
      data-testid="bottom-sheet"
      data-snap={snap}
    >
      {above && <div className="absolute inset-x-2 bottom-full mb-2">{above}</div>}
      <div
        className="flex shrink-0 cursor-grab touch-none justify-center pb-1 pt-2 active:cursor-grabbing"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <button
          type="button"
          className="flex h-6 w-16 items-center justify-center rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          aria-label={`${label} panel, ${SNAP_LABEL[snap]}. Activate to resize.`}
          data-testid="sheet-handle"
          onClick={(e) => {
            // Pointer taps are handled in onPointerUp; keyboard activation arrives with detail 0.
            if (e.detail === 0) choose(ORDER[(ORDER.indexOf(snap) + 1) % ORDER.length] ?? 'half');
          }}
        >
          <span className="h-1.5 w-10 rounded-full bg-slate-300 dark:bg-slate-600" aria-hidden />
        </button>
      </div>
      <section
        aria-label={label}
        className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4"
        // The part of the sheet below the screen edge is padding, so the end of the content can
        // always be scrolled into view at every snap point.
        style={{ paddingBottom: offsetFor(snap) + 24 }}
      >
        {children}
      </section>
    </div>
  );
}
