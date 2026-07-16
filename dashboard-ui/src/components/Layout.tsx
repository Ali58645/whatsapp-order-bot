import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, getTenantFilter, setTenantFilter, setToken, Tenant } from "../api";

const nav = [
  { to: "/", label: "Overview", end: true },
  { to: "/leads", label: "Leads" },
  { to: "/orders", label: "Orders" },
  { to: "/activity", label: "Activity" },
];

export default function Layout() {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantId, setTenantId] = useState(getTenantFilter());

  useEffect(() => {
    api<Tenant[]>("/api/dashboard/tenants", { tenant: false })
      .then(setTenants)
      .catch(() => setTenants([]));
  }, []);

  function onTenantChange(value: string) {
    setTenantId(value);
    setTenantFilter(value);
    // Soft reload current view via custom event
    window.dispatchEvent(new Event("tenant-change"));
  }

  function logout() {
    setToken(null);
    navigate("/login");
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-ink-900/8 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
          <div className="mr-auto min-w-0">
            <p className="font-display text-xl font-semibold tracking-tight text-ink-900">
              Bahi<span className="text-sea-600">Desk</span>
            </p>
            <p className="truncate text-xs text-ink-600">WhatsApp bot console</p>
          </div>

          <label className="flex items-center gap-2 text-sm text-ink-700">
            <span className="hidden sm:inline">Tenant</span>
            <select
              className="max-w-[10rem] rounded-lg border border-ink-900/10 bg-white px-2 py-1.5 text-sm shadow-sm sm:max-w-[14rem]"
              value={tenantId}
              onChange={(e) => onTenantChange(e.target.value)}
            >
              <option value="all">All tenants</option>
              {tenants.map((t) => (
                <option key={t.phone_number_id} value={t.phone_number_id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={logout}
            className="rounded-lg px-2.5 py-1.5 text-sm text-ink-600 hover:bg-mist-100"
          >
            Log out
          </button>
        </div>

        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 pb-2">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-ink-900 text-white"
                    : "text-ink-700 hover:bg-mist-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 animate-fade-up">
        <Outlet />
      </main>
    </div>
  );
}
