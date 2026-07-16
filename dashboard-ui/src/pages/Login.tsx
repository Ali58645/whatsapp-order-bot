import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
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
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm animate-fade-up rounded-2xl bg-white/90 p-8 shadow-soft"
      >
        <p className="font-display text-3xl font-semibold text-ink-900">
          Bahi<span className="text-sea-600">Desk</span>
        </p>
        <p className="mt-1 text-sm text-ink-600">Sign in to the bot console</p>

        <label className="mt-6 block text-sm font-medium text-ink-800">
          Username
          <input
            className="mt-1 w-full rounded-lg border border-ink-900/10 px-3 py-2 outline-none ring-sea-500 focus:ring-2"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label className="mt-4 block text-sm font-medium text-ink-800">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded-lg border border-ink-900/10 px-3 py-2 outline-none ring-sea-500 focus:ring-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && (
          <p className="mt-3 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-lg bg-sea-600 py-2.5 text-sm font-semibold text-white transition hover:bg-sea-700 disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
