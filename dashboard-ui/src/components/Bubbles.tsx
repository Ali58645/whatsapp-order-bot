type Msg = { role: string; content: string };

export default function Bubbles({ messages }: { messages: Msg[] }) {
  if (!messages.length) {
    return (
      <p className="rounded-xl bg-mist-50 px-3 py-6 text-center text-sm text-ink-600">
        No messages in session history
      </p>
    );
  }

  return (
    <div className="space-y-2 rounded-xl bg-[#e7ddd2] p-3">
      {messages.map((m, i) => {
        const mine = m.role === "assistant";
        return (
          <div
            key={i}
            className={`flex ${mine ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-snug shadow-sm ${
                mine
                  ? "rounded-bl-md bg-white text-ink-900"
                  : "rounded-br-md bg-[#d9fdd3] text-ink-900"
              }`}
            >
              <p className="whitespace-pre-wrap break-words">{m.content}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
