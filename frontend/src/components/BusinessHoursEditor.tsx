import { Label, Textarea } from "./ui/input";
import { cn } from "../lib/utils";

export type BusinessHoursConfig = {
  enabled?: boolean;
  timezone?: string;
  away_message?: string;
  days?: Record<string, string[][]>;
};

const DAY_DEFS = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
  { key: "wed", label: "Wed" },
  { key: "thu", label: "Thu" },
  { key: "fri", label: "Fri" },
  { key: "sat", label: "Sat" },
  { key: "sun", label: "Sun" },
] as const;

type DayKey = (typeof DAY_DEFS)[number]["key"];

const TIMEZONES = [
  { value: "Asia/Karachi", label: "Pakistan (Karachi)" },
  { value: "Asia/Dubai", label: "UAE (Dubai)" },
  { value: "Asia/Riyadh", label: "Saudi Arabia (Riyadh)" },
  { value: "Asia/Kolkata", label: "India (Kolkata)" },
  { value: "Europe/London", label: "UK (London)" },
  { value: "America/New_York", label: "US Eastern" },
  { value: "UTC", label: "UTC" },
];

const DEFAULT_SLOT: [string, string] = ["09:00", "18:00"];

export const AWAY_MESSAGE_UR =
  "Shukriya — abhi team available nahi. Business hours mein rabta karein.";
export const AWAY_MESSAGE_EN =
  "Thanks for messaging — our team is currently unavailable. Please reach out during business hours.";

export function defaultAwayMessage(lang: "en" | "roman_urdu" | string = "roman_urdu"): string {
  return lang === "en" || lang === "english" ? AWAY_MESSAGE_EN : AWAY_MESSAGE_UR;
}

export const DEFAULT_BUSINESS_HOURS: BusinessHoursConfig = {
  enabled: false,
  timezone: "Asia/Karachi",
  away_message: AWAY_MESSAGE_UR,
  days: {
    mon: [DEFAULT_SLOT],
    tue: [DEFAULT_SLOT],
    wed: [DEFAULT_SLOT],
    thu: [DEFAULT_SLOT],
    fri: [DEFAULT_SLOT],
    sat: [["10:00", "14:00"]],
    sun: [],
  },
};

/** Build default hours seeded for the selected bot language. */
export function defaultBusinessHoursForLang(
  lang: "en" | "roman_urdu" | string = "roman_urdu"
): BusinessHoursConfig {
  return {
    ...DEFAULT_BUSINESS_HOURS,
    away_message: defaultAwayMessage(lang),
    days: {
      mon: [DEFAULT_SLOT],
      tue: [DEFAULT_SLOT],
      wed: [DEFAULT_SLOT],
      thu: [DEFAULT_SLOT],
      fri: [DEFAULT_SLOT],
      sat: [["10:00", "14:00"]],
      sun: [],
    },
  };
}

function normalizeDays(days?: Record<string, string[][]>): Record<DayKey, string[][]> {
  const out = {} as Record<DayKey, string[][]>;
  for (const { key } of DAY_DEFS) {
    const slots = days?.[key];
    if (!Array.isArray(slots)) {
      out[key] = DEFAULT_BUSINESS_HOURS.days?.[key] ? [...DEFAULT_BUSINESS_HOURS.days[key]] : [];
      continue;
    }
    out[key] = slots
      .filter((slot) => Array.isArray(slot) && slot.length >= 2)
      .map((slot) => [String(slot[0]).slice(0, 5), String(slot[1]).slice(0, 5)]);
  }
  return out;
}

export function normalizeBusinessHours(raw?: BusinessHoursConfig | null): BusinessHoursConfig {
  if (!raw) return { ...DEFAULT_BUSINESS_HOURS };
  return {
    ...DEFAULT_BUSINESS_HOURS,
    ...raw,
    days: normalizeDays(raw.days),
  };
}

function dayOpen(days: Record<DayKey, string[][]>, key: DayKey): boolean {
  return (days[key] || []).length > 0;
}

function daySlot(days: Record<DayKey, string[][]>, key: DayKey): [string, string] {
  const slot = days[key]?.[0];
  if (!slot) return DEFAULT_SLOT;
  return [slot[0] || DEFAULT_SLOT[0], slot[1] || DEFAULT_SLOT[1]];
}

type Props = {
  value?: BusinessHoursConfig | null;
  onChange: (next: BusinessHoursConfig) => void;
  disabled?: boolean;
  className?: string;
};

export function BusinessHoursEditor({ value, onChange, disabled, className }: Props) {
  const bh = normalizeBusinessHours(value);
  const days = bh.days as Record<DayKey, string[][]>;

  const patch = (partial: Partial<BusinessHoursConfig>) => {
    onChange(normalizeBusinessHours({ ...bh, ...partial }));
  };

  const patchDay = (key: DayKey, open: boolean, start?: string, end?: string) => {
    const nextDays = { ...days };
    if (!open) {
      nextDays[key] = [];
    } else {
      const [a, b] = daySlot(days, key);
      nextDays[key] = [[start ?? a, end ?? b]];
    }
    patch({ days: nextDays });
  };

  const copyMondayToWeekdays = () => {
    const mon = days.mon?.length ? [...days.mon[0]] : [...DEFAULT_SLOT];
    const nextDays = { ...days };
    for (const key of ["tue", "wed", "thu", "fri"] as DayKey[]) {
      nextDays[key] = [[mon[0], mon[1]]];
    }
    patch({ days: nextDays });
  };

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Business hours</p>
          <p className="text-xs text-muted-foreground">
            Outside hours the bot sends an away message only.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={Boolean(bh.enabled)}
            disabled={disabled}
            onChange={(e) =>
              patch({
                enabled: e.target.checked,
                ...(e.target.checked && !value?.days ? { days: DEFAULT_BUSINESS_HOURS.days } : {}),
              })
            }
          />
          Enabled
        </label>
      </div>

      {bh.enabled && (
        <>
          <div>
            <Label>Timezone</Label>
            <select
              className="mt-1.5 flex h-10 w-full rounded-xl border border-input bg-card/80 px-3.5 text-sm text-foreground focus-ring disabled:opacity-50"
              value={bh.timezone || "Asia/Karachi"}
              disabled={disabled}
              onChange={(e) => patch({ timezone: e.target.value })}
            >
              {TIMEZONES.map((tz) => (
                <option key={tz.value} value={tz.value}>
                  {tz.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <Label className="mb-0">Weekly schedule</Label>
              <button
                type="button"
                className="text-[11px] text-primary hover:underline disabled:opacity-50"
                disabled={disabled}
                onClick={copyMondayToWeekdays}
              >
                Copy Mon → weekdays
              </button>
            </div>
            <div className="space-y-2 rounded-xl border border-border bg-background/60 p-3">
              {DAY_DEFS.map(({ key, label }) => {
                const open = dayOpen(days, key);
                const [start, end] = daySlot(days, key);
                return (
                  <div key={key} className="flex flex-wrap items-center gap-2 sm:gap-3">
                    <span className="w-9 text-xs font-medium text-muted-foreground">{label}</span>
                    <label className="flex items-center gap-1.5 text-xs">
                      <input
                        type="checkbox"
                        checked={open}
                        disabled={disabled}
                        onChange={(e) => patchDay(key, e.target.checked)}
                      />
                      Open
                    </label>
                    {open ? (
                      <div className="flex flex-1 flex-wrap items-center gap-2">
                        <input
                          type="time"
                          className="h-9 rounded-lg border border-input bg-card/80 px-2 text-sm disabled:opacity-50"
                          value={start}
                          disabled={disabled}
                          onChange={(e) => patchDay(key, true, e.target.value, end)}
                        />
                        <span className="text-xs text-muted-foreground">to</span>
                        <input
                          type="time"
                          className="h-9 rounded-lg border border-input bg-card/80 px-2 text-sm disabled:opacity-50"
                          value={end}
                          disabled={disabled}
                          onChange={(e) => patchDay(key, true, start, e.target.value)}
                        />
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">Closed</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div>
            <Label>Away message</Label>
            <Textarea
              className="mt-1.5"
              rows={2}
              value={bh.away_message || ""}
              disabled={disabled}
              onChange={(e) => patch({ away_message: e.target.value })}
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              Sent automatically when someone messages outside your schedule.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
