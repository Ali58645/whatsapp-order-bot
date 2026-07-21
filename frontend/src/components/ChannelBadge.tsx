import { cn } from "../lib/utils";

export type ChannelId = "whatsapp" | "instagram" | "messenger";

const LABELS: Record<ChannelId, string> = {
  whatsapp: "WA",
  instagram: "IG",
  messenger: "FB",
};

const STYLES: Record<ChannelId, string> = {
  whatsapp: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/25",
  instagram: "bg-fuchsia-500/15 text-fuchsia-400 ring-fuchsia-500/25",
  messenger: "bg-blue-500/15 text-blue-400 ring-blue-500/25",
};

export function ChannelBadge({
  channel,
  className,
}: {
  channel?: string | null;
  className?: string;
}) {
  const ch = (channel || "whatsapp").toLowerCase() as ChannelId;
  const id = ch in LABELS ? ch : "whatsapp";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ring-1",
        STYLES[id],
        className
      )}
      title={id}
    >
      {LABELS[id]}
    </span>
  );
}
