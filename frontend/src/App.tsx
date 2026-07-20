import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getRole, getToken, isOwner, isReadonlySession } from "./api";
import Layout from "./components/layout/Layout";
import Login from "./pages/Login";
import { Skeleton } from "./components/ui/avatar";

const Overview = lazy(() => import("./pages/Overview"));
const Leads = lazy(() => import("./pages/Leads"));
const Orders = lazy(() => import("./pages/Orders"));
const Conversations = lazy(() => import("./pages/Conversations"));
const Activity = lazy(() => import("./pages/Activity"));
const Settings = lazy(() => import("./pages/Settings"));
const Businesses = lazy(() => import("./pages/Businesses"));
const Team = lazy(() => import("./pages/Team"));
const OwnerHome = lazy(() => import("./pages/owner/OwnerHome"));
const Customers = lazy(() => import("./pages/owner/Customers"));
const Billing = lazy(() => import("./pages/owner/Billing"));

function Private({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  if (isOwner() || isReadonlySession()) return <Navigate to="/" replace />;
  if (getRole() !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function OwnerOnly({ children }: { children: React.ReactNode }) {
  if (!(isOwner() || isReadonlySession())) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function HomeRoute() {
  if (isOwner() || isReadonlySession()) return <OwnerHome />;
  return <Overview />;
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
  // Re-read role after login / view-as without full remount of router tree
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

        {/* Owner shell */}
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
                <Settings ownerMode />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="menu"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Settings ownerMode menuOnly />
              </SuspensePage>
            </OwnerOnly>
          }
        />
        <Route
          path="billing"
          element={
            <OwnerOnly>
              <SuspensePage>
                <Billing />
              </SuspensePage>
            </OwnerOnly>
          }
        />

        {/* Admin console */}
        <Route
          path="leads"
          element={
            <AdminOnly>
              <SuspensePage>
                <Leads />
              </SuspensePage>
            </AdminOnly>
          }
        />
        <Route
          path="orders"
          element={
            <AdminOnly>
              <SuspensePage>
                <Orders />
              </SuspensePage>
            </AdminOnly>
          }
        />
        <Route
          path="conversations"
          element={
            <AdminOnly>
              <SuspensePage>
                <Conversations />
              </SuspensePage>
            </AdminOnly>
          }
        />
        <Route
          path="activity"
          element={
            <AdminOnly>
              <SuspensePage>
                <Activity />
              </SuspensePage>
            </AdminOnly>
          }
        />
        <Route
          path="businesses"
          element={
            <AdminOnly>
              <SuspensePage>
                <Businesses />
              </SuspensePage>
            </AdminOnly>
          }
        />
        <Route
          path="team"
          element={
            <AdminOnly>
              <SuspensePage>
                <Team />
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
