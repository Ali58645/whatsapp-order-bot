import { motion } from "framer-motion";
import { cn } from "../../lib/utils";

export function EmptyState({
  title,
  description,
  action,
  illustration = "inbox",
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  illustration?: "inbox" | "search" | "chat" | "orders";
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-16 text-center",
        className
      )}
    >
      <EmptyArt kind={illustration} />
      <h3 className="mt-5 text-base font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </motion.div>
  );
}

function EmptyArt({ kind }: { kind: string }) {
  const stroke = "hsl(var(--muted-foreground))";
  const fill = "hsl(var(--primary) / 0.2)";
  return (
    <svg width="120" height="96" viewBox="0 0 120 96" fill="none" aria-hidden>
      <rect x="20" y="24" width="80" height="56" rx="12" fill={fill} stroke={stroke} strokeOpacity="0.35" />
      {kind === "chat" && (
        <>
          <rect x="32" y="40" width="36" height="10" rx="5" fill={stroke} fillOpacity="0.25" />
          <rect x="52" y="56" width="36" height="10" rx="5" fill="hsl(var(--primary))" fillOpacity="0.55" />
        </>
      )}
      {kind === "orders" && (
        <>
          <circle cx="44" cy="52" r="8" stroke={stroke} strokeOpacity="0.4" />
          <circle cx="76" cy="52" r="8" stroke={stroke} strokeOpacity="0.4" />
          <path d="M36 28h48l-6 20H42L36 28z" stroke={stroke} strokeOpacity="0.4" fill={fill} />
        </>
      )}
      {kind === "search" && (
        <>
          <circle cx="54" cy="48" r="14" stroke={stroke} strokeOpacity="0.45" />
          <path d="M64 58l12 12" stroke={stroke} strokeOpacity="0.45" strokeWidth="2" strokeLinecap="round" />
        </>
      )}
      {kind === "inbox" && (
        <>
          <path d="M28 44l32-12 32 12v24a8 8 0 01-8 8H36a8 8 0 01-8-8V44z" stroke={stroke} strokeOpacity="0.4" fill={fill} />
          <path d="M28 44l32 16 32-16" stroke={stroke} strokeOpacity="0.4" />
        </>
      )}
    </svg>
  );
}
