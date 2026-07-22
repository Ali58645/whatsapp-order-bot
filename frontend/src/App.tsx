import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getRole, getToken, isOwner, isSupportSession } from "./api";
import Layout from "./components/layout/Layout";
import Login from "./pages/Login";
import { Skeleton } from "./components/ui/avatar";

const Leads = lazy(() => import("./pages/Leads"));
const Orders = lazy(() => import("./pages/Orders"));
const Conversations = lazy(() => import("./pages/Conversations"));
const Settings = lazy(() => import("./pages/Settings"));
const Businesses = lazy(() => import("./pages/Businesses"));
const Team = lazy(() => import("./pages/Team"));
const AccessLog = lazy(() => import("./pages/AccessLog"));
const OwnerHome = lazy(() => import("./pages/owner/OwnerHome"));
const OwnerBot = lazy(() => import("./pages/owner/OwnerBot"));
const Customers = lazy(() => import("./pages/owner/Customers"));
const OwnerMenu = lazy(() => import("./pages/owner/OwnerMenu"));
const Billing = lazy(() => import("./pages/owner/Billing"));
const Account = lazy(() => import("./pages/owner/Account"));
const OwnerTeam = lazy(() => import("./pages/owner/OwnerTeam"));
const Broadcast = lazy(() => import("./pages/owner/Broadcast"));
const Channels = lazy(() => import("./pages/Channels"));

function Private({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Platform console — real admins only (not support / owner sessions). */
function AdminOnly({ children }: { children: React.ReactNode }) {
  if (isOwner() || isSupportSession()) return <Navigate to="/" replace />;
  if (getRole() !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

/** Owner workspace — real owners and admin support sessions. */
function OwnerOnly({ children }: { children: React.ReactNode }) {
  if (!(isOwner() || isSupportSession())) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function TeamRoute() {
  if (isOwner() || isSupportSession()) return <OwnerTeam />;
  return <Team />;
}

function HomeRoute() {
  if (isOwner() || isSupportSession()) return <OwnerHome />;
  return <Businesses />;
}

function PageFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-40 w-full rounded-2xl" />
      <Skeleton className="h-40 w-full rounded-2xl" />
    </div>
  );
}

function SuspensePage({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageFallback />}>{children}</Suspense>;
}

export default function App() {
  const [, bump] = useState(0);
  useEffect(() => {
    const on = () => bump((n) => n + 1);
    window.addEventListener("storage", on);
    return () => window.removeEventListener("storage", on);
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Private>
            <Layout />
          </Private>
        }
      >
        <Route
          index
          element={
            <SuspensePage>
              <HomeRoute />
            </SuspensePage>
          }
        />

        {/* Owner / support shell */}
        <Route
          path="customers"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Customers />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="my-bot"
          element={
            <OwnerOnly>
              <SuspensePage>
                <OwnerBot />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="my-bot/:section"
          element={
            <OwnerOnly>
              <SuspensePage>
                <OwnerBot />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="menu"
          element={
            <OwnerOnly>
              <SuspensePage>
                <OwnerMenu />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="billing"
          element={
            <SuspensePage>
              <Billing />
            </SuspensePage>
          }
        />
        <Route
          path="account"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Account />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="broadcast"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Broadcast />
              </SuspensePage>
            </OwnerOnly>
          }
        />

        <Route
          path="channels"
          element={
            <SuspensePage>
              <Channels />
            </SuspensePage>
          }
        />
        <Route
          path="channels/:channel"
          element={
            <SuspensePage>
              <Channels />
            </SuspensePage>
          }
        />

        {/* Legacy tenant inbox routes — only via support session deep links; not in admin nav */}
        <Route
          path="leads"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Leads />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="orders"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Orders />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="conversations"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Conversations />
              </SuspensePage>
            </OwnerOnly>
          }
        />

        {/* Admin platform console */}
        <Route
          path="businesses"
          element={<Navigate to="/" replace />}
        />
        <Route
          path="team"
          element={
            <SuspensePage>
              <TeamRoute />
            </SuspensePage>
          }
        />
        <Route
          path="access-log"
          element={
            <AdminOnly>
              <SuspensePage>
                <AccessLog />
              </SuspensePage>
            </AdminOnly>
          }
        />
        <Route
          path="settings"
          element={
            <AdminOnly>
              <SuspensePage>
                <Settings />
              </SuspensePage>
            </AdminOnly>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
