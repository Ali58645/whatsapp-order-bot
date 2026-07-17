import { useMemo } from "react";
import { cn } from "../../lib/utils";

type Msg = { role: string; content: string };

function parseContent(content: string): { text: string; chips: string[] } {
  const chips: string[] = [];
  const text = content;
  const chipLines = content.match(/^[•\-\d]+[\.)]?\s*.+$/gm);
  if (chipLines && chipLines.length <= 6) {
    for (const line of chipLines) {
      const cleaned = line.replace(/^[•\-\d]+[\.)]?\s*/, "").trim();
      if (cleaned.length < 40) chips.push(cleaned);
    }
  }
  const bracket = [...content.matchAll(/\[([^\]]{1,32})\]/g)].map((m) => m[1]);
  if (bracket.length) chips.push(...bracket);
  return { text, chips: [...new Set(chips)] };
}

function Bubble({ mine, content }: { mine: boolean; content: string }) {
  const { text, chips } = parseContent(content);
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "relative max-w-[85%] px-3 py-2 text-[13.5px] leading-relaxed shadow-sm",
          mine
            ? "rounded-2xl rounded-br-sm bg-[var(--wa-out)] text-white"
            : "rounded-2xl rounded-bl-sm bg-[var(--wa-in)] text-zinc-100"
        )}
      >
        {/* Tail */}
        <span
          className={cn(
            "absolute bottom-0 h-3 w-3",
            mine ? "-right-1 bg-[var(--wa-out)]" : "-left-1 bg-[var(--wa-in)]"
          )}
          style={{
            clipPath: mine
              ? "polygon(0 0, 0 100%, 100% 100%)"
              : "polygon(100% 0, 0 100%, 100% 100%)",
          }}
          aria-hidden
        />
        <p className="transcript-text relative whitespace-pre-wrap">{text}</p>
        {chips.length > 0 && (
          <div className="relative mt-2 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span
                key={c}
                className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1 text-[11px] font-medium text-white/90"
              >
                {c}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function WhatsAppThread({ messages }: { messages: Msg[] }) {
  const items = useMemo(() => messages, [messages]);

  if (!items.length) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-muted/40 px-4 py-10 text-center text-sm text-muted-foreground">
        No messages in session history yet
      </div>
    );
  }

  return (
    <div
      className="relative space-y-2.5 overflow-hidden rounded-xl p-3 sm:p-4"
      style={{
        backgroundColor: "var(--wa-bg)",
        backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
      }}
    >
      <div className="mb-3 flex justify-center">
        <span className="rounded-full bg-black/40 px-3 py-1 text-[10px] font-medium uppercase tracking-wider text-zinc-400">
          Today
        </span>
      </div>
      {items.map((m, i) => (
        <Bubble key={i} mine={m.role === "user"} content={m.content} />
      ))}
    </div>
  );
}
