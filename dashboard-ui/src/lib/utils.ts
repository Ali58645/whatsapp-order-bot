import type { EventItem } from "../api";

/** Relative time e.g. "2h ago" */
export function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const sec = Math.floor((Date.now() - d.getTime()) / 1000);
    if (sec < 60) return "just now";
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

export function initials(name: string, fallback = "?"): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return fallback.slice(0, 2).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export type StatusStyle = { label: string; className: string };

const STATUS_MAP: Record<string, StatusStyle> = {
  active: { label: "Bot · In Progress", className: "bg-amber-100 text-amber-800 ring-amber-200/80" },
  confirmed: { label: "Demo Scheduled", className: "bg-bahi-100 text-bahi-800 ring-bahi-200/80" },
  stalled: { label: "Not Responding", className: "bg-slate-100 text-slate-600 ring-slate-200/80" },
  new: { label: "New", className: "bg-sky-100 text-sky-800 ring-sky-200/80" },
};

export function leadStatus(status: string): StatusStyle {
  const key = (status || "new").toLowerCase();
  return STATUS_MAP[key] ?? { label: status || "New", className: "bg-sky-100 text-sky-800 ring-sky-200/80" };
}

/** Last N days of event counts (oldest → newest) for sparklines */
export function eventsByDay(events: EventItem[], days = 7): number[] {
  const counts = Array(days).fill(0);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  for (const ev of events) {
    if (!ev.created_at) continue;
    const d = new Date(ev.created_at);
    d.setHours(0, 0, 0, 0);
    const diff = Math.round((now.getTime() - d.getTime()) / 86400000);
    if (diff >= 0 && diff < days) counts[days - 1 - diff] += 1;
  }
  return counts;
}

export function deltaVsPrior(values: number[]): { delta: number; pct: number | null } {
  if (values.length < 2) return { delta: 0, pct: null };
  const today = values[values.length - 1];
  const prior = values[values.length - 2];
  const delta = today - prior;
  const pct = prior === 0 ? (today > 0 ? 100 : 0) : Math.round((delta / prior) * 100);
  return { delta, pct };
}

export const STATUS_BAR_COLORS: Record<string, string> = {
  active: "#d97706",
  confirmed: "#0f655e",
  stalled: "#94a3b8",
  new: "#0284c7",
};

export function eventIconType(type: string): "lead" | "order" | "mute" | "error" | "default" {
  if (type === "confirmed" || type === "activation") return "lead";
  if (type.includes("order")) return "order";
  if (type === "mute" || type === "human_takeover") return "mute";
  if (type === "error") return "error";
  return "default";
}
