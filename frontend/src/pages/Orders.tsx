import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { api, Order } from "../api";
import { Avatar, Skeleton } from "../components/ui/avatar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { EmptyState } from "../components/ui/empty-state";
import { formatRs, relativeTime } from "../lib/utils";

export default function Orders() {
  const [items, setItems] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Order | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api<{ items: Order[]; total: number }>("/api/dashboard/orders")
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">Confirmed food orders from the bot</p>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : !items.length ? (
        <EmptyState
          title="No orders yet"
          description="When customers confirm, tickets appear here with line items and totals."
          illustration="orders"
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border">
          <ul className="divide-y divide-border">
            {items.map((o) => {
              const name = o.contact.profile_name || o.contact.wa_id;
              return (
                <li key={o.id}>
                  <button
                    onClick={() => setSelected(o)}
                    className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-muted/30"
                  >
                    <Avatar name={name} seed={o.contact.wa_id} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{name}</p>
                      <p className="text-xs text-muted-foreground">
                        #{o.id} · {relativeTime(o.created_at)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold tabular">{formatRs(o.total)}</p>
                      <Badge className="mt-1 bg-primary/15 text-primary">{o.status}</Badge>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <AnimatePresence>
        {selected && (
          <motion.div
            className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 backdrop-blur-sm sm:items-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelected(null)}
          >
            <motion.div
              initial={{ y: 24, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 16, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-2xl border border-border bg-card p-5 shadow-elevated"
              role="dialog"
              aria-label="Order details"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Order #{selected.id}</h2>
                  <p className="text-sm text-muted-foreground">
                    {selected.contact.profile_name || selected.contact.wa_id}
                  </p>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setSelected(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              {selected.delivery_address && (
                <p className="mt-3 text-sm text-muted-foreground">
                  {selected.delivery_address}
                </p>
              )}
              <ul className="mt-4 space-y-2">
                {(selected.items || []).map((it, i) => (
                  <li key={i} className="flex justify-between text-sm">
                    <span>
                      {it.qty || 1}× {it.name || "Item"}
                    </span>
                    <span className="tabular text-muted-foreground">
                      {formatRs((it.qty || 1) * (it.price || 0))}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex justify-between border-t border-border pt-3 text-base font-semibold">
                <span>Total</span>
                <span className="tabular">{formatRs(selected.total)}</span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
