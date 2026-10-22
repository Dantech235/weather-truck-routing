import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { useRef } from 'react';
import { MOTION, withMotion } from './timelines';

interface Props {
  value: number;
  format: (n: number) => string;
  className?: string;
}

/**
 * Counts from 0 to `value` by writing textContent through a ref (no React state per frame).
 * Screen readers get the final value from a visually hidden twin.
 */
export function CountUp({ value, format, className }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const final = format(value);

  useGSAP(
    () => {
      const el = ref.current;
      if (!el) return;
      const mm = withMotion((reduce) => {
        if (reduce) {
          el.textContent = final;
          return;
        }
        const proxy = { v: 0 };
        gsap.to(proxy, {
          v: value,
          duration: MOTION.countUp,
          ease: 'power1.out',
          onUpdate: () => {
            el.textContent = format(proxy.v);
          },
          onComplete: () => {
            el.textContent = final;
          },
        });
      });
      return () => mm.revert();
    },
    { dependencies: [value] },
  );

  return (
    <span className={className}>
      <span ref={ref} aria-hidden>
        {final}
      </span>
      <span className="sr-only">{final}</span>
    </span>
  );
}
