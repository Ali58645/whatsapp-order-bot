import { cn } from "../../lib/utils";

export function Badge({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide",
        className
      )}
    >
      {children}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active: { label: "Talking", cls: "bg-warning/15 text-warning ring-1 ring-warning/25" },
    confirmed: { label: "Demo booked", cls: "bg-primary/15 text-primary ring-1 ring-primary/25" },
    stalled: { label: "Quiet", cls: "bg-muted text-muted-foreground ring-1 ring-border" },
    new: { label: "New", cls: "bg-sky-500/15 text-sky-400 ring-1 ring-sky-500/25" },
  };
  const s = map[(status || "new").toLowerCase()] ?? {
    label: status || "New",
    cls: "bg-sky-500/15 text-sky-400 ring-1 ring-sky-500/25",
  };
  return <Badge className={s.cls}>{s.label}</Badge>;
}
