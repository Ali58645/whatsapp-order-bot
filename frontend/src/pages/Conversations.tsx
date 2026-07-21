import { useCallback, useEffect, useState } from "react";
import { api, Lead } from "../api";
import { ChannelBadge } from "../components/ChannelBadge";
import LeadDrawer from "../components/leads/LeadDrawer";
import { Avatar, Skeleton } from "../components/ui/avatar";
import { StatusPill } from "../components/ui/badge";
import { EmptyState } from "../components/ui/empty-state";
import { relativeTime } from "../lib/utils";

/** Active conversations = leads currently in progress / new */
export default function Conversations() {
  const [items, setItems] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api<{ items: Lead[] }>("/api/dashboard/leads?status=active&search="),
      api<{ items: Lead[] }>("/api/dashboard/leads?status=new&search="),
    ])
      .then(([a, n]) => {
        const map = new Map<number, Lead>();
        for (const l of [...a.items, ...n.items]) map.set(l.id, l);
        setItems(
          [...map.values()].sort(
            (x, y) =>
              new Date(y.last_activity || 0).getTime() -
              new Date(x.last_activity || 0).getTime()
          )
        );
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Conversations</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Live chats the bot is handling right now
        </p>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : !items.length ? (
        <EmptyState
          title="No open conversations"
          description="Active and new leads show up here for quick takeover."
          illustration="chat"
        />
      ) : (
        <div className="space-y-2">
          {items.map((lead) => {
            const name =
              lead.business_name ||
              lead.contact.profile_name ||
              lead.contact.wa_id;
            return (
              <button
                key={lead.id}
                onClick={() => setSelected(lead.id)}
                className="flex w-full items-center gap-3 rounded-2xl border border-border bg-card p-3.5 text-left transition hover:border-primary/30 hover:bg-muted/20"
              >
                <div className="relative">
                  <Avatar name={name} seed={lead.contact.wa_id} />
                  <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-primary ring-2 ring-card" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-medium">{name}</p>
                    <ChannelBadge channel={lead.contact.channel} />
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {lead.phase ? `Phase: ${lead.phase}` : lead.contact.wa_id}
                  </p>
                </div>
                <div className="text-right">
                  <StatusPill status={lead.status} />
                  <p className="mt-1 text-[11px] tabular text-muted-foreground">
                    {relativeTime(lead.last_activity)}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {selected != null && (
        <LeadDrawer
          leadId={selected}
          onClose={() => setSelected(null)}
          onMuted={load}
        />
      )}
    </div>
  );
}
