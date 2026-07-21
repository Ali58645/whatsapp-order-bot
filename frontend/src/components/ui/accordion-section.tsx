import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "../../lib/utils";

type Props = {
  title: string;
  count?: number;
  countLabel?: string;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
  /** Optional control before the title (e.g. drag handle). */
  leading?: ReactNode;
};

export function AccordionSection({
  title,
  count,
  countLabel = "items",
  defaultOpen = false,
  children,
  className,
  leading,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section
      className={cn(
        "overflow-hidden rounded-2xl border border-border bg-card",
        className
      )}
    >
      <div className="flex items-stretch">
        {leading}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-3 px-5 py-4 text-left transition",
            leading ? "pl-2" : "",
            "hover:bg-muted/30 focus-ring"
          )}
        >
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-foreground">{title}</div>
            {count != null && (
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                {count} {countLabel}
              </div>
            )}
          </div>
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
              open && "rotate-180"
            )}
          />
        </button>
      </div>
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="space-y-4 border-t border-border px-5 py-4">{children}</div>
        </div>
      </div>
    </section>
  );
}
