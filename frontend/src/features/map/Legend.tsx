import { useRiskRules } from '../../api/queries';
import type { RiskLevel } from '../../api/types';
import { colorOf, isRiskLevel, labelOf, LEVEL_ICONS } from '../../lib/risk';

/** Built from GET /risk-rules/ (single source of truth). Renders nothing until loaded. */
export function Legend() {
  const { data } = useRiskRules();
  if (!data) return null;
  const levels = data.levels.filter(isRiskLevel) as RiskLevel[];
  return (
    <div
      className="surface pointer-events-auto w-fit max-w-full rounded-2xl px-3.5 py-2 text-xs font-medium"
      aria-label="Risk legend"
    >
      <ul className="flex flex-wrap gap-x-3 gap-y-1">
        {levels.map((level) => (
          <li key={level} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: colorOf(level) }}
              aria-hidden
            />
            <span aria-hidden>{LEVEL_ICONS[level]}</span>
            {labelOf(level)}
          </li>
        ))}
      </ul>
    </div>
  );
}
