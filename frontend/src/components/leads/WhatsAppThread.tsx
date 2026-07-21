import { useEffect, useMemo, useRef } from "react";
import { Lock } from "lucide-react";
import { cn } from "../../lib/utils";

type Msg = { role: string; content: string; sender?: string };

type Props = {
  messages: Msg[];
  /** Owner inbox: customer left, bot right */
  view?: "owner" | "customer";
  embedded?: boolean;
};

function parseContent(content: string): { text: string; chips: string[] } {
  const chips: string[] = [];
  const text = content;
  const chipLines = content.match(/^[•▢\-\d]+[\.)]?\s*.+$/gm);
  if (chipLines && chipLines.length <= 8) {
    for (const line of chipLines) {
      const cleaned = line.replace(/^[•▢\-\d]+[\.)]?\s*/, "").trim();
      if (cleaned.length < 48) chips.push(cleaned);
    }
  }
  const bracket = [...content.matchAll(/\[([^\]]{1,32})\]/g)].map((m) => m[1]);
  if (bracket.length) chips.push(...bracket);
  return { text, chips: [...new Set(chips)] };
}

function isOutgoing(role: string, view: "owner" | "customer"): boolean {
  if (view === "owner") {
    return role === "assistant" || role === "human_agent";
  }
  return role === "user" || role === "human_agent";
}

function Bubble({
  mine,
  content,
  agent,
  time,
}: {
  mine: boolean;
  content: string;
  agent?: boolean;
  time: string;
}) {
  const { text, chips } = parseContent(content);
  return (
    <div className={cn("flex px-2", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "relative max-w-[82%] px-2.5 pb-1.5 pt-1.5 text-[14px] leading-[1.35] shadow-sm",
          mine
            ? "rounded-[18px] rounded-br-[4px] bg-[#005c4b] text-[#e9edef]"
            : "rounded-[18px] rounded-bl-[4px] bg-[#202c33] text-[#e9edef]"
        )}
      >
        {agent && (
          <span className="mb-1 inline-block rounded bg-white/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-white/80">
            You
          </span>
        )}
        <p className="transcript-text whitespace-pre-wrap break-words">{text}</p>
        {chips.length > 0 && (
          <div className="mt-2 flex flex-col gap-1 border-t border-white/10 pt-2">
            {chips.map((c) => (
              <span
                key={c}
                className="rounded-lg border border-[#00a884]/40 bg-[#0b141a]/40 px-2.5 py-1.5 text-center text-[12px] font-medium text-[#00d4aa]"
              >
                {c}
              </span>
            ))}
          </div>
        )}
        <p
          className={cn(
            "mt-0.5 text-right text-[10px] tabular leading-none",
            mine ? "text-emerald-200/50" : "text-zinc-500"
          )}
        >
          {time}
        </p>
        </div>
    </div>
  );
}

const WALLPAPER = `url("data:image/svg+xml,%3Csvg width='80' height='80' viewBox='0 0 80 80' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='0.025'%3E%3Cpath d='M0 0h40v40H0V0zm40 40h40v40H40V40z'/%3E%3C/g%3E%3C/svg%3E")`;

export function WhatsAppThread({ messages, view = "owner", embedded = true }: Props) {
  const items = useMemo(() => messages.filter((m) => (m.content || "").trim()), [messages]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const now = useMemo(
    () =>
      new Date().toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      }),
    []
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items.length]);

  if (!items.length) {
    return (
      <div
        className={cn(
          "flex h-full min-h-[280px] flex-col items-center justify-center px-6 text-center",
          embedded ? "bg-[#0b141a]" : "rounded-xl border border-dashed border-border bg-muted/40"
        )}
        style={embedded ? { backgroundImage: WALLPAPER } : undefined}
      >
        <div className="rounded-full bg-[#202c33] p-3">
          <Lock className="h-5 w-5 text-[#8696a0]" />
        </div>
        <p className="mt-3 text-sm font-medium text-[#e9edef]">No messages yet</p>
        <p className="mt-1 max-w-[200px] text-xs text-[#8696a0]">
          Messages with your bot will appear here end-to-end encrypted style.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative min-h-full space-y-1 py-3",
        embedded ? "bg-[#0b141a]" : "rounded-xl p-3 sm:p-4"
      )}
      style={{
        backgroundColor: embedded ? "#0b141a" : "var(--wa-bg)",
        backgroundImage: WALLPAPER,
      }}
    >
      <div className="mb-2 flex justify-center px-2">
        <span className="rounded-lg bg-[#182229]/90 px-3 py-1 text-[11px] font-medium text-[#8696a0] shadow-sm">
          Today
        </span>
      </div>
      {items.map((m, i) => (
        <Bubble
          key={`${i}-${m.content.slice(0, 24)}`}
          mine={isOutgoing(m.role, view)}
          content={m.content}
          agent={m.role === "human_agent" || m.sender === "human_agent"}
          time={now}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
