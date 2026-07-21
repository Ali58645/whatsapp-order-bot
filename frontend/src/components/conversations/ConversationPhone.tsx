import { useCallback, useEffect, useState } from "react";
import { Hand, Loader2, Mic, Plus, Send, Smile } from "lucide-react";
import { toast } from "sonner";
import { api, Conversation, Lead, MeResponse, getTenantFilter } from "../../api";
import { WhatsAppThread } from "../leads/WhatsAppThread";
import { PhoneChatFrame } from "./PhoneChatFrame";
import { Skeleton } from "../ui/avatar";
import { Button } from "../ui/button";
import { Switch } from "../ui/switch";
import { cn } from "../../lib/utils";

type Props = {
  contactId: number;
  leadId?: number;
  sessionId?: number;
  tenantDbId?: number;
  contactName: string;
  channel?: string;
  waId?: string;
  phase?: string | null;
  onBack?: () => void;
  onUpdated?: () => void;
};

function isMuted(conv: Conversation | null): boolean {
  if (!conv?.muted_until) return false;
  return new Date(conv.muted_until) > new Date();
}

export function ConversationPhone({
  contactId,
  leadId,
  sessionId,
  tenantDbId,
  contactName,
  channel,
  waId,
  phase,
  onBack,
  onUpdated,
}: Props) {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [muteBusy, setMuteBusy] = useState(false);
  const [confirmTakeover, setConfirmTakeover] = useState(false);
  const [draft, setDraft] = useState("");

  const muted = isMuted(conversation);
  const contactWa = waId || conversation?.contact?.wa_id || "";

  const refresh = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    if (!silent) setLoading(true);
    try {
      const sessionQ = sessionId ? `?session_id=${sessionId}` : "";
      if (!silent) {
        const profile = await api<MeResponse>("/api/dashboard/me", { tenant: false });
        setMe(profile);
      }
      const conv = await api<Conversation>(
        `/api/dashboard/conversations/${contactId}${sessionQ}`,
        { tenant: false }
      );

      let history = conv.history ?? [];
      if (!history.length && leadId && !silent) {
        try {
          const lead = await api<Lead>(`/api/dashboard/leads/${leadId}`, { tenant: false });
          if (lead.history?.length) history = lead.history;
        } catch {
          /* ignore */
        }
      }

      setConversation((prev) => {
        const incoming = conv.history ?? [];
        // Keep previous messages if API briefly returns empty during race
        if (silent && !incoming.length && (prev?.history?.length || 0) > 0) {
          return { ...conv, history: prev!.history, muted_until: conv.muted_until };
        }
        return { ...conv, history: incoming.length ? incoming : history };
      });
    } catch (e: unknown) {
      if (!silent) {
        toast.error(e instanceof Error ? e.message : "Failed to load chat");
        setConversation(null);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [contactId, leadId, sessionId]);

  useEffect(() => {
    void refresh({ silent: false });
  }, [refresh]);

  // Live inbox: poll while this chat is open (inbound during takeover)
  useEffect(() => {
    const id = window.setInterval(() => {
      void refresh({ silent: true });
    }, 2500);
    return () => window.clearInterval(id);
  }, [refresh]);

  const load = useCallback(() => refresh({ silent: false }), [refresh]);

  async function resolveTenantPhone(): Promise<string> {
    const fromMe = me?.tenant?.phone_number_id;
    if (fromMe) return fromMe;
    const filter = getTenantFilter();
    if (filter && filter !== "all") return filter;
    if (tenantDbId) {
      const raw = await api<{ items?: { id: number; phone_number_id: string }[] } | { id: number; phone_number_id: string }[]>(
        "/api/dashboard/tenants",
        { tenant: false }
      );
      const list = Array.isArray(raw) ? raw : raw.items || [];
      const match = list.find((t) => t.id === tenantDbId);
      if (match) return match.phone_number_id;
    }
    throw new Error("Could not resolve business for takeover");
  }

  async function toggleTakeover() {
    if (!contactWa) return;
    if (!muted && !confirmTakeover) {
      setConfirmTakeover(true);
      return;
    }
    setMuteBusy(true);
    try {
      const tenantPhone = await resolveTenantPhone();
      await api("/api/dashboard/mutes", {
        method: "POST",
        body: JSON.stringify({
          tenant_id: tenantPhone,
          wa_id: contactWa,
          mute: !muted,
        }),
        tenant: false,
      });
      const next = !muted;
      setConfirmTakeover(false);
      setConversation((prev) =>
        prev
          ? {
              ...prev,
              muted_until: next
                ? new Date(Date.now() + 24 * 3600 * 1000).toISOString()
                : null,
            }
          : prev
      );
      toast.success(next ? "Human takeover on — bot paused" : "Bot resumed for this chat");
      await load();
      onUpdated?.();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Takeover failed");
    } finally {
      setMuteBusy(false);
    }
  }

  async function sendReply() {
    if (!draft.trim() || sending) return;
    const text = draft.trim();
    setSending(true);
    try {
      const conv = await api<Conversation>(
        `/api/dashboard/conversations/${contactId}/send`,
        {
          method: "POST",
          body: JSON.stringify({ text }),
          tenant: false,
        }
      );
      setConversation(conv);
      setDraft("");
      toast.success("Message sent");
      onUpdated?.();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  }

  const messages = conversation?.history ?? [];
  const windowOpen = conversation?.window_open ?? false;
  const botName = me?.tenant?.name || "Your bot";

  const composer = (
    <div className="space-y-2">
      {!windowOpen && !loading && (
        <p className="rounded-lg bg-black/40 px-2 py-1.5 text-center text-[10px] text-zinc-400">
          Customer must message first (24h WhatsApp window).
        </p>
      )}
      {muted && windowOpen && (
        <p className="text-center text-[10px] font-medium text-amber-400/90">
          Live — you&apos;re replying · bot is paused
        </p>
      )}
      <div className="flex items-center gap-2">
        <button type="button" className="text-[#8696a0]" aria-hidden tabIndex={-1}>
          <Plus className="h-6 w-6" />
        </button>
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full bg-[#2a3942] px-3 py-2">
          <Smile className="h-5 w-5 shrink-0 text-[#8696a0]" />
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendReply();
              }
            }}
            disabled={!windowOpen || sending}
            placeholder={
              !windowOpen
                ? "Window closed"
                : muted
                  ? "Type your reply…"
                  : "Type to reply (pauses bot)"
            }
            className="min-w-0 flex-1 border-0 bg-transparent text-[15px] text-white placeholder:text-[#8696a0] focus:outline-none disabled:opacity-50"
          />
          {!draft.trim() ? <Mic className="h-5 w-5 shrink-0 text-[#8696a0]" /> : null}
        </div>
        <button
          type="button"
          disabled={!windowOpen || sending || !draft.trim()}
          onClick={() => void sendReply()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#00a884] text-white disabled:opacity-40"
          aria-label="Send"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex w-full max-w-[420px] flex-col gap-3">
      <div
        className={cn(
          "rounded-2xl border px-4 py-3 transition",
          muted ? "border-amber-500/40 bg-amber-500/10" : "border-border bg-card"
        )}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-full",
                muted ? "bg-amber-500/20 text-amber-400" : "bg-primary/15 text-primary"
              )}
            >
              <Hand className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold">
                {muted ? "You’re handling this chat" : "Bot is handling this chat"}
              </p>
              <p className="text-xs text-muted-foreground">
                {muted
                  ? "Toggle off anytime to let the bot resume"
                  : "Toggle on to reply yourself — bot stays quiet"}
              </p>
            </div>
          </div>
          <Switch
            checked={muted}
            disabled={muteBusy || loading || !contactWa}
            onCheckedChange={() => void toggleTakeover()}
            aria-label="Human takeover"
          />
        </div>
        {confirmTakeover && !muted && (
          <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
            <p className="text-sm font-medium text-amber-200">Take over from the bot?</p>
            <p className="mt-1 text-xs text-muted-foreground">
              The bot won’t reply for 24 hours. You’ll see their messages live here.
            </p>
            <div className="mt-3 flex gap-2">
              <Button size="sm" onClick={() => void toggleTakeover()} disabled={muteBusy}>
                {muteBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Yes, take over"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirmTakeover(false)}
                disabled={muteBusy}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>

      <PhoneChatFrame
        contactName={contactName}
        subtitle={muted ? `${contactWa || ""} · You`.trim() : contactWa || undefined}
        channel={channel || conversation?.contact?.channel}
        botName={botName}
        onBack={onBack}
        footer={composer}
        takeoverActive={muted}
      >
        {loading ? (
          <div className="space-y-3 p-4">
            <Skeleton className="h-10 w-3/4 rounded-2xl bg-[#202c33]" />
            <Skeleton className="ml-auto h-10 w-2/3 rounded-2xl bg-[#005c4b]/40" />
            <Skeleton className="h-10 w-4/5 rounded-2xl bg-[#202c33]" />
          </div>
        ) : (
          <WhatsAppThread messages={messages} view="owner" embedded />
        )}
      </PhoneChatFrame>
    </div>
  );
}
