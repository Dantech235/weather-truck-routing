import type { Checkpoint } from '../../api/types';
import { formatLocalTime } from '../../lib/format';
import { LevelChip } from '../routes/LevelChip';

export function CheckpointPopup({ route, checkpoint }: { route: string; checkpoint: Checkpoint }) {
  const r = checkpoint.risk;
  return (
    <div
      className="min-w-[160px] text-slate-900 dark:text-slate-100"
      data-testid="checkpoint-popup"
    >
      <p className="text-xs text-slate-500 dark:text-slate-400">Route {route}</p>
      <p className="font-semibold tabular-nums">Mile {checkpoint.mile.toFixed(1)}</p>
      <p className="text-sm tabular-nums">ETA {formatLocalTime(checkpoint.eta_utc)}</p>
      <div className="mt-1 flex flex-wrap items-center gap-1">
        <LevelChip level={r.level} />
        {r.drivers.length > 0 && r.level !== 'UNKNOWN' && (
          <span className="text-xs text-slate-600 dark:text-slate-300">{r.drivers.join(', ')}</span>
        )}
      </div>
    </div>
  );
}
