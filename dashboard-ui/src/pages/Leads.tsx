import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import { api, Lead } from "../api";
import LeadDrawer from "../components/LeadDrawer";
import Avatar from "../components/ui/Avatar";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import StatusPill from "../components/ui/StatusPill";
import { relativeTime } from "../lib/utils";

const STATUSES = ["", "active", "confirmed", "stalled"];

function LeadCard({ lead, onClick }: { lead: Lead; onClick: () => void }) {
  const name = lead.business_name || lead.contact.profile_name || "Unknown";
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-xl border border-canvas-200 bg-white p-4 text-left shadow-card transition-ui hover:border-bahi-200 md:hidden"
    >
      <Avatar name={name} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-ink-900">{lead.business_name || "—"}</p>
        <p className="truncate text-xs text-ink-500">{lead.contact.profile_name || lead.contact.wa_id}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusPill status={lead.status} />
          <span className="text-xs text-ink-400">{relativeTime(lead.last_activity)}</span>
        </div>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-ink-300" />
    </button>
  );
}

export default function LeadsPage() {
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setError("");
    setLoading(true);
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (q) params.set("search", q);
    api<{ items: Lead[]; total: number }>(`/api/dashboard/leads?${params}`)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [status, q]);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div>
      <PageHeader title="Leads" subtitle={`${total} total · tap a row for details`} />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex flex-wrap gap-1.5">
          {STATUSES.map((s) => (
            <button
              key={s || "all"}
              type="button"
              onClick={() => setStatus(s)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition-ui ${
                status === s
                  ? "bg-bahi-600 text-white shadow-sm"
                  : "border border-canvas-200 bg-white text-ink-600 hover:border-bahi-200 hover:text-bahi-700"
              }`}
            >
              {s || "All"}
            </button>
          ))}
        </div>
        <form
          className="relative flex flex-1"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(search.trim());
          }}
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            className="w-full rounded-xl border border-canvas-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none transition-ui focus:border-bahi-400 focus:ring-2 focus:ring-bahi-500/15"
            placeholder="Search name, business, phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>
      </div>

      {error && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</p>
      )}

      {/* Mobile cards */}
      <div className="space-y-3 md:hidden">
        {loading &&
          [1, 2, 3].map((i) => (
            <div key={i} className="h-20 animate-shimmer rounded-xl bg-canvas-200" />
          ))}
        {!loading && items.length === 0 && (
          <EmptyState title="No leads yet — your bot is ready" description="Leads appear here when customers message your WhatsApp bot." />
        )}
        {!loading && items.map((lead) => (
          <LeadCard key={lead.id} lead={lead} onClick={() => setSelected(lead)} />
        ))}
      </div>

      {/* Desktop table */}
      <div className="hidden overflow-hidden rounded-2xl border border-canvas-200 bg-white shadow-card md:block">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-canvas-100 bg-canvas-50 text-[11px] font-bold uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-3">Business</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Demo</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3 w-8" />
              </tr>
            </thead>
            <tbody>
              {loading &&
                [1, 2, 3, 4].map((i) => (
                  <tr key={i} className="border-b border-canvas-100">
                    <td colSpan={6} className="px-4 py-4">
                      <div className="h-5 animate-shimmer rounded bg-canvas-200" />
                    </td>
                  </tr>
                ))}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-0">
                    <div className="p-8">
                      <EmptyState
                        title="No leads yet — your bot is ready"
                        description="Leads appear here when customers message your WhatsApp bot."
                      />
                    </div>
                  </td>
                </tr>
              )}
              {!loading &&
                items.map((lead) => {
                  const name = lead.business_name || lead.contact.profile_name || "?";
                  return (
                    <tr
                      key={lead.id}
                      className="group cursor-pointer border-b border-canvas-100 transition-ui last:border-0 hover:bg-bahi-50/40"
                      onClick={() => setSelected(lead)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={name} size="sm" />
                          <div>
                            <p className="font-semibold text-ink-900">{lead.business_name || "—"}</p>
                            <p className="text-xs text-ink-500">{lead.business_type || "—"}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-ink-800">{lead.contact.profile_name || "—"}</p>
                        <p className="font-mono text-xs text-ink-400">{lead.contact.wa_id}</p>
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={lead.status} />
                      </td>
                      <td className="px-4 py-3 text-ink-700">{lead.demo_slot || "—"}</td>
                      <td className="px-4 py-3 text-xs font-medium text-ink-500">
                        {relativeTime(lead.last_activity)}
                      </td>
                      <td className="px-4 py-3">
                        <ChevronRight className="h-4 w-4 text-ink-300 opacity-0 transition-ui group-hover:opacity-100" />
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <LeadDrawer leadId={selected.id} onClose={() => setSelected(null)} onMuted={load} />
      )}
    </div>
  );
}
