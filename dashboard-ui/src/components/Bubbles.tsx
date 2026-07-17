type Msg = { role: string; content: string };

/** Detect interactive list/button reply patterns for chip rendering */
function parseContent(content: string): { text: string; chips: string[] } {
  const chips: string[] = [];
  let text = content;

  // Lines like "• Option" or numbered choices
  const chipLines = content.match(/^[•\-\d]+[\.)]?\s*.+$/gm);
  if (chipLines && chipLines.length <= 6) {
    for (const line of chipLines) {
      const cleaned = line.replace(/^[•\-\d]+[\.)]?\s*/, "").trim();
      if (cleaned.length < 40) chips.push(cleaned);
    }
  }

  // Bracketed quick replies: [Yes] [No]
  const bracket = [...content.matchAll(/\[([^\]]{1,32})\]/g)].map((m) => m[1]);
  if (bracket.length) chips.push(...bracket);

  return { text, chips: [...new Set(chips)] };
}

function Bubble({
  mine,
  content,
  time,
}: {
  mine: boolean;
  content: string;
  time?: string;
}) {
  const { text, chips } = parseContent(content);
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[88%] rounded-2xl px-3 py-2 shadow-sm ${
          mine
            ? "rounded-br-md bg-[#d9fdd3] text-ink-900"
            : "rounded-bl-md bg-white text-ink-900"
        }`}
      >
        <p className="transcript-text whitespace-pre-wrap text-sm leading-relaxed">{text}</p>
        {chips.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span
                key={c}
                className="rounded-full border border-bahi-200/60 bg-bahi-50 px-2 py-0.5 text-[11px] font-semibold text-bahi-800"
              >
                {c}
              </span>
            ))}
          </div>
        )}
        {time && (
          <p className={`mt-1 text-[10px] ${mine ? "text-right text-ink-500/70" : "text-ink-400"}`}>
            {time}
          </p>
        )}
      </div>
    </div>
  );
}

export default function Bubbles({ messages }: { messages: Msg[] }) {
  if (!messages.length) {
    return (
      <div className="rounded-xl border border-dashed border-canvas-300 bg-canvas-50 px-4 py-8 text-center text-sm text-ink-500">
        No messages in session history
      </div>
    );
  }

  return (
    <div className="space-y-2.5 rounded-xl bg-[#e5ddd5] p-3 sm:p-4">
      {messages.map((m, i) => {
        const mine = m.role === "user";
        return <Bubble key={i} mine={mine} content={m.content} />;
      })}
    </div>
  );
}
