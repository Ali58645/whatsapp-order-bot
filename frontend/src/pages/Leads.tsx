import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowUpDown, Search } from "lucide-react";
import { api, Lead } from "../api";
import { ChannelBadge } from "../components/ChannelBadge";
import LeadDrawer from "../components/leads/LeadDrawer";
import { Avatar, Skeleton } from "../components/ui/avatar";
import { StatusPill } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { EmptyState } from "../components/ui/empty-state";
import { Input } from "../components/ui/input";
import { cn, relativeTime } from "../lib/utils";

const STATUS_FILTERS = [
  { id: "", label: "All" },
  { id: "active", label: "Talking" },
  { id: "confirmed", label: "Demo booked" },
  { id: "stalled", label: "Quiet" },
  { id: "new", label: "New" },
];

const CHANNEL_FILTERS = [
  { id: "", label: "All channels" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "instagram", label: "Instagram" },
  { id: "messenger", label: "Messenger" },
];

type SortKey = "business" | "status" | "activity";

export default function Leads() {
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [sort, setSort] = useState<SortKey>("activity");
  const [asc, setAsc] = useState(false);

  const openFromUrl = params.get("open");

  const load = useCallback(() => {
    setLoading(true);
    api<{ items: Lead[]; total: number }>(
      `/api/dashboard/leads?status=${encodeURIComponent(status)}&search=${encodeURIComponent(search)}&channel=${encodeURIComponent(channel)}`
    )
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [status, search, channel]);

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

  // Debounced search-as-you-type
  useEffect(() => {
    const t = setTimeout(() => setSearch(q), 220);
    return () => clearTimeout(t);
  }, [q]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { "": total };
    for (const l of items) {
      const k = (l.status || "new").toLowerCase();
      c[k] = (c[k] || 0) + 1;
    }
    return c;
  }, [items, total]);

  const sorted = useMemo(() => {
    const arr = [...items];
    arr.sort((a, b) => {
      let cmp = 0;
      if (sort === "business") {
        cmp = (a.business_name || "").localeCompare(b.business_name || "");
      } else if (sort === "status") {
        cmp = (a.status || "").localeCompare(b.status || "");
      } else {
        cmp =
          new Date(a.last_activity || 0).getTime() -
          new Date(b.last_activity || 0).getTime();
      }
      return asc ? cmp : -cmp;
    });
    return arr;
  }, [items, sort, asc]);

  function toggleSort(key: SortKey) {
    if (sort === key) setAsc(!asc);
    else {
      setSort(key);
      setAsc(key === "business");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Leads</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {total} lead{total === 1 ? "" : "s"} in view
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search name, phone, business…"
            className="pl-9"
            aria-label="Search leads"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {CHANNEL_FILTERS.map((f) => (
          <button
            key={f.id || "all-ch"}
            type="button"
            onClick={() => setChannel(f.id)}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition",
              channel === f.id
                ? "bg-primary/20 text-primary ring-1 ring-primary/40"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.id || "all"}
            onClick={() => setStatus(f.id)}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition",
              status === f.id
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {f.label}
            {f.id === "" || counts[f.id] != null ? (
              <span className="ml-1.5 opacity-70">{f.id === "" ? total : counts[f.id] || 0}</span>
            ) : null}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : !sorted.length ? (
        <EmptyState
          title="No leads yet — your bot is ready"
          description="When campaigns activate, leads land here with full transcripts."
          illustration="inbox"
        />
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-hidden rounded-2xl border border-border md:block">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-semibold">
                    <button className="inline-flex items-center gap-1" onClick={() => toggleSort("business")}>
                      Lead <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3 font-semibold">
                    <button className="inline-flex items-center gap-1" onClick={() => toggleSort("status")}>
                      Status <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3 font-semibold">Demo</th>
                  <th className="px-4 py-3 font-semibold">
                    <button className="inline-flex items-center gap-1" onClick={() => toggleSort("activity")}>
                      Activity <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((lead, i) => {
                  const name =
                    lead.business_name ||
                    lead.contact.profile_name ||
                    lead.contact.wa_id;
                  return (
                    <motion.tr
                      key={lead.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(i * 0.02, 0.2) }}
                      onClick={() => setSelected(lead.id)}
                      className="group cursor-pointer border-t border-border transition hover:bg-muted/30 hover:shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.15)]"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={name} seed={lead.contact.wa_id} />
                          <div className="min-w-0">
                            <p className="flex items-center gap-2 truncate font-medium">
                              {name}
                              <ChannelBadge channel={lead.contact.channel} />
                            </p>
                            <p className="truncate text-xs text-muted-foreground">
                              {lead.contact.wa_id}
                              {lead.business_type ? ` · ${lead.business_type}` : ""}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={lead.status} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {lead.demo_slot || "—"}
                      </td>
                      <td className="px-4 py-3 tabular text-muted-foreground">
                        {relativeTime(lead.last_activity)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="sm"
                          variant="soft"
                          className="opacity-0 transition group-hover:opacity-100"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelected(lead.id);
                          }}
                        >
                          Open
                        </Button>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="space-y-2 md:hidden">
            {sorted.map((lead) => {
              const name =
                lead.business_name ||
                lead.contact.profile_name ||
                lead.contact.wa_id;
              return (
                <button
                  key={lead.id}
                  onClick={() => setSelected(lead.id)}
                  className="flex w-full items-center gap-3 rounded-2xl border border-border bg-card p-3 text-left transition hover:border-primary/30"
                >
                  <Avatar name={name} seed={lead.contact.wa_id} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {relativeTime(lead.last_activity)}
                    </p>
                  </div>
                  <StatusPill status={lead.status} />
                </button>
              );
            })}
          </div>
        </>
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
