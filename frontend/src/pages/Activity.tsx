import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CircleDot,
  Package,
  Sparkles,
  VolumeX,
} from "lucide-react";
import { api, EventItem } from "../api";
import { Skeleton } from "../components/ui/avatar";
import { EmptyState } from "../components/ui/empty-state";
import { cn, eventIconType, relativeTime } from "../lib/utils";

const FILTERS = [
  { id: "", label: "All" },
  { id: "activation", label: "Activation" },
  { id: "confirmed", label: "Confirmed" },
  { id: "stalled", label: "Stalled" },
  { id: "mute", label: "Mute" },
  { id: "human_takeover", label: "Takeover" },
  { id: "error", label: "Error" },
];

export default function Activity() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [type, setType] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api<{ items: EventItem[] }>(
      `/api/dashboard/events?type=${encodeURIComponent(type)}`
    )
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [type]);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Activity</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          What happened on your bot — activations, demos, takeovers
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.id || "all"}
            onClick={() => setType(f.id)}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition",
              type === f.id
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : !items.length ? (
        <EmptyState
          title="No events match this filter"
          description="Try another type or wait for the next lead activation."
          illustration="search"
        />
      ) : (
        <ul className="space-y-2">
          {items.map((ev, idx) => {
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
                className="rounded-2xl border border-border bg-card p-4 transition hover:bg-muted/20"
              >
                <div className="flex items-start gap-3">
                  <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
                    <Icon className="h-4 w-4 text-primary" />
                    {idx === 0 && type === "" && (
                      <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 animate-pulse-dot rounded-full bg-primary ring-2 ring-card" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold capitalize">
                        {ev.type.replace(/_/g, " ")}
                      </p>
                      <span className="text-xs tabular text-muted-foreground">
                        {relativeTime(ev.created_at)}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {ev.contact?.profile_name || ev.contact?.wa_id || "System"}
                    </p>
                    {ev.payload && Object.keys(ev.payload).length > 0 && (
                      <pre className="mt-2 overflow-x-auto rounded-lg bg-muted/50 p-2 text-[11px] text-muted-foreground">
                        {JSON.stringify(ev.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
