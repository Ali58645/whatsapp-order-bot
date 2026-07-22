import { FormEvent, useState } from "react";
import { Loader2, Megaphone } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../api";
import { Button } from "../../components/ui/button";
import { Label, Textarea } from "../../components/ui/input";

export default function BroadcastPage() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<{ sent: number; failed: number; skipped: number } | null>(
    null
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      const res = await api<{ sent: number; failed: number; skipped: number }>(
        "/api/dashboard/broadcast",
        {
          method: "POST",
          body: JSON.stringify({ text: text.trim() }),
          tenant: false,
        }
      );
      setLast(res);
      toast.success(`Sent to ${res.sent} customers`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Broadcast failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Broadcast</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Message customers who recently chatted (WhatsApp 24-hour window). Max 50 per send.
        </p>
      </div>

      <form
        onSubmit={(e) => void onSubmit(e)}
        className="space-y-4 rounded-2xl border border-border bg-card p-5"
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Megaphone className="h-4 w-4" />
          Message
        </div>
        <div>
          <Label>Text</Label>
          <Textarea
            className="mt-1.5"
            rows={5}
            maxLength={1024}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Assalam o Alaikum — aaj special offer…"
            required
          />
          <p className="mt-1 text-[11px] text-muted-foreground">{text.length}/1024</p>
        </div>
        <Button type="submit" disabled={busy || !text.trim()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Send broadcast
        </Button>
        {last && (
          <p className="text-xs text-muted-foreground">
            Last send: {last.sent} ok · {last.failed} failed · {last.skipped} skipped
          </p>
        )}
      </form>
    </div>
  );
}
