import { lazy, Suspense } from "react";
import { Skeleton } from "./avatar";

const LazySpark = lazy(() => import("./spark-area-inner"));

export function SparkArea({ data, className }: { data: number[]; className?: string }) {
  return (
    <Suspense fallback={<Skeleton className="h-12 w-full rounded-md" />}>
      <LazySpark data={data} className={className} />
    </Suspense>
  );
}
