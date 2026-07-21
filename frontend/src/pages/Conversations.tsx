import { useCallback, useEffect, useMemo, useState } from "react";
import { MessageCircle, Search } from "lucide-react";
import { api, Lead } from "../api";
import { ChannelBadge } from "../components/ChannelBadge";
import { ConversationPhone } from "../components/conversations/ConversationPhone";
import { Avatar, Skeleton } from "../components/ui/avatar";
import { StatusPill } from "../components/ui/badge";
import { EmptyState } from "../components/ui/empty-state";
import { Input } from "../components/ui/input";
import { cn, relativeTime } from "../lib/utils";

const STATUS_FILTERS = [
  { id: "", label: "All" },
  { id: "active", label: "In progress" },
  { id: "new", label: "New" },
  { id: "confirmed", label: "Scheduled" },
  { id: "stalled", label: "Quiet" },
];

function leadName(lead: Lead): string {
  return lead.business_name || lead.contact.profile_name || lead.contact.wa_id;
}

function previewText(lead: Lead): string {
  if (lead.last_message_preview) return lead.last_message_preview;
  const hist = lead.history;
  if (hist?.length) return hist[hist.length - 1].content;
  return lead.phase ? `Phase: ${lead.phase}` : "No messages yet";
}

export default function Conversations() {
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Lead | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({
      search: q,
      limit: "100",
      offset: "0",
    });
    if (status) params.set("status", status);
    api<{ items: Lead[]; total: number }>(`/api/dashboard/leads?${params}`)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [q, status]);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  useEffect(() => {
    const t = window.setTimeout(() => setQ(search.trim()), 300);
    return () => window.clearTimeout(t);
  }, [search]);

  const showPhone = selected !== null;
  const listHiddenOnMobile = showPhone;

  const emptySelection = useMemo(
    () => !loading && items.length > 0 && !selected,
    [loading, items.length, selected]
  );

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-[480px] flex-col gap-4 lg:flex-row">
      {/* Conversation list */}
      <section
        className={cn(
          "flex w-full flex-col overflow-hidden rounded-2xl border border-border bg-card lg:w-[min(100%,380px)] lg:shrink-0",
          listHiddenOnMobile && "hidden lg:flex"
        )}
      >
        <div className="border-b border-border px-4 py-4">
          <h1 className="text-xl font-bold tracking-tight">Conversations</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Every lead chat with your bot · {total} total
          </p>
          <div className="relative mt-3">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name or number…"
              className="pl-9"
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.id || "all"}
                type="button"
                onClick={() => setStatus(f.id)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[11px] font-medium transition",
                  status === f.id
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:bg-muted/50"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {loading ? (
            <div className="space-y-2 p-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-[72px] w-full rounded-xl" />
              ))}
            </div>
          ) : !items.length ? (
            <div className="p-4">
              <EmptyState
                title="No conversations yet"
                description="When someone messages your bot, their full chat appears here."
                illustration="chat"
              />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {items.map((lead) => {
                const name = leadName(lead);
                const active = selected?.id === lead.id;
                return (
                  <li key={lead.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(lead)}
                      className={cn(
                        "flex w-full items-start gap-3 px-4 py-3.5 text-left transition",
                        active ? "bg-primary/10" : "hover:bg-muted/30"
                      )}
                    >
                      <Avatar name={name} seed={lead.contact.wa_id} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="truncate font-medium">{name}</p>
                          <ChannelBadge channel={lead.contact.channel} />
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {previewText(lead)}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <StatusPill status={lead.status} />
                        <p className="mt-1 text-[10px] tabular text-muted-foreground">
                          {relativeTime(lead.last_activity)}
                        </p>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      {/* Phone preview */}
      <section
        className={cn(
          "flex min-h-0 flex-1 flex-col items-center justify-center rounded-2xl border border-border bg-muted/20 p-4 lg:p-8",
          !showPhone && "hidden lg:flex"
        )}
      >
        {selected && selected.contact_id ? (
          <ConversationPhone
            key={selected.contact_id}
            contactId={selected.contact_id}
            leadId={selected.id}
            sessionId={selected.session_id}
            tenantDbId={selected.tenant_id}
            contactName={leadName(selected)}
            channel={selected.contact.channel}
            waId={selected.contact.wa_id}
            phase={selected.phase}
            onBack={() => setSelected(null)}
            onUpdated={load}
          />
        ) : emptySelection ? (
          <div className="max-w-sm text-center text-muted-foreground">
            <MessageCircle className="mx-auto h-12 w-12 opacity-30" />
            <p className="mt-4 text-sm font-medium text-foreground">Select a conversation</p>
            <p className="mt-1 text-xs">
              Pick a lead on the left to open their WhatsApp-style chat with your bot.
            </p>
          </div>
        ) : !loading && !items.length ? null : (
          <Skeleton className="h-[600px] w-full max-w-[380px] rounded-[2.75rem]" />
        )}
      </section>
    </div>
  );
}
