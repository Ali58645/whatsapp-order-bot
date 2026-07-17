import type { LucideIcon } from "lucide-react";
import { TrendingDown, TrendingUp } from "lucide-react";
import Sparkline from "./Sparkline";

type Props = {
  label: string;
  value: string | number;
  icon: LucideIcon;
  sparkline?: number[];
  delta?: number;
  deltaLabel?: string;
  loading?: boolean;
};

export default function StatCard({
  label,
  value,
  icon: Icon,
  sparkline = [],
  delta,
  deltaLabel = "vs yesterday",
  loading,
}: Props) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-canvas-200 bg-white p-4 shadow-card">
        <div className="h-3 w-24 animate-shimmer rounded bg-canvas-200" />
        <div className="mt-3 h-9 w-20 animate-shimmer rounded bg-canvas-200" />
        <div className="mt-4 h-7 w-full animate-shimmer rounded bg-canvas-200" />
      </div>
    );
  }

  const up = delta !== undefined && delta >= 0;
  const showDelta = delta !== undefined;

  return (
    <div className="group rounded-2xl border border-canvas-200 bg-white p-4 shadow-card transition duration-150 hover:border-bahi-200/60 hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-bahi-50 text-bahi-700 transition duration-150 group-hover:bg-bahi-100">
          <Icon className="h-[1.125rem] w-[1.125rem]" strokeWidth={2} />
        </div>
        {sparkline.length > 0 && <Sparkline values={sparkline} />}
      </div>
      <p className="mt-3 text-xs font-semibold uppercase tracking-wider text-ink-500">{label}</p>
      <p className="mt-1 text-3xl font-extrabold tabular-nums tracking-tight text-ink-900">{value}</p>
      {showDelta && (
        <p className={`mt-2 flex items-center gap-1 text-xs font-medium ${up ? "text-bahi-700" : "text-amber-700"}`}>
          {up ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
          {up ? "+" : ""}
          {delta} {deltaLabel}
        </p>
      )}
    </div>
  );
}
