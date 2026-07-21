import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Megaphone, MessageCircle, Send, X } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  Conversation,
  getTenantFilter,
  Lead,
  Tenant,
} from "../../api";
import { Avatar } from "../ui/avatar";
import { StatusPill } from "../ui/badge";
import { Button } from "../ui/button";
import { Switch } from "../ui/switch";
import { Skeleton } from "../ui/avatar";
import { Textarea, Input } from "../ui/input";
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
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [muted, setMuted] = useState(false);
  const [confirmMute, setConfirmMute] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [notesBusy, setNotesBusy] = useState(false);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api<Lead>(`/api/dashboard/leads/${leadId}`, { tenant: false });
      setLead(data);
      setNotes(data.notes || "");
      setTagsText((data.tags || []).join(", "));
      if (data.contact_id) {
        try {
          const conv = await api<Conversation>(
            `/api/dashboard/conversations/${data.contact_id}`,
            { tenant: false }
          );
          setConversation(conv);
          setMuted(Boolean(conv.muted_until && new Date(conv.muted_until) > new Date()));
        } catch {
          setConversation(null);
          setMuted(false);
        }
      } else {
        setConversation(null);
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
        const raw = await api<{ items?: Tenant[] } | Tenant[]>("/api/dashboard/tenants", { tenant: false });
        const tenants = Array.isArray(raw) ? raw : raw.items || [];
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

  async function sendReply() {
    if (!lead?.contact_id || !draft.trim() || sending) return;
    const text = draft.trim();
    setSending(true);
    setError("");
    try {
      const conv = await api<Conversation>(
        `/api/dashboard/conversations/${lead.contact_id}/send`,
        {
          method: "POST",
          body: JSON.stringify({ text }),
          tenant: false,
        }
      );
      setConversation(conv);
      setLead((prev) => (prev ? { ...prev, history: conv.history } : prev));
      setMuted(Boolean(conv.muted_until && new Date(conv.muted_until) > new Date()));
      setDraft("");
      toast.success("Message sent");
      onMuted?.();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Send failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setSending(false);
    }
  }

  function onComposerKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendReply();
    }
  }

  const name =
    lead?.business_name || lead?.contact?.profile_name || lead?.contact?.wa_id || "Lead";
  const messages = conversation?.history ?? lead?.history ?? [];
  const windowOpen = conversation?.window_open ?? false;
  const canSend = windowOpen && !sending && !loading && Boolean(lead?.contact_id);

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
                  <Button size="sm" variant="soft" className="mt-2" asChild>
                    <Link to={`/conversations?open=${lead.id}`} onClick={onClose}>
                      <MessageCircle className="mr-1.5 h-3.5 w-3.5" />
                      Open chat
                    </Link>
                  </Button>
                </>
              )}
            </div>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </header>

          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 space-y-6 overflow-y-auto px-5 py-4">
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

              {/* Conversation transcript */}
              <section className="flex min-h-[280px] flex-col">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Conversation
                </h3>
                {loading ? (
                  <Skeleton className="h-64 w-full rounded-xl" />
                ) : (
                  <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border">
                    <div className="min-h-[200px] flex-1 overflow-y-auto">
                      <WhatsAppThread messages={messages} />
                    </div>
                  </div>
                )}
              </section>

              {/* Owner notes */}
              {!loading && lead && (
                <section className="space-y-3 rounded-xl border border-border bg-muted/20 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Your notes
                  </h3>
                  <Textarea
                    rows={3}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Private notes about this customer…"
                  />
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Tags (comma-separated)
                    </p>
                    <Input
                      className="mt-1"
                      value={tagsText}
                      onChange={(e) => setTagsText(e.target.value)}
                      placeholder="vip, follow-up"
                    />
                  </div>
                  <Button
                    size="sm"
                    variant="soft"
                    disabled={notesBusy}
                    onClick={() => {
                      setNotesBusy(true);
                      void api(`/api/dashboard/leads/${leadId}/notes`, {
                        method: "PATCH",
                        body: JSON.stringify({
                          notes,
                          tags: tagsText
                            .split(",")
                            .map((t) => t.trim())
                            .filter(Boolean),
                        }),
                        tenant: false,
                      })
                        .then(() => toast.success("Notes saved"))
                        .catch((e: unknown) =>
                          toast.error(e instanceof Error ? e.message : "Save failed")
                        )
                        .finally(() => setNotesBusy(false));
                    }}
                  >
                    Save notes
                  </Button>
                </section>
              )}

              {/* Details */}
              <section>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Answers from the bot
                </h3>
                {loading || !lead ? (
                  <Skeleton className="h-32 w-full rounded-xl" />
                ) : (
                  <div className="grid grid-cols-2 gap-4 rounded-xl border border-border bg-muted/20 p-4">
                    <Field label="Business type" value={lead.business_type} />
                    <Field label="Locations" value={lead.locations} />
                    <Field label="Current system" value={lead.current_system} />
                    <Field label="Demo time" value={lead.demo_slot} />
                    <Field label="What they wanted" value={lead.entry_intent} />
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

            {/* Reply composer — pinned to drawer bottom */}
            <div className="border-t border-border bg-card px-4 py-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Reply from dashboard
              </p>
              {!loading && !windowOpen && (
                <p className="mb-2 text-xs text-muted-foreground">
                  Window closed — customer must message first
                </p>
              )}
              <div className="flex items-end gap-2">
                <Textarea
                  ref={composerRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={onComposerKeyDown}
                  placeholder={windowOpen ? "Type a message…" : "Messaging window closed"}
                  disabled={!canSend}
                  rows={1}
                  className="min-h-[40px] max-h-28 resize-none rounded-2xl py-2.5 text-[13px]"
                />
                <Button
                  size="icon"
                  className="h-10 w-10 shrink-0 rounded-full"
                  disabled={!canSend || !draft.trim()}
                  onClick={() => void sendReply()}
                  aria-label="Send message"
                >
                  {sending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>
        </motion.aside>
      </motion.div>
    </AnimatePresence>
  );
}
