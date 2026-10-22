import clsx from 'clsx';
import type { RiskLevel } from '../../api/types';
import { colorOf, labelOf, LEVEL_ICONS, onColorOf } from '../../lib/risk';

/** Risk level as text + icon on its colour — never colour alone. */
export function LevelChip({ level, className }: { level: RiskLevel; className?: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold',
        className,
      )}
      style={{ backgroundColor: colorOf(level), color: onColorOf(level) }}
    >
      <span aria-hidden>{LEVEL_ICONS[level]}</span>
      {labelOf(level)}
    </span>
  );
}
