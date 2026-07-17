import { STATUS_BAR_COLORS } from "../../lib/utils";
import { leadStatus } from "../../lib/utils";

type Props = { data: Record<string, number> };

export default function SegmentedBar({ data }: Props) {
  const entries = Object.entries(data).filter(([, n]) => n > 0);
  const total = entries.reduce((s, [, n]) => s + n, 0) || 1;

  if (!entries.length) {
    return (
      <div className="rounded-xl bg-canvas-100 px-4 py-8 text-center text-sm text-ink-500">
        No leads yet — pipeline will appear here
      </div>
    );
  }

  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-canvas-200">
        {entries.map(([status, count]) => (
          <div
            key={status}
            className="h-full transition-all duration-500 first:rounded-l-full last:rounded-r-full"
            style={{
              width: `${(count / total) * 100}%`,
              backgroundColor: STATUS_BAR_COLORS[status.toLowerCase()] ?? "#64748b",
            }}
            title={`${leadStatus(status).label}: ${count}`}
          />
        ))}
      </div>
      <ul className="mt-4 space-y-2">
        {entries.map(([status, count]) => {
          const { label } = leadStatus(status);
          const color = STATUS_BAR_COLORS[status.toLowerCase()] ?? "#64748b";
          return (
            <li key={status} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2 text-ink-700">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                {label}
              </span>
              <span className="font-semibold tabular-nums text-ink-900">{count}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
