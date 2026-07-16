import { useCallback, useEffect, useState } from "react";
import { api, EventItem, Overview } from "../api";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-2xl bg-white/90 p-4 shadow-soft">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-600">{label}</p>
      <p className="mt-1 font-display text-3xl font-semibold text-ink-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-600">{hint}</p>}
    </div>
  );
}

function formatTime(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    api<Overview>("/api/dashboard/overview")
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load"));
  }, []);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }
  if (!data) {
    return <p className="text-sm text-ink-600">Loading overview…</p>;
  }

  const statusEntries = Object.entries(data.leads_by_status);
  const statusMax = Math.max(1, ...statusEntries.map(([, n]) => n));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Overview</h1>
        <p className="text-sm text-ink-600">Today’s pulse across your WhatsApp bots</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Leads today" value={data.leads_today} hint={`${data.leads_this_week} this week`} />
        <Stat label="Demos scheduled" value={data.demos_scheduled} />
        <Stat label="Orders today" value={data.orders_today} />
        <Stat label="Revenue today" value={`Rs ${data.revenue_today.toLocaleString()}`} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-2xl bg-white/90 p-4 shadow-soft">
          <h2 className="text-sm font-semibold text-ink-900">Leads by status</h2>
          <ul className="mt-3 space-y-2">
            {statusEntries.length === 0 && (
              <li className="text-sm text-ink-600">No leads yet</li>
            )}
            {statusEntries.map(([status, count]) => (
              <li key={status}>
                <div className="mb-1 flex justify-between text-xs">
                  <span className="capitalize text-ink-700">{status}</span>
                  <span className="font-medium text-ink-900">{count}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-mist-100">
                  <div
                    className="h-full rounded-full bg-sea-500 transition-all duration-500"
                    style={{ width: `${(count / statusMax) * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-ink-600">
            {data.active_conversations} active conversation
            {data.active_conversations === 1 ? "" : "s"}
          </p>
        </section>

        <section className="rounded-2xl bg-white/90 p-4 shadow-soft">
          <h2 className="text-sm font-semibold text-ink-900">Recent activity</h2>
          <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto">
            {data.recent_events.length === 0 && (
              <li className="text-sm text-ink-600">No events yet</li>
            )}
            {data.recent_events.map((ev: EventItem) => (
              <li
                key={ev.id}
                className="flex items-start justify-between gap-2 border-b border-mist-100 pb-2 text-sm last:border-0"
              >
                <div>
                  <p className="font-medium text-ink-900">{ev.type}</p>
                  <p className="text-xs text-ink-600">
                    {ev.contact?.profile_name || ev.contact?.wa_id || "—"}
                  </p>
                </div>
                <time className="shrink-0 text-xs text-ink-600">
                  {formatTime(ev.created_at)}
                </time>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
