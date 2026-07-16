import { useCallback, useEffect, useState } from "react";
import { api, Order } from "../api";

function formatTime(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function OrdersPage() {
  const [items, setItems] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Order | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    api<{ items: Order[]; total: number }>("/api/dashboard/orders")
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const onTenant = () => load();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [load]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Orders</h1>
        <p className="text-sm text-ink-600">{total} total</p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="overflow-hidden rounded-2xl bg-white/90 shadow-soft">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="border-b border-mist-100 bg-mist-50/80 text-xs uppercase tracking-wide text-ink-600">
              <tr>
                <th className="px-4 py-3 font-medium">Contact</th>
                <th className="px-4 py-3 font-medium">Total</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-ink-600">
                    No orders yet
                  </td>
                </tr>
              )}
              {items.map((o) => (
                <tr
                  key={o.id}
                  className="cursor-pointer border-b border-mist-100 last:border-0 hover:bg-sea-50/40"
                  onClick={() => setSelected(o)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium">{o.contact.profile_name || "—"}</p>
                    <p className="font-mono text-xs text-ink-600">{o.contact.wa_id}</p>
                  </td>
                  <td className="px-4 py-3 font-medium">
                    Rs {o.total.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 capitalize">{o.status}</td>
                  <td className="px-4 py-3 text-xs text-ink-600">
                    {formatTime(o.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-40 flex items-end justify-center bg-ink-950/40 sm:items-center"
          onClick={() => setSelected(null)}
        >
          <div
            className="animate-fade-up m-0 w-full max-w-md rounded-t-2xl bg-white p-5 shadow-soft sm:m-4 sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <h2 className="font-display text-xl font-semibold">Order #{selected.id}</h2>
              <button
                type="button"
                className="text-sm text-ink-600"
                onClick={() => setSelected(null)}
              >
                Close
              </button>
            </div>
            <p className="mt-1 text-sm text-ink-600">
              {selected.contact.profile_name} · {selected.contact.wa_id}
            </p>
            <p className="mt-3 text-sm">
              <span className="text-ink-600">Address:</span>{" "}
              {selected.delivery_address || "—"}
            </p>
            <ul className="mt-3 space-y-1 text-sm">
              {(selected.items || []).map((it, i) => (
                <li key={i} className="flex justify-between gap-2">
                  <span>
                    {it.qty || 1}× {it.name || "Item"}
                  </span>
                  <span className="text-ink-700">
                    Rs {((it.price || 0) * (it.qty || 1)).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t border-mist-100 pt-3 text-right font-semibold">
              Total Rs {selected.total.toLocaleString()}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
