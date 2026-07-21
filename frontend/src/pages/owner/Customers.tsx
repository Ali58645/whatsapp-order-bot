import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CalendarClock, Download, MessageCircle, Search } from "lucide-react";
import { toast } from "sonner";
import { api, downloadAuthenticated, fetchMe, Lead } from "../../api";
import { ChannelBadge } from "../../components/ChannelBadge";
import LeadDrawer from "../../components/leads/LeadDrawer";
import { Avatar, Skeleton } from "../../components/ui/avatar";
import { StatusPill } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { EmptyState } from "../../components/ui/empty-state";
import { Input } from "../../components/ui/input";
import { cn, relativeTime } from "../../lib/utils";
import Orders from "../Orders";

/** Owner-facing status chips — plain language, not CRM jargon. */
const STATUS_FILTERS = [
  { id: "", label: "All", hint: "Everyone who messaged you" },
  { id: "new", label: "New", hint: "Just started chatting" },
  { id: "active", label: "Talking", hint: "Bot is collecting answers" },
  { id: "confirmed", label: "Demo booked", hint: "They picked a demo time" },
  { id: "stalled", label: "Quiet", hint: "Stopped replying" },
] as const;

function leadName(lead: Lead): string {
  return lead.business_name || lead.contact.profile_name || lead.contact.wa_id;
}

function LeadCustomers() {
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);

  const openFromUrl = params.get("open");

  const load = useCallback(() => {
    setLoading(true);
    const qs = new URLSearchParams({
      search,
      limit: "100",
      offset: "0",
    });
    api<{ items: Lead[]; total: number }>(`/api/dashboard/leads?${qs}`)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [search]);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  useEffect(() => {
    if (openFromUrl) {
      setSelected(Number(openFromUrl));
      setParams({}, { replace: true });
    }
  }, [openFromUrl, setParams]);

  useEffect(() => {
    const t = setTimeout(() => setSearch(q.trim()), 220);
    return () => clearTimeout(t);
  }, [q]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { "": items.length };
    for (const l of items) {
      const k = (l.status || "new").toLowerCase();
      c[k] = (c[k] || 0) + 1;
    }
    return c;
  }, [items]);

  const filtered = useMemo(() => {
    if (!status) return items;
    return items.filter((l) => (l.status || "new").toLowerCase() === status);
  }, [items, status]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Customers</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Who messaged your bot · filter by where they are in the flow
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            void downloadAuthenticated("/api/dashboard/export/leads.csv", "customers.csv")
              .then(() => toast.success("Download started"))
              .catch((e: unknown) =>
                toast.error(e instanceof Error ? e.message : "Export failed")
              );
          }}
        >
          <Download className="mr-1.5 h-3.5 w-3.5" />
          Export CSV
        </Button>
      </div>

      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name or number…"
          className="pl-9"
          aria-label="Search customers"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.id || "all"}
            type="button"
            title={f.hint}
            onClick={() => setStatus(f.id)}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition",
              status === f.id
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {f.label}
            <span className="ml-1.5 opacity-70">
              {f.id === "" ? total : counts[f.id] || 0}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-[72px] w-full rounded-2xl" />
          ))}
        </div>
      ) : !filtered.length ? (
        <EmptyState
          title={status ? "No one in this status" : "No customers yet"}
          description={
            status
              ? "Try All, or wait for the bot to move people here."
              : "When someone messages WhatsApp, they show up here with a clear status."
          }
          illustration="inbox"
        />
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
          {filtered.map((lead) => {
            const name = leadName(lead);
            const demo = lead.demo_slot?.trim();
            return (
              <li key={lead.id}>
                <div className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:gap-4">
                  <button
                    type="button"
                    onClick={() => setSelected(lead.id)}
                    className="flex min-w-0 flex-1 items-start gap-3 text-left transition hover:opacity-90"
                  >
                    <Avatar name={name} seed={lead.contact.wa_id} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-medium">{name}</p>
                        <ChannelBadge channel={lead.contact.channel} />
                        <StatusPill status={lead.status} />
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {lead.contact.wa_id}
                        {lead.business_type ? ` · ${lead.business_type}` : ""}
                      </p>
                      {demo ? (
                        <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-primary">
                          <CalendarClock className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">Demo: {demo}</span>
                        </p>
                      ) : null}
                    </div>
                    <p className="shrink-0 text-[11px] tabular text-muted-foreground sm:pt-1">
                      {relativeTime(lead.last_activity)}
                    </p>
                  </button>
                  <div className="flex shrink-0 gap-2 sm:flex-col sm:items-stretch lg:flex-row">
                    <Button
                      size="sm"
                      variant="soft"
                      className="flex-1 sm:flex-none"
                      onClick={() => setSelected(lead.id)}
                    >
                      Details
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1 sm:flex-none" asChild>
                      <Link to={`/conversations?open=${lead.id}`}>
                        <MessageCircle className="mr-1.5 h-3.5 w-3.5" />
                        Chat
                      </Link>
                    </Button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
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

/** Owner pipeline — leads or orders based on their tenant flow_mode. */
export default function Customers() {
  const [mode, setMode] = useState<"lead" | "order" | null>(null);

  useEffect(() => {
    fetchMe()
      .then((me) => setMode(me.tenant?.flow_mode === "order" ? "order" : "lead"))
      .catch(() => setMode("lead"));
  }, []);

  if (!mode) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  return mode === "order" ? <Orders /> : <LeadCustomers />;
}
