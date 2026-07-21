import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Hand, MessageCircle, Search } from "lucide-react";
import { api, Lead } from "../api";
import { ChannelBadge } from "../components/ChannelBadge";
import { ConversationPhone } from "../components/conversations/ConversationPhone";
import { Avatar, Skeleton } from "../components/ui/avatar";
import { EmptyState } from "../components/ui/empty-state";
import { Input } from "../components/ui/input";
import { cn, relativeTime } from "../lib/utils";

type InboxFilter = "all" | "you" | "bot";

const INBOX_FILTERS: { id: InboxFilter; label: string; hint: string }[] = [
  { id: "all", label: "All", hint: "Every chat" },
  { id: "you", label: "You handle", hint: "Human takeover on" },
  { id: "bot", label: "Bot handles", hint: "Bot is replying" },
];

function leadName(lead: Lead): string {
  return lead.business_name || lead.contact.profile_name || lead.contact.wa_id;
}

function previewText(lead: Lead): string {
  if (lead.last_message_preview) {
    const who =
      lead.last_message_role === "human_agent"
        ? "You: "
        : lead.last_message_role === "assistant"
          ? "Bot: "
          : "";
    return `${who}${lead.last_message_preview}`;
  }
  const hist = lead.history;
  if (hist?.length) return hist[hist.length - 1].content;
  return "Tap to open chat";
}

export default function Conversations() {
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [inbox, setInbox] = useState<InboxFilter>("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const openFromUrl = params.get("open");

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      const silent = opts?.silent ?? false;
      if (!silent) setLoading(true);
      try {
        const params = new URLSearchParams({
          search: q,
          limit: "80",
          offset: "0",
        });
        const r = await api<{ items: Lead[]; total: number }>(
          `/api/dashboard/leads?${params}`
        );
        setItems(r.items);
        setTotal(r.total);
      } catch {
        if (!silent) {
          setItems([]);
          setTotal(0);
        }
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [q]
  );

  useEffect(() => {
    void load({ silent: false });
    const onTenant = () => void load({ silent: false });
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  // Poll only while tab is visible — was every 5s even in background
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState !== "visible") return;
      void load({ silent: true });
    };
    const id = window.setInterval(tick, 10_000);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    const t = window.setTimeout(() => setQ(search.trim()), 300);
    return () => window.clearTimeout(t);
  }, [search]);

  const filtered = useMemo(() => {
    if (inbox === "you") return items.filter((l) => l.human_takeover);
    if (inbox === "bot") return items.filter((l) => !l.human_takeover);
    return items;
  }, [items, inbox]);

  const selected = useMemo(
    () => filtered.find((l) => l.id === selectedId) || items.find((l) => l.id === selectedId) || null,
    [filtered, items, selectedId]
  );

  // Deep link from Customers “Chat”
  useEffect(() => {
    if (!openFromUrl) return;
    const id = Number(openFromUrl);
    if (!Number.isFinite(id)) return;
    setSelectedId(id);
    setInbox("all");
    setParams({}, { replace: true });
  }, [openFromUrl, setParams]);

  // Auto-pick first chat on desktop when nothing selected
  useEffect(() => {
    if (loading || selectedId != null || !filtered.length || openFromUrl) return;
    if (typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches) {
      setSelectedId(filtered[0].id);
    }
  }, [loading, filtered, selectedId, openFromUrl]);

  const showPhone = selected !== null;
  const listHiddenOnMobile = showPhone;
  const youCount = items.filter((l) => l.human_takeover).length;

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-[480px] flex-col gap-4 lg:flex-row">
      <section
        className={cn(
          "flex w-full flex-col overflow-hidden rounded-2xl border border-border bg-card lg:w-[min(100%,380px)] lg:shrink-0",
          listHiddenOnMobile && "hidden lg:flex"
        )}
      >
        <div className="border-b border-border px-4 py-4">
          <h1 className="text-xl font-bold tracking-tight">Conversations</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Open a chat → reply or take over · {total} total
            {youCount > 0 ? ` · ${youCount} with you` : ""}
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
            {INBOX_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                title={f.hint}
                onClick={() => setInbox(f.id)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[11px] font-medium transition",
                  inbox === f.id
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:bg-muted/50"
                )}
              >
                {f.label}
                {f.id === "you" && youCount > 0 ? ` (${youCount})` : ""}
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
          ) : !filtered.length ? (
            <div className="p-4">
              <EmptyState
                title={inbox === "you" ? "No chats you’re handling" : "No conversations yet"}
                description={
                  inbox === "you"
                    ? "Turn on Human takeover in a chat to move it here."
                    : "When someone messages your bot, their chat appears here."
                }
                illustration="chat"
              />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {filtered.map((lead) => {
                const name = leadName(lead);
                const active = selectedId === lead.id;
                const takeover = Boolean(lead.human_takeover);
                return (
                  <li key={lead.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(lead.id)}
                      className={cn(
                        "flex w-full items-start gap-3 px-4 py-3.5 text-left transition",
                        active ? "bg-primary/10" : "hover:bg-muted/30"
                      )}
                    >
                      <div className="relative">
                        <Avatar name={name} seed={lead.contact.wa_id} />
                        {takeover && (
                          <span className="absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-black ring-2 ring-card">
                            <Hand className="h-2.5 w-2.5" />
                          </span>
                        )}
                      </div>
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
                        {takeover ? (
                          <span className="inline-flex rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
                            You
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                            Bot
                          </span>
                        )}
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
            onBack={() => setSelectedId(null)}
            onUpdated={() => void load({ silent: true })}
          />
        ) : !loading && filtered.length ? (
          <div className="max-w-sm text-center text-muted-foreground">
            <MessageCircle className="mx-auto h-12 w-12 opacity-30" />
            <p className="mt-4 text-sm font-medium text-foreground">Select a conversation</p>
            <p className="mt-1 text-xs">
              1) Pick a chat · 2) Turn on Human takeover if you want to reply · 3) Type below the phone
            </p>
          </div>
        ) : !loading && !filtered.length ? null : (
          <Skeleton className="h-[600px] w-full max-w-[380px] rounded-[2.75rem]" />
        )}
      </section>
    </div>
  );
}
