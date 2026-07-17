import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, X, AlertCircle, Info } from "lucide-react";

type ToastKind = "success" | "error" | "info";

type Toast = { id: number; message: string; kind: ToastKind };

type ToastCtx = { toast: (message: string, kind?: ToastKind) => void };

const Ctx = createContext<ToastCtx | null>(null);

let _id = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const toast = useCallback((message: string, kind: ToastKind = "success") => {
    const id = ++_id;
    setItems((prev) => [...prev, { id, message, kind }]);
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  }, []);

  function dismiss(id: number) {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }

  const icons = {
    success: CheckCircle2,
    error: AlertCircle,
    info: Info,
  };

  const styles = {
    success: "border-bahi-200 bg-white text-ink-900",
    error: "border-red-200 bg-white text-ink-900",
    info: "border-sky-200 bg-white text-ink-900",
  };

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div
        className="pointer-events-none fixed bottom-20 left-1/2 z-[100] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4 md:bottom-6 md:left-auto md:right-6 md:translate-x-0"
        aria-live="polite"
      >
        {items.map((t) => {
          const Icon = icons[t.kind];
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start gap-2 rounded-xl border px-3 py-2.5 shadow-card animate-fade-up ${styles[t.kind]}`}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-bahi-600" aria-hidden />
              <p className="flex-1 text-sm font-medium">{t.message}</p>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="rounded p-0.5 text-ink-500 transition hover:bg-canvas-100 hover:text-ink-800"
                aria-label="Dismiss"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}
