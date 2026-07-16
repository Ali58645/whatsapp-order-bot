import { useEffect, useState } from "react";
import { api, getTenantFilter, Lead } from "../api";
import Bubbles from "./Bubbles";

type Props = {
  leadId: number;
  onClose: () => void;
  onMuted?: () => void;
};

export default function LeadDrawer({ leadId, onClose, onMuted }: Props) {
  const [lead, setLead] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    api<Lead>(`/api/dashboard/leads/${leadId}`, { tenant: false })
      .then(async (data) => {
        setLead(data);
        if (data.contact_id) {
          try {
            const conv = await api<{ muted_until: string | null }>(
              `/api/dashboard/conversations/${data.contact_id}`,
              { tenant: false }
            );
            setMuted(Boolean(conv.muted_until && new Date(conv.muted_until) > new Date()));
          } catch {
            setMuted(false);
          }
        }
      })
      .catch((e) => setError(e.message));
  }, [leadId]);

  async function toggleMute() {
    if (!lead) return;
    setBusy(true);
    setError("");
    try {
      // Resolve tenant phone_number_id from filter or conversation
      let tenantPhone = getTenantFilter();
      if (tenantPhone === "all") {
        const tenants = await api<{ phone_number_id: string; id: number }[]>(
          "/api/dashboard/tenants",
          { tenant: false }
        );
        const match = tenants.find((t) => t.id === lead.tenant_id);
        if (!match) throw new Error("Select a tenant to mute, or set tenant filter");
        tenantPhone = match.phone_number_id;
      }
      await api("/api/dashboard/mutes", {
        method: "POST",
        tenant: false,
        body: JSON.stringify({
          tenant_id: tenantPhone,
          wa_id: lead.contact.wa_id,
          mute: !muted,
        }),
      });
      setMuted(!muted);
      onMuted?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Mute failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-950/40" onClick={onClose}>
      <aside
        className="animate-slide-in flex h-full w-full max-w-md flex-col bg-white shadow-soft"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-mist-100 px-4 py-3">
          <div>
            <h2 className="font-display text-xl font-semibold text-ink-900">
              {lead?.business_name || "Lead"}
            </h2>
            <p className="text-xs text-ink-600">
              {lead?.contact.profile_name} · {lead?.contact.wa_id}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-ink-600 hover:bg-mist-100"
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {error && <p className="text-sm text-red-600">{error}</p>}
          {!lead && !error && <p className="text-sm text-ink-600">Loading…</p>}
          {lead && (
            <>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["Status", lead.status],
                  ["Type", lead.business_type || "—"],
                  ["Locations", lead.locations || "—"],
                  ["System", lead.current_system || "—"],
                  ["Demo", lead.demo_slot || "—"],
                  ["Intent", lead.entry_intent || "—"],
                  ["Source", lead.ad_source || "—"],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs text-ink-600">{k}</dt>
                    <dd className="font-medium capitalize text-ink-900">{v}</dd>
                  </div>
                ))}
              </dl>

              <button
                type="button"
                disabled={busy}
                onClick={toggleMute}
                className={`w-full rounded-lg py-2.5 text-sm font-semibold text-white ${
                  muted ? "bg-ink-700 hover:bg-ink-800" : "bg-amber-600 hover:bg-amber-700"
                } disabled:opacity-60`}
              >
                {busy ? "…" : muted ? "Unmute (resume bot)" : "Mute / Human takeover"}
              </button>

              <div>
                <h3 className="mb-2 text-sm font-semibold text-ink-900">Conversation</h3>
                <Bubbles messages={lead.history || []} />
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
