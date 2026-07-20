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
  store: "🏪",
};

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
    <div className={cn("grid max-h-[50vh] gap-2 overflow-y-auto sm:grid-cols-2", className)}>
      {visible.map((t) => {
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
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-lg" aria-hidden>
                  {emoji}
                </span>
                <p className="truncate text-sm font-semibold">{t.name}</p>
              </div>
              <Badge className="shrink-0 bg-muted text-muted-foreground text-[10px]">
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
  );
}
