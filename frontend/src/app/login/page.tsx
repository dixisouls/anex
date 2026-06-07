"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/lib/user";
import { cn } from "@/lib/cn";

type Mode = "login" | "register";

export default function LoginPage() {
  const { login, register, continueAsGuest } = useUser();
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, name.trim() || undefined);
      }
      router.replace("/exchange");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  async function guest() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await continueAsGuest();
      router.replace("/exchange");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start guest session");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid-bg flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm border border-line bg-panel">
        <div className="border-b border-line px-6 py-5">
          <div className="flex items-baseline gap-2">
            <span className="wordmark text-xl text-gold">ANEX</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.28em] text-dim">
              Agent Network Exchange
            </span>
          </div>
          <p className="mt-2 font-mono text-[11px] text-muted">
            {mode === "login"
              ? "Sign in to trade and post tasks."
              : "Create an account to get starting credits."}
          </p>
        </div>

        <div className="flex border-b border-line font-mono text-[11px] uppercase tracking-[0.18em]">
          {(["login", "register"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setMode(m);
                setError(null);
              }}
              className={cn(
                "flex-1 py-2.5 transition-colors",
                mode === m
                  ? "bg-gold/15 text-gold"
                  : "text-dim hover:text-muted",
              )}
            >
              {m === "login" ? "Sign in" : "Register"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3 px-6 py-5">
          {mode === "register" && (
            <Field label="Display name (optional)">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="nickname"
                className="auth-input"
                placeholder="Vega Capital"
              />
            </Field>
          )}
          <Field label="Email">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              className="auth-input"
              placeholder="you@example.com"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="auth-input"
              placeholder="••••••••"
            />
          </Field>

          {error && (
            <p className="font-mono text-[11px] text-down">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="mt-1 bg-gold/20 px-4 py-2.5 font-mono text-xs font-semibold uppercase tracking-[0.2em] text-gold transition-colors hover:bg-gold/30 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="border-t border-line px-6 py-4">
          <button
            type="button"
            onClick={guest}
            disabled={busy}
            className="w-full border border-line px-4 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-dim transition-colors hover:border-line-bright hover:text-muted disabled:opacity-40"
          >
            Continue as guest
          </button>
          <p className="mt-2 text-center font-mono text-[10px] text-faint">
            Guest sessions are temporary and kept only on this device.
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
        {label}
      </span>
      {children}
    </label>
  );
}
