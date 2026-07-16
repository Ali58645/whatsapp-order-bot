import { useCallback, useEffect, useState } from "react";
import { api, Lead } from "../api";
import LeadDrawer from "../components/LeadDrawer";

const STATUSES = ["", "active", "confirmed", "stalled"];

function formatTime(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function LeadsPage() {
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Lead | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (q) params.set("search", q);
    api<{ items: Lead[]; total: number }>(`/api/dashboard/leads?${params}`)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message));
  }, [status, q]);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Leads</h1>
        <p className="text-sm text-ink-600">{total} total · tap a row for details</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex flex-wrap gap-1.5">
          {STATUSES.map((s) => (
            <button
              key={s || "all"}
              type="button"
              onClick={() => setStatus(s)}
              className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${
                status === s
                  ? "bg-ink-900 text-white"
                  : "bg-white text-ink-700 shadow-sm"
              }`}
            >
              {s || "all"}
            </button>
          ))}
        </div>
        <form
          className="flex flex-1 gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(search.trim());
          }}
        >
          <input
            className="w-full rounded-lg border border-ink-900/10 bg-white px-3 py-2 text-sm outline-none ring-sea-500 focus:ring-2"
            placeholder="Search name, business, phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            type="submit"
            className="rounded-lg bg-sea-600 px-3 py-2 text-sm font-medium text-white"
          >
            Search
          </button>
        </form>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="overflow-hidden rounded-2xl bg-white/90 shadow-soft">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-mist-100 bg-mist-50/80 text-xs uppercase tracking-wide text-ink-600">
              <tr>
                <th className="px-4 py-3 font-medium">Business</th>
                <th className="px-4 py-3 font-medium">Contact</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Demo</th>
                <th className="px-4 py-3 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-600">
                    No leads match
                  </td>
                </tr>
              )}
              {items.map((lead) => (
                <tr
                  key={lead.id}
                  className="cursor-pointer border-b border-mist-100 last:border-0 hover:bg-sea-50/40"
                  onClick={() => setSelected(lead)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-ink-900">
                      {lead.business_name || "—"}
                    </p>
                    <p className="text-xs text-ink-600">{lead.business_type}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p>{lead.contact.profile_name || "—"}</p>
                    <p className="font-mono text-xs text-ink-600">{lead.contact.wa_id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-mist-100 px-2 py-0.5 text-xs capitalize">
                      {lead.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{lead.demo_slot || "—"}</td>
                  <td className="px-4 py-3 text-xs text-ink-600">
                    {formatTime(lead.last_activity)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <LeadDrawer
          leadId={selected.id}
          onClose={() => setSelected(null)}
          onMuted={load}
        />
      )}
    </div>
  );
}
