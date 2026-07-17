import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { AlertCircle, Loader2 } from "lucide-react";
import { ApiError, getToken, login } from "../api";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (getToken()) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 20% 0%, rgba(15,101,94,0.18), transparent 55%), radial-gradient(ellipse 60% 50% at 100% 100%, rgba(10,22,40,0.08), transparent 50%), linear-gradient(180deg, #f3efe8 0%, #faf8f5 45%, #faf8f5 100%)",
        }}
      />

      <form
        onSubmit={onSubmit}
        className="relative w-full max-w-[22rem] animate-fade-up rounded-2xl border border-canvas-200 bg-white p-8 shadow-card"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-bahi-600 text-lg font-extrabold text-white">
            B
          </div>
          <div>
            <p className="text-xl font-bold tracking-tight text-ink-900">
              Bahi<span className="text-bahi-600">Desk</span>
            </p>
            <p className="text-xs text-ink-500">WhatsApp bot console</p>
          </div>
        </div>

        <p className="mt-6 text-sm text-ink-600">Sign in to manage leads, orders, and bot settings.</p>

        <label className="mt-5 block text-sm font-semibold text-ink-800">
          Username
          <input
            className="mt-1.5 w-full rounded-xl border border-canvas-200 bg-canvas-50 px-3.5 py-2.5 text-sm outline-none transition-ui focus:border-bahi-400 focus:bg-white focus:ring-2 focus:ring-bahi-500/20"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label className="mt-4 block text-sm font-semibold text-ink-800">
          Password
          <input
            type="password"
            className="mt-1.5 w-full rounded-xl border border-canvas-200 bg-canvas-50 px-3.5 py-2.5 text-sm outline-none transition-ui focus:border-bahi-400 focus:bg-white focus:ring-2 focus:ring-bahi-500/20"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && (
          <div
            className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800"
            role="alert"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-bahi-600 py-3 text-sm font-bold text-white transition-ui hover:bg-bahi-700 disabled:opacity-60"
        >
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Signing in…
            </>
          ) : (
            "Sign in"
          )}
        </button>
      </form>
    </div>
  );
}
