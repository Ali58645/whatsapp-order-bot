import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  Activity,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Settings,
  Users,
  X,
  ChevronDown,
} from "lucide-react";
import { api, getTenantFilter, setTenantFilter, setToken, Tenant } from "../api";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/leads", label: "Leads", icon: Users },
  { to: "/orders", label: "Orders", icon: Package },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className={`flex items-center gap-2.5 ${compact ? "justify-center" : ""}`}>
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-bahi-600 text-sm font-extrabold text-white shadow-sm">
        B
      </div>
      {!compact && (
        <div>
          <p className="text-base font-bold tracking-tight text-white">
            Bahi<span className="text-bahi-300">Desk</span>
          </p>
          <p className="text-[10px] font-medium uppercase tracking-widest text-white/45">Console</p>
        </div>
      )}
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  return (
    <nav className="flex flex-1 flex-col gap-1 px-3">
      {nav.map((item) => {
        const Icon = item.icon;
        const active = item.end
          ? location.pathname === item.to || location.pathname === item.to + "/"
          : location.pathname.startsWith(item.to);
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-ui ${
              active
                ? "bg-sidebar-active text-white shadow-sm"
                : "text-white/65 hover:bg-sidebar-hover hover:text-white"
            }`}
          >
            <Icon className="h-[1.125rem] w-[1.125rem] shrink-0" strokeWidth={active ? 2.25 : 2} />
            {item.label}
          </NavLink>
        );
      })}
    </nav>
  );
}

export default function Layout() {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantId, setTenantId] = useState(getTenantFilter());
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    api<Tenant[]>("/api/dashboard/tenants", { tenant: false })
      .then(setTenants)
      .catch(() => setTenants([]));
  }, []);

  function onTenantChange(value: string) {
    setTenantId(value);
    setTenantFilter(value);
    window.dispatchEvent(new Event("tenant-change"));
  }

  function logout() {
    setToken(null);
    navigate("/login");
  }

  const tenantSelect = (
    <div className="relative">
      <label className="sr-only" htmlFor="tenant-select">
        Tenant
      </label>
      <select
        id="tenant-select"
        className="w-full appearance-none rounded-xl border border-white/10 bg-sidebar-hover py-2.5 pl-3 pr-8 text-sm font-medium text-white outline-none transition-ui focus:border-bahi-500/50 focus:ring-2 focus:ring-bahi-500/25"
        value={tenantId}
        onChange={(e) => onTenantChange(e.target.value)}
      >
        <option value="all" className="bg-ink-900 text-white">
          All tenants
        </option>
        {tenants.map((t) => (
          <option key={t.phone_number_id} value={t.phone_number_id} className="bg-ink-900 text-white">
            {t.name}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
    </div>
  );

  return (
    <div className="min-h-screen bg-canvas-50 md:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col bg-sidebar md:fixed md:inset-y-0 md:flex md:w-64">
        <div className="border-b border-white/8 px-5 py-5">
          <Logo />
        </div>
        <div className="flex flex-1 flex-col py-4">
          <NavItems />
        </div>
        <div className="space-y-3 border-t border-white/8 px-4 py-4">
          {tenantSelect}
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-white/55 transition-ui hover:bg-sidebar-hover hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Log out
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-canvas-200 bg-white/95 px-4 py-3 backdrop-blur-md md:hidden">
        <Logo compact />
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="rounded-lg p-2 text-ink-700 transition-ui hover:bg-canvas-100"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-ink-950/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-sidebar shadow-drawer animate-slide-in">
            <div className="flex items-center justify-between border-b border-white/8 px-4 py-4">
              <Logo />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-lg p-2 text-white/60 hover:bg-sidebar-hover hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex flex-1 flex-col py-3">
              <NavItems onNavigate={() => setMobileOpen(false)} />
            </div>
            <div className="space-y-3 border-t border-white/8 px-4 py-4">
              {tenantSelect}
              <button
                type="button"
                onClick={logout}
                className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/55 hover:bg-sidebar-hover hover:text-white"
              >
                <LogOut className="h-4 w-4" />
                Log out
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex min-h-screen flex-1 flex-col md:pl-64">
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-8 animate-fade-up">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-canvas-200 bg-white/95 px-1 py-1 backdrop-blur-md md:hidden">
        {nav.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-0.5 rounded-lg py-2 text-[10px] font-semibold transition-ui ${
                  isActive ? "text-bahi-700" : "text-ink-500"
                }`
              }
            >
              <Icon className="h-5 w-5" strokeWidth={2} />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
