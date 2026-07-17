import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getToken } from "./api";
import Layout from "./components/layout/Layout";
import Login from "./pages/Login";
import { Skeleton } from "./components/ui/avatar";

const Overview = lazy(() => import("./pages/Overview"));
const Leads = lazy(() => import("./pages/Leads"));
const Orders = lazy(() => import("./pages/Orders"));
const Conversations = lazy(() => import("./pages/Conversations"));
const Activity = lazy(() => import("./pages/Activity"));
const Settings = lazy(() => import("./pages/Settings"));

function Private({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
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

export default function App() {
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
            <Suspense fallback={<PageFallback />}>
              <Overview />
            </Suspense>
          }
        />
        <Route
          path="leads"
          element={
            <Suspense fallback={<PageFallback />}>
              <Leads />
            </Suspense>
          }
        />
        <Route
          path="orders"
          element={
            <Suspense fallback={<PageFallback />}>
              <Orders />
            </Suspense>
          }
        />
        <Route
          path="conversations"
          element={
            <Suspense fallback={<PageFallback />}>
              <Conversations />
            </Suspense>
          }
        />
        <Route
          path="activity"
          element={
            <Suspense fallback={<PageFallback />}>
              <Activity />
            </Suspense>
          }
        />
        <Route
          path="settings"
          element={
            <Suspense fallback={<PageFallback />}>
              <Settings />
            </Suspense>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
