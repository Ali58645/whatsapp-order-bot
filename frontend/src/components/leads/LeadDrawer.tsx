import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Megaphone } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  getTenantFilter,
  Lead,
  Tenant,
} from "../../api";
import { Avatar } from "../ui/avatar";
import { StatusPill } from "../ui/badge";
import { Button } from "../ui/button";
import { Switch } from "../ui/switch";
import { Skeleton } from "../ui/avatar";
import { WhatsAppThread } from "./WhatsAppThread";
import { cn } from "../../lib/utils";

type Props = {
  leadId: number;
  onClose: () => void;
  onMuted?: () => void;
};

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-sm text-foreground">{value || "—"}</p>
    </div>
  );
}

export default function LeadDrawer({ leadId, onClose, onMuted }: Props) {
  const [lead, setLead] = useState<Lead | null>(null);
  const [loading, setLoading] = useState(true);
  const [muted, setMuted] = useState(false);
  const [confirmMute, setConfirmMute] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api<Lead>(`/api/dashboard/leads/${leadId}`, { tenant: false });
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load lead");
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

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
        const tenants = await api<Tenant[]>("/api/dashboard/tenants", { tenant: false });
        const match = tenants.find((t) => t.id === lead.tenant_id);
        if (!match) throw new Error("Select a tenant to mute, or set tenant filter");
        tenantPhone = match.phone_number_id;
      }
      await api("/api/dashboard/mutes", {
        method: "POST",
        body: JSON.stringify({
          tenant_id: tenantPhone,
          wa_id: lead.contact.wa_id,
          mute: !muted,
        }),
        tenant: false,
      });
      const next = !muted;
      setMuted(next);
      setConfirmMute(false);
      toast.success(next ? "Human takeover enabled" : "Bot resumed for this contact");
      onMuted?.();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Mute failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  const name =
    lead?.business_name || lead?.contact?.profile_name || lead?.contact?.wa_id || "Lead";

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        role="presentation"
      >
        <motion.aside
          role="dialog"
          aria-modal="true"
          aria-label="Lead details"
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", stiffness: 380, damping: 36 }}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            "flex h-full w-full flex-col border-l border-border bg-card shadow-drawer sm:max-w-lg",
            "glass"
          )}
        >
          {/* Header */}
          <header className="flex items-start gap-3 border-b border-border px-5 py-4">
            {loading || !lead ? (
              <Skeleton className="h-11 w-11 rounded-full" />
            ) : (
              <Avatar
                name={name}
                seed={lead.contact.wa_id}
                size="lg"
              />
            )}
            <div className="min-w-0 flex-1">
              {loading || !lead ? (
                <>
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="mt-2 h-3 w-28" />
                </>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-lg font-semibold">{name}</h2>
                    <StatusPill status={lead.status} />
                  </div>
                  <p className="mt-0.5 truncate text-sm text-muted-foreground">
                    {lead.contact.profile_name}
                    {lead.contact.profile_name && lead.contact.wa_id ? " · " : ""}
                    {lead.contact.wa_id}
                  </p>
                </>
              )}
            </div>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
            {error && (
              <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}

            {/* Mute / takeover */}
            <section className="rounded-xl border border-border bg-muted/30 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">Human takeover</p>
                  <p className="text-xs text-muted-foreground">
                    {muted ? "Muted — you handle this chat" : "Bot is active"}
                  </p>
                </div>
                <Switch
                  checked={muted}
                  disabled={busy || loading || !lead}
                  onCheckedChange={() => toggleMute()}
                />
              </div>
              {confirmMute && !muted && (
                <div className="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-3">
                  <p className="text-sm font-medium text-warning">Enable human takeover?</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    The bot will stop replying until you unmute.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" onClick={() => toggleMute()} disabled={busy}>
                      Confirm
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setConfirmMute(false)}
                      disabled={busy}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </section>

            {/* Conversation — the money screen */}
            <section>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Conversation
              </h3>
              {loading ? (
                <Skeleton className="h-64 w-full rounded-xl" />
              ) : (
                <WhatsAppThread messages={lead?.history || []} />
              )}
            </section>

            {/* Details */}
            <section>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Lead details
              </h3>
              {loading || !lead ? (
                <Skeleton className="h-32 w-full rounded-xl" />
              ) : (
                <div className="grid grid-cols-2 gap-4 rounded-xl border border-border bg-muted/20 p-4">
                  <Field label="Status" value={lead.status} />
                  <Field label="Business type" value={lead.business_type} />
                  <Field label="Locations" value={lead.locations} />
                  <Field label="Current system" value={lead.current_system} />
                  <Field label="Demo slot" value={lead.demo_slot} />
                  <Field label="Entry intent" value={lead.entry_intent} />
                  <div className="col-span-2">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Ad source
                    </p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-sm">
                      {lead.ad_source ? (
                        <>
                          <Megaphone className="h-3.5 w-3.5 text-primary" />
                          {lead.ad_source}
                        </>
                      ) : (
                        "—"
                      )}
                    </p>
                  </div>
                </div>
              )}
            </section>
          </div>
        </motion.aside>
      </motion.div>
    </AnimatePresence>
  );
}
