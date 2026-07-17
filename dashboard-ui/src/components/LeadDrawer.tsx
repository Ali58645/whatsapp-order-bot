import { useEffect, useState } from "react";
import { X, MessageSquareOff, MessageSquare } from "lucide-react";
import { api, getTenantFilter, Lead } from "../api";
import Bubbles from "./Bubbles";
import StatusPill from "./ui/StatusPill";
import { useToast } from "./ui/Toast";

type Props = {
  leadId: number;
  onClose: () => void;
  onMuted?: () => void;
};

export default function LeadDrawer({ leadId, onClose, onMuted }: Props) {
  const { toast } = useToast();
  const [lead, setLead] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [muted, setMuted] = useState(false);
  const [confirmMute, setConfirmMute] = useState(false);

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
    if (!muted && !confirmMute) {
      setConfirmMute(true);
      return;
    }
    setBusy(true);
    setError("");
    try {
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
      setConfirmMute(false);
      toast(muted ? "Bot resumed for this contact" : "Human takeover enabled", "success");
      onMuted?.();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Mute failed";
      setError(msg);
      toast(msg, "error");
    } finally {
      setBusy(false);
    }
  }

  const fields: [string, string][] = lead
    ? [
        ["Status", lead.status],
        ["Business type", lead.business_type || "—"],
        ["Locations", lead.locations || "—"],
        ["Current system", lead.current_system || "—"],
        ["Demo slot", lead.demo_slot || "—"],
        ["Entry intent", lead.entry_intent || "—"],
        ["Ad source", lead.ad_source || "—"],
      ]
    : [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink-950/45 backdrop-blur-[2px]" onClick={onClose}>
      <aside
        className="animate-slide-in flex h-full w-full max-w-md flex-col border-l border-canvas-200 bg-white shadow-drawer sm:max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-canvas-100 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-ink-900">{lead?.business_name || "Lead"}</h2>
            <p className="mt-0.5 truncate text-xs text-ink-500">
              {lead?.contact.profile_name} · {lead?.contact.wa_id}
            </p>
            {lead && (
              <div className="mt-2">
                <StatusPill status={lead.status} />
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-ink-500 transition-ui hover:bg-canvas-100 hover:text-ink-800"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
          {error && (
            <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}
          {!lead && !error && (
            <div className="space-y-3">
              <div className="h-4 w-32 animate-shimmer rounded bg-canvas-200" />
              <div className="h-20 animate-shimmer rounded-xl bg-canvas-200" />
            </div>
          )}
          {lead && (
            <>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-canvas-100 bg-canvas-50 p-4 text-sm">
                {fields.map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">{k}</dt>
                    <dd className="mt-0.5 font-medium capitalize text-ink-900">{v}</dd>
                  </div>
                ))}
              </dl>

              <div className="rounded-xl border border-canvas-200 bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    {muted ? (
                      <MessageSquareOff className="h-5 w-5 text-amber-600" />
                    ) : (
                      <MessageSquare className="h-5 w-5 text-bahi-600" />
                    )}
                    <div>
                      <p className="text-sm font-bold text-ink-900">Bot responses</p>
                      <p className="text-xs text-ink-500">
                        {muted ? "Muted — you handle this chat" : "Bot is active"}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={muted}
                    disabled={busy}
                    onClick={toggleMute}
                    className={`relative h-7 w-12 shrink-0 rounded-full transition-ui ${
                      muted ? "bg-amber-500" : "bg-canvas-300"
                    } disabled:opacity-60`}
                  >
                    <span
                      className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-ui ${
                        muted ? "left-[1.35rem]" : "left-0.5"
                      }`}
                    />
                  </button>
                </div>
                {confirmMute && !muted && (
                  <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-900">
                    <p className="font-semibold">Enable human takeover?</p>
                    <p className="mt-1 text-amber-800/90">The bot will stop replying until you unmute.</p>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={toggleMute}
                        disabled={busy}
                        className="rounded-lg bg-amber-600 px-3 py-1.5 font-semibold text-white hover:bg-amber-700"
                      >
                        Confirm mute
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmMute(false)}
                        className="rounded-lg px-3 py-1.5 font-medium text-amber-900 hover:bg-amber-100"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-500">Conversation</h3>
                <Bubbles messages={lead.history || []} />
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
