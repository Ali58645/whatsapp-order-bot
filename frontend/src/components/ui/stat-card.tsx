import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { cn, deltaVsPrior } from "../../lib/utils";
import { CountUp } from "./count-up";
import { SparkArea } from "./spark-area";
import { Skeleton } from "./avatar";

export function StatCard({
  label,
  value,
  series = [],
  prefix = "",
  suffix = "",
  glow = false,
  delay = 0,
  loading,
}: {
  label: string;
  value: number;
  series?: number[];
  prefix?: string;
  suffix?: string;
  glow?: boolean;
  delay?: number;
  loading?: boolean;
}) {
  const spark = series ?? [];
  const { delta, pct } = deltaVsPrior(spark);
  const up = delta >= 0;

  if (loading) {
    return <Skeleton className="h-[148px] w-full rounded-2xl" />;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, delay }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-border bg-card p-5 gradient-border",
        glow && "shadow-glow"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 font-stat text-stat tabular text-foreground">
            <CountUp value={Number(value) || 0} prefix={prefix} suffix={suffix} />
          </p>
        </div>
        {pct != null && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-semibold",
              up ? "bg-primary/15 text-primary" : "bg-destructive/15 text-destructive"
            )}
          >
            {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
            {Math.abs(pct)}%
          </span>
        )}
      </div>
      <div className="mt-3 -mx-1">
        <SparkArea data={spark} />
      </div>
    </motion.div>
  );
}
