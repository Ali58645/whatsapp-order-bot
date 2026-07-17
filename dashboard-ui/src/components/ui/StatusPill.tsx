import { leadStatus } from "../../lib/utils";

export default function StatusPill({ status }: { status: string }) {
  const { label, className } = leadStatus(status);
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${className}`}>
      {label}
    </span>
  );
}
