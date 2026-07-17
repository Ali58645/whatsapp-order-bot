import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  BellOff,
  CheckCircle2,
  ShoppingBag,
  Zap,
} from "lucide-react";
import { api, EventItem } from "../api";
import PageHeader from "../components/ui/PageHeader";
import { eventIconType, relativeTime } from "../lib/utils";

const TYPES = ["", "activation", "confirmed", "stalled", "mute", "human_takeover", "error"];

function EventCard({ ev }: { ev: EventItem }) {
  const kind = eventIconType(ev.type);
  const icons = {
    lead: CheckCircle2,
    order: ShoppingBag,
    mute: BellOff,
    error: AlertTriangle,
    default: Zap,
  };
  const colors = {
    lead: "border-l-bahi-500 bg-bahi-50/30",
    order: "border-l-sky-500 bg-sky-50/30",
    mute: "border-l-amber-500 bg-amber-50/30",
    error: "border-l-red-500 bg-red-50/30",
    default: "border-l-canvas-300",
  };
  const Icon = icons[kind];
  return (
    <li
      className={`rounded-xl border border-canvas-200 border-l-4 bg-white px-4 py-3 shadow-card transition-ui hover:shadow-card-hover ${colors[kind]}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white shadow-sm">
            <Icon className="h-4 w-4 text-ink-600" />
          </div>
          <div>
            <p className="font-semibold capitalize text-ink-900">{ev.type.replace(/_/g, " ")}</p>
            <p className="text-xs text-ink-500">
              {ev.contact?.profile_name || ev.contact?.wa_id || "System"}
            </p>
            {Object.keys(ev.payload || {}).length > 0 && (
              <pre className="mt-2 max-h-20 overflow-auto rounded-lg bg-canvas-50 p-2 text-[10px] text-ink-600">
                {JSON.stringify(ev.payload, null, 2)}
              </pre>
            )}
          </div>
        </div>
        <time className="shrink-0 text-xs font-medium text-ink-400">{relativeTime(ev.created_at)}</time>
      </div>
    </li>
  );
}

export default function ActivityPage() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [type, setType] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setError("");
    setLoading(true);
    const params = new URLSearchParams();
    if (type) params.set("type", type);
    api<{ items: EventItem[] }>(`/api/dashboard/events?${params}`)
      .then((res) => setItems(res.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [type]);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div>
      <PageHeader title="Activity" subtitle="Audit trail from your WhatsApp bots" />

      <div className="mb-4 flex flex-wrap gap-1.5">
        {TYPES.map((t) => (
          <button
            key={t || "all"}
            type="button"
            onClick={() => setType(t)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-ui ${
              type === t
                ? "bg-bahi-600 text-white"
                : "border border-canvas-200 bg-white text-ink-600 hover:border-bahi-200"
            }`}
          >
            {t ? t.replace(/_/g, " ") : "All"}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</p>
      )}

      <ol className="space-y-3">
        {loading &&
          [1, 2, 3].map((i) => (
            <li key={i} className="h-16 animate-shimmer rounded-xl bg-canvas-200" />
          ))}
        {!loading && items.length === 0 && (
          <li className="rounded-2xl border border-dashed border-canvas-300 bg-white py-12 text-center text-sm text-ink-500">
            No events match this filter
          </li>
        )}
        {!loading && items.map((ev) => <EventCard key={ev.id} ev={ev} />)}
      </ol>
    </div>
  );
}
