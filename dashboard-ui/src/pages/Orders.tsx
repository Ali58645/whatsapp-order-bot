import { useCallback, useEffect, useState } from "react";
import { ChevronRight, X } from "lucide-react";
import { api, Order } from "../api";
import Avatar from "../components/ui/Avatar";
import PageHeader from "../components/ui/PageHeader";
import { relativeTime } from "../lib/utils";

function OrderCard({ order, onClick }: { order: Order; onClick: () => void }) {
  const name = order.contact.profile_name || order.contact.wa_id;
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-xl border border-canvas-200 bg-white p-4 text-left shadow-card transition-ui hover:border-bahi-200 md:hidden"
    >
      <Avatar name={name} />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-ink-900">{name}</p>
        <p className="text-sm font-bold text-bahi-700">Rs {order.total.toLocaleString()}</p>
        <p className="text-xs capitalize text-ink-500">{order.status} · {relativeTime(order.created_at)}</p>
      </div>
      <ChevronRight className="h-4 w-4 text-ink-300" />
    </button>
  );
}

export default function OrdersPage() {
  const [items, setItems] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setError("");
    setLoading(true);
    api<{ items: Order[]; total: number }>("/api/dashboard/orders")
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div>
      <PageHeader title="Orders" subtitle={`${total} total`} />

      {error && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</p>
      )}

      <div className="space-y-3 md:hidden">
        {loading &&
          [1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-shimmer rounded-xl bg-canvas-200" />
          ))}
        {!loading && items.length === 0 && (
          <div className="rounded-2xl border border-dashed border-canvas-300 bg-white py-12 text-center text-sm text-ink-500">
            No orders yet
          </div>
        )}
        {!loading && items.map((o) => (
          <OrderCard key={o.id} order={o} onClick={() => setSelected(o)} />
        ))}
      </div>

      <div className="hidden overflow-hidden rounded-2xl border border-canvas-200 bg-white shadow-card md:block">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="border-b border-canvas-100 bg-canvas-50 text-[11px] font-bold uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">When</th>
              </tr>
            </thead>
            <tbody>
              {loading &&
                [1, 2, 3].map((i) => (
                  <tr key={i} className="border-b border-canvas-100">
                    <td colSpan={4} className="px-4 py-4">
                      <div className="h-5 animate-shimmer rounded bg-canvas-200" />
                    </td>
                  </tr>
                ))}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center text-ink-500">
                    No orders yet
                  </td>
                </tr>
              )}
              {!loading &&
                items.map((o) => {
                  const name = o.contact.profile_name || o.contact.wa_id;
                  return (
                    <tr
                      key={o.id}
                      className="cursor-pointer border-b border-canvas-100 transition-ui last:border-0 hover:bg-bahi-50/40"
                      onClick={() => setSelected(o)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={name} size="sm" />
                          <div>
                            <p className="font-semibold">{name}</p>
                            <p className="font-mono text-xs text-ink-400">{o.contact.wa_id}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-bold tabular-nums text-bahi-700">
                        Rs {o.total.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 capitalize">{o.status}</td>
                      <td className="px-4 py-3 text-xs font-medium text-ink-500">
                        {relativeTime(o.created_at)}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/45 backdrop-blur-[2px] sm:items-center"
          onClick={() => setSelected(null)}
        >
          <div
            className="animate-slide-in m-0 w-full max-w-md rounded-t-2xl border border-canvas-200 bg-white p-5 shadow-drawer sm:m-4 sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold text-ink-900">Order #{selected.id}</h2>
                <p className="mt-0.5 text-sm text-ink-500">
                  {selected.contact.profile_name} · {selected.contact.wa_id}
                </p>
              </div>
              <button
                type="button"
                className="rounded-lg p-2 text-ink-500 hover:bg-canvas-100"
                onClick={() => setSelected(null)}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mt-4 text-sm">
              <span className="font-semibold text-ink-500">Address:</span>{" "}
              {selected.delivery_address || "—"}
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              {(selected.items || []).map((it, i) => (
                <li key={i} className="flex justify-between gap-2 border-b border-canvas-100 pb-2 last:border-0">
                  <span>
                    {it.qty || 1}× {it.name || "Item"}
                  </span>
                  <span className="font-semibold tabular-nums text-ink-700">
                    Rs {((it.price || 0) * (it.qty || 1)).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t border-canvas-200 pt-3 text-right text-lg font-extrabold text-bahi-700">
              Rs {selected.total.toLocaleString()}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
