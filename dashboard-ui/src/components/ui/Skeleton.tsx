type Props = { className?: string };

export default function Skeleton({ className = "" }: Props) {
  return (
    <div
      className={`animate-shimmer rounded-lg bg-gradient-to-r from-canvas-200 via-canvas-100 to-canvas-200 bg-[length:200%_100%] ${className}`}
      aria-hidden
    />
  );
}

export function StatCardSkeleton() {
  return (
    <div className="rounded-2xl border border-canvas-200 bg-white p-4 shadow-card">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="mt-3 h-8 w-16" />
      <Skeleton className="mt-3 h-8 w-full" />
    </div>
  );
}
