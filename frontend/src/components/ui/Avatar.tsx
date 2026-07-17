import { cn, initials, avatarStyle } from "../../lib/utils";

export function Avatar({
  name,
  seed,
  size = "md",
  className,
}: {
  name: string;
  seed?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const dims = size === "sm" ? "h-8 w-8 text-[10px]" : size === "lg" ? "h-11 w-11 text-sm" : "h-9 w-9 text-xs";
  const style = avatarStyle(seed || name);
  return (
    <div
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold",
        dims,
        className
      )}
      style={style}
      aria-hidden
    >
      {initials(name, seed?.slice(-2) || "?")}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("shimmer rounded-lg", className)} />;
}
