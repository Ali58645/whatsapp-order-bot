import { useCallback, useEffect, useState } from "react";
import { Loader2, Mic, Plus, Send, Smile } from "lucide-react";
import { toast } from "sonner";
import { api, Conversation, Lead, MeResponse } from "../../api";
import { WhatsAppThread } from "../leads/WhatsAppThread";
import { PhoneChatFrame } from "./PhoneChatFrame";
import { Skeleton } from "../ui/avatar";

type Props = {
  contactId: number;
  leadId?: number;
  sessionId?: number;
  contactName: string;
  channel?: string;
  waId?: string;
  phase?: string | null;
  onBack?: () => void;
  onUpdated?: () => void;
};

export function ConversationPhone({
  contactId,
  leadId,
  sessionId,
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
  const [draft, setDraft] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const sessionQ = sessionId ? `?session_id=${sessionId}` : "";
      const [profile, conv] = await Promise.all([
        api<MeResponse>("/api/dashboard/me", { tenant: false }),
        api<Conversation>(`/api/dashboard/conversations/${contactId}${sessionQ}`, {
          tenant: false,
        }),
      ]);
      setMe(profile);

      let history = conv.history ?? [];
      if (!history.length && leadId) {
        try {
          const lead = await api<Lead>(`/api/dashboard/leads/${leadId}`, { tenant: false });
          if (lead.history?.length) history = lead.history;
        } catch {
          /* ignore */
        }
      }
      setConversation({ ...conv, history });
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load chat");
      setConversation(null);
    } finally {
      setLoading(false);
    }
  }, [contactId, leadId, sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

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
  const subtitle = waId || conversation?.contact?.wa_id || undefined;

  const composer = (
    <div className="flex items-center gap-2">
      <button type="button" className="text-[#8696a0]" aria-hidden>
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
          placeholder={windowOpen ? "Message" : "24h window closed"}
          className="min-w-0 flex-1 border-0 bg-transparent text-[15px] text-white placeholder:text-[#8696a0] focus:outline-none disabled:opacity-50"
        />
        {!draft.trim() ? (
          <Mic className="h-5 w-5 shrink-0 text-[#8696a0]" />
        ) : null}
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
  );

  return (
    <PhoneChatFrame
      contactName={contactName}
      subtitle={phase ? `${subtitle} · ${phase}` : subtitle}
      channel={channel || conversation?.contact?.channel}
      botName={botName}
      onBack={onBack}
      footer={composer}
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
  );
}
