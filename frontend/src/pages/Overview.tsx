import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  CircleDot,
  Package,
  RefreshCw,
  Sparkles,
  VolumeX,
  AlertTriangle,
} from "lucide-react";
import { api, Overview as OverviewData } from "../api";
import { StatCard } from "../components/ui/stat-card";
import { Skeleton } from "../components/ui/avatar";
import { EmptyState } from "../components/ui/empty-state";
import { Button } from "../components/ui/button";
import {
  cn,
  eventsByDay,
  eventIconType,
  relativeTime,
} from "../lib/utils";

export default function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api<OverviewData>("/api/dashboard/overview")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  const series = useMemo(
    () => eventsByDay(data?.recent_events || [], 7),
    [data?.recent_events]
  );

  const funnel = useMemo(() => {
    const s = data?.leads_by_status || {};
    const newN = s.new || 0;
    const active = s.active || 0;
    const confirmed = s.confirmed || 0;
    const total = Math.max(newN + active + confirmed, 1);
    return [
      { key: "new", label: "New", count: newN, pct: Math.round((newN / total) * 100) },
      { key: "active", label: "In Progress", count: active, pct: Math.round((active / total) * 100) },
      {
        key: "confirmed",
        label: "Demo Scheduled",
        count: confirmed,
        pct: Math.round((confirmed / total) * 100),
      },
    ];
  }, [data?.leads_by_status]);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Live pipeline across your WhatsApp tenants
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Leads today"
          value={data?.leads_today ?? 0}
          series={series}
          glow
          delay={0}
          loading={loading}
        />
        <StatCard
          label="Demos scheduled"
          value={data?.demos_scheduled ?? 0}
          series={series}
          delay={0.05}
          loading={loading}
        />
        <StatCard
          label="Orders today"
          value={data?.orders_today ?? 0}
          series={series}
          delay={0.1}
          loading={loading}
        />
        <StatCard
          label="Revenue today"
          value={data?.revenue_today ?? 0}
          series={series}
          prefix="Rs "
          delay={0.15}
          loading={loading}
        />
      </div>

      {/* Funnel */}
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Leads funnel</h2>
          <span className="text-xs text-muted-foreground">
            {data?.active_conversations ?? 0} active conversations
          </span>
        </div>
        {loading ? (
          <Skeleton className="mt-4 h-20 w-full" />
        ) : (
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-stretch">
            {funnel.map((step, i) => (
              <motion.div
                key={step.key}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.05 }}
                className="relative flex flex-1 flex-col rounded-xl border border-border bg-muted/30 p-4"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {step.label}
                </p>
                <p className="mt-2 font-stat text-3xl tabular tracking-tight">{step.count}</p>
                <p className="mt-1 text-xs text-primary">{step.pct}% of pipeline</p>
                {i < funnel.length - 1 && (
                  <div className="absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 text-muted-foreground sm:block">
                    →
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </section>

      {/* Activity timeline */}
      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold">Recent activity</h2>
        {loading ? (
          <div className="mt-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !data?.recent_events?.length ? (
          <EmptyState
            className="mt-4 border-0 bg-transparent py-10"
            title="Quiet so far"
            description="New lead activations and demos will pulse here live."
            illustration="inbox"
          />
        ) : (
          <ul className="mt-4 space-y-1">
            {data.recent_events.slice(0, 12).map((ev, idx) => {
              const kind = eventIconType(ev.type);
              const Icon =
                kind === "lead"
                  ? Sparkles
                  : kind === "order"
                    ? Package
                    : kind === "mute"
                      ? VolumeX
                      : kind === "error"
                        ? AlertTriangle
                        : CircleDot;
              return (
                <li
                  key={ev.id}
                  className="flex items-center gap-3 rounded-xl px-2 py-2.5 transition hover:bg-muted/40"
                >
                  <div className="relative flex h-9 w-9 items-center justify-center rounded-full bg-muted">
                    <Icon className="h-4 w-4 text-primary" />
                    {idx === 0 && (
                      <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 animate-pulse-dot rounded-full bg-primary ring-2 ring-card" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium capitalize">
                      {ev.type.replace(/_/g, " ")}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {ev.contact?.profile_name || ev.contact?.wa_id || "—"}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs tabular text-muted-foreground">
                    {relativeTime(ev.created_at)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
