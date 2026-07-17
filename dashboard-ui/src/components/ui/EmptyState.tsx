type Props = { title: string; description?: string };

function Illustration() {
  return (
    <svg viewBox="0 0 120 80" className="mx-auto h-20 w-28 text-bahi-300" aria-hidden>
      <rect x="8" y="20" width="44" height="52" rx="8" fill="currentColor" opacity="0.25" />
      <rect x="56" y="12" width="56" height="60" rx="10" fill="currentColor" opacity="0.4" />
      <circle cx="84" cy="32" r="10" fill="#faf8f5" opacity="0.9" />
      <rect x="68" y="48" width="32" height="6" rx="3" fill="#faf8f5" opacity="0.7" />
      <rect x="68" y="58" width="24" height="5" rx="2.5" fill="#faf8f5" opacity="0.5" />
      <path d="M20 36h20M20 44h14M20 52h18" stroke="#faf8f5" strokeWidth="3" strokeLinecap="round" opacity="0.6" />
    </svg>
  );
}

export default function EmptyState({ title, description }: Props) {
  return (
    <div className="rounded-2xl border border-dashed border-canvas-300 bg-white px-6 py-12 text-center shadow-card">
      <Illustration />
      <p className="mt-4 text-base font-semibold text-ink-900">{title}</p>
      {description && <p className="mt-1 text-sm text-ink-500">{description}</p>}
    </div>
  );
}
