import { useCallback, useEffect, useState } from "react";
import {
  Activity as ActivityIcon,
  AlertTriangle,
  BellOff,
  CalendarCheck,
  CheckCircle2,
  MessageCircle,
  ShoppingBag,
  Users,
  Zap,
} from "lucide-react";
import { api, EventItem, Overview } from "../api";
import PageHeader from "../components/ui/PageHeader";
import SegmentedBar from "../components/ui/SegmentedBar";
import StatCard from "../components/ui/StatCard";
import { StatCardSkeleton } from "../components/ui/Skeleton";
import { deltaVsPrior, eventIconType, eventsByDay, relativeTime } from "../lib/utils";

function EventRow({ ev }: { ev: EventItem }) {
  const kind = eventIconType(ev.type);
  const icons = {
    lead: CheckCircle2,
    order: ShoppingBag,
    mute: BellOff,
    error: AlertTriangle,
    default: Zap,
  };
  const colors = {
    lead: "bg-bahi-100 text-bahi-700",
    order: "bg-sky-100 text-sky-700",
    mute: "bg-amber-100 text-amber-800",
    error: "bg-red-100 text-red-700",
    default: "bg-canvas-200 text-ink-600",
  };
  const Icon = icons[kind];
  return (
    <li className="flex gap-3 border-b border-canvas-100 py-3 last:border-0">
      <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${colors[kind]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold capitalize text-ink-900">{ev.type.replace(/_/g, " ")}</p>
        <p className="truncate text-xs text-ink-500">
          {ev.contact?.profile_name || ev.contact?.wa_id || "System"}
        </p>
      </div>
      <time className="shrink-0 text-xs font-medium text-ink-400">{relativeTime(ev.created_at)}</time>
    </li>
  );
}

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setError("");
    setLoading(true);
    api<Overview>("/api/dashboard/overview")
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  const spark = data ? eventsByDay(data.recent_events) : [];
  const sparkDelta = deltaVsPrior(spark);

  if (error) {
    return (
      <div>
        <PageHeader title="Overview" subtitle="Today's pulse across your WhatsApp bots" />
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Today's pulse across your WhatsApp bots"
        action={
          <button
            type="button"
            onClick={load}
            className="rounded-xl border border-canvas-200 bg-white px-3 py-2 text-sm font-semibold text-ink-700 shadow-card transition-ui hover:border-bahi-200 hover:text-bahi-700"
          >
            Refresh
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        {loading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <StatCard
              label="Leads today"
              value={data!.leads_today}
              icon={Users}
              sparkline={spark}
              delta={data!.leads_today - Math.max(0, Math.round((data!.leads_this_week - data!.leads_today) / 6))}
              deltaLabel="vs daily avg"
            />
            <StatCard
              label="Demos scheduled"
              value={data!.demos_scheduled}
              icon={CalendarCheck}
              sparkline={spark}
              delta={sparkDelta.delta}
            />
            <StatCard
              label="Orders today"
              value={data!.orders_today}
              icon={ShoppingBag}
              sparkline={spark}
              delta={sparkDelta.delta}
            />
            <StatCard
              label="Revenue today"
              value={`Rs ${data!.revenue_today.toLocaleString()}`}
              icon={MessageCircle}
              sparkline={spark}
              delta={sparkDelta.delta}
            />
          </>
        )}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2 lg:gap-6">
        <section className="rounded-2xl border border-canvas-200 bg-white p-5 shadow-card">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-bold text-ink-900">Leads by status</h2>
            {!loading && (
              <span className="text-xs font-medium text-ink-500">
                {data!.active_conversations} active chat{data!.active_conversations === 1 ? "" : "s"}
              </span>
            )}
          </div>
          {loading ? (
            <div className="h-24 animate-shimmer rounded-xl bg-canvas-200" />
          ) : (
            <SegmentedBar data={data!.leads_by_status} />
          )}
        </section>

        <section className="rounded-2xl border border-canvas-200 bg-white p-5 shadow-card">
          <div className="mb-1 flex items-center gap-2">
            <ActivityIcon className="h-4 w-4 text-bahi-600" />
            <h2 className="text-sm font-bold text-ink-900">Recent activity</h2>
          </div>
          <ul className="mt-2 max-h-80 overflow-y-auto">
            {loading && (
              <li className="py-8 text-center text-sm text-ink-500">Loading activity…</li>
            )}
            {!loading && data!.recent_events.length === 0 && (
              <li className="py-8 text-center text-sm text-ink-500">No events yet</li>
            )}
            {!loading && data!.recent_events.map((ev) => <EventRow key={ev.id} ev={ev} />)}
          </ul>
        </section>
      </div>
    </div>
  );
}
