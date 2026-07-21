import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { api, OnboardingTemplate } from "../api";
import { Badge } from "./ui/badge";
import { cn } from "../lib/utils";

type Props = {
  selectedId: string;
  onSelect: (id: string, tmpl?: OnboardingTemplate) => void;
  flowMode?: "lead" | "order" | "";
  className?: string;
};

const ICON_FALLBACK: Record<string, string> = {
  utensils: "🍽️",
  "shopping-basket": "🛒",
  droplets: "💧",
  pill: "💊",
  cake: "🎂",
  shirt: "👕",
  scissors: "✂️",
  monitor: "💻",
  "shopping-cart": "🛍️",
  "message-circle": "💬",
  wrench: "🔧",
  smartphone: "📱",
  tv: "📺",
  beef: "🥩",
  carrot: "🥬",
  milk: "🥛",
  dumbbell: "🏋️",
  stethoscope: "🩺",
  car: "🚗",
  "graduation-cap": "📚",
  home: "🏠",
  sparkles: "✨",
  flower: "💐",
  footprints: "👟",
  store: "🏪",
};

/** Display groups so every vertical category is easy to find. */
const CATEGORY_GROUPS: { label: string; verticals: string[] }[] = [
  {
    label: "Food & dining",
    verticals: ["restaurant", "bakery", "meat", "produce", "dairy"],
  },
  {
    label: "Grocery & essentials",
    verticals: ["grocery", "water", "pharmacy", "general_store"],
  },
  {
    label: "Retail & shopping",
    verticals: ["clothing", "shoes", "hardware", "mobile", "electronics", "beauty", "gifts"],
  },
  {
    label: "Services & booking",
    verticals: ["salon", "gym", "clinic", "auto", "education", "real_estate"],
  },
  {
    label: "Business & generic",
    verticals: ["pos", "generic"],
  },
];

function groupTemplates(items: OnboardingTemplate[]) {
  const used = new Set<string>();
  const groups: { label: string; items: OnboardingTemplate[] }[] = [];

  for (const g of CATEGORY_GROUPS) {
    const matched = items.filter((t) => g.verticals.includes(t.vertical));
    if (!matched.length) continue;
    matched.forEach((t) => used.add(t.id));
    groups.push({ label: g.label, items: matched });
  }

  const leftover = items.filter((t) => !used.has(t.id));
  if (leftover.length) {
    groups.push({ label: "Other", items: leftover });
  }
  return groups;
}

export function TemplatePicker({ selectedId, onSelect, flowMode, className }: Props) {
  const [items, setItems] = useState<OnboardingTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const q = flowMode ? `?flow_mode=${flowMode}` : "";
    api<{ items: OnboardingTemplate[] }>(`/api/dashboard/templates${q}`, { tenant: false })
      .then((r) => setItems(r.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [flowMode]);

  const visible = useMemo(() => {
    if (!flowMode) return items;
    const filtered = items.filter((t) => t.flow_mode === flowMode);
    return filtered.length ? filtered : items;
  }, [items, flowMode]);

  const groups = useMemo(() => groupTemplates(visible), [visible]);

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading templates…
      </div>
    );
  }

  if (!visible.length) {
    return <p className="text-sm text-muted-foreground">No templates found.</p>;
  }

  return (
    <div className={cn("max-h-[50vh] space-y-4 overflow-y-auto", className)}>
      {groups.map((g) => (
        <div key={g.label}>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            {g.label}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {g.items.map((t) => {
              const emoji = ICON_FALLBACK[t.icon || ""] || ICON_FALLBACK.store;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onSelect(t.id, t)}
                  className={cn(
                    "rounded-xl border px-3 py-3 text-left transition-colors",
                    selectedId === t.id
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-muted/40"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="text-lg" aria-hidden>
                        {emoji}
                      </span>
                      <p className="truncate text-sm font-semibold">{t.name}</p>
                    </div>
                    <Badge className="shrink-0 bg-muted text-[10px] text-muted-foreground">
                      {t.flow_mode}
                    </Badge>
                  </div>
                  <p className="mt-1.5 line-clamp-2 text-xs text-muted-foreground">
                    {t.blurb || t.description}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
