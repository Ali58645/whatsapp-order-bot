import { useCallback, useEffect, useState } from "react";
import { api, EventItem } from "../api";

const TYPES = ["", "activation", "confirmed", "stalled", "mute", "human_takeover", "error"];

function formatTime(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ActivityPage() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [type, setType] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    const params = new URLSearchParams();
    if (type) params.set("type", type);
    api<{ items: EventItem[] }>(`/api/dashboard/events?${params}`)
      .then((res) => setItems(res.items))
      .catch((e) => setError(e.message));
  }, [type]);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Activity</h1>
        <p className="text-sm text-ink-600">Audit trail from the bot</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {TYPES.map((t) => (
          <button
            key={t || "all"}
            type="button"
            onClick={() => setType(t)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              type === t ? "bg-ink-900 text-white" : "bg-white text-ink-700 shadow-sm"
            }`}
          >
            {t || "all"}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <ol className="space-y-3">
        {items.length === 0 && (
          <li className="rounded-2xl bg-white/90 p-6 text-center text-sm text-ink-600 shadow-soft">
            No events
          </li>
        )}
        {items.map((ev) => (
          <li
            key={ev.id}
            className="rounded-2xl bg-white/90 px-4 py-3 shadow-soft animate-fade-up"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-ink-900">{ev.type}</p>
                <p className="text-xs text-ink-600">
                  {ev.contact?.profile_name || ev.contact?.wa_id || "system"}
                </p>
                {Object.keys(ev.payload || {}).length > 0 && (
                  <pre className="mt-2 max-h-24 overflow-auto rounded-lg bg-mist-50 p-2 text-[11px] text-ink-700">
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                )}
              </div>
              <time className="shrink-0 text-xs text-ink-600">
                {formatTime(ev.created_at)}
              </time>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
