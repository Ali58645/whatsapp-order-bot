import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { ApiError, getToken, login } from "../api";
import { Button } from "../components/ui/button";
import { Input, Label } from "../components/ui/input";
import { cn } from "../lib/utils";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [shake, setShake] = useState(false);

  if (getToken()) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Login failed";
      setError(msg);
      setShake(true);
      setTimeout(() => setShake(false), 500);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left brand panel */}
      <div className="relative hidden overflow-hidden bg-[#0A0F0D] lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-20 top-10 h-72 w-72 animate-mesh rounded-full bg-bahi-600/30 blur-[100px]" />
          <div className="absolute bottom-10 right-0 h-96 w-96 animate-mesh rounded-full bg-teal-400/20 blur-[120px]" style={{ animationDelay: "-6s" }} />
          <div className="absolute left-1/3 top-1/2 h-48 w-48 animate-mesh rounded-full bg-emerald-500/15 blur-[80px]" style={{ animationDelay: "-12s" }} />
        </div>
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-bahi-400 to-bahi-700 text-lg font-bold text-white shadow-glow">
              B
            </div>
            <span className="text-xl font-bold tracking-tight text-white">BahiDesk</span>
          </div>
        </div>
        <div className="relative max-w-md">
          <h1 className="text-4xl font-bold leading-tight tracking-tight text-white">
            Your WhatsApp revenue console
          </h1>
          <p className="mt-4 text-base text-zinc-400">
            Leads, demos, and conversations — one premium surface for operators who sell.
          </p>
        </div>
        <p className="relative text-xs text-zinc-600">© Bahi POS · AccellionX</p>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center bg-background px-6 py-12">
        <motion.div
          animate={shake ? { x: [0, -8, 8, -6, 6, 0] } : { x: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm"
        >
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-bahi-400 to-bahi-700 font-bold text-white">
                B
              </div>
              <span className="text-lg font-bold">BahiDesk</span>
            </div>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">Welcome back</h2>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to your operator console</p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <div>
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1.5"
                required
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5"
                required
              />
            </div>
            {error && (
              <p className={cn("text-sm text-destructive")} role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy} size="lg">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              Sign in
            </Button>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
