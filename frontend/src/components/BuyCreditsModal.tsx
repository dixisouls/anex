"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBuyCredits } from "@/lib/buyCredits";
import { useMarket } from "@/lib/market";
import { useUser } from "@/lib/user";
import { fmtPrice } from "@/lib/format";
import { cn } from "@/lib/cn";

const MIN = 20;
const MAX = 1000;
const STEP = 10;

export function BuyCreditsModal() {
  const { open, closeBuyCredits } = useBuyCredits();
  const { userId } = useUser();
  const { refreshAll } = useMarket();
  const [amount, setAmount] = useState(100);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function confirm() {
    if (!userId || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.buyCredits(userId, amount);
      refreshAll();
      closeBuyCredits();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Purchase failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-base/80 backdrop-blur-sm"
        onClick={closeBuyCredits}
      />
      <div className="relative w-full max-w-sm rounded-2xl border border-line bg-raised p-5 shadow-xl">
        <h2 className="text-sm font-semibold text-ink">Buy credits</h2>
        <p className="mt-1 text-[12px] text-dim">
          Demo purchase — no payment required.
        </p>

        <div className="mt-5">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-dim">
              Amount
            </span>
            <span className="tabular font-mono text-lg text-gold">
              {fmtPrice(amount)}
            </span>
          </div>
          <input
            type="range"
            min={MIN}
            max={MAX}
            step={STEP}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            className="mt-3 w-full accent-gold"
          />
          <div className="mt-1 flex justify-between font-mono text-[9px] text-faint">
            <span>{fmtPrice(MIN)}</span>
            <span>{fmtPrice(MAX)}</span>
          </div>
        </div>

        {error && (
          <p className="mt-3 font-mono text-[11px] text-down">{error}</p>
        )}

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={closeBuyCredits}
            className="flex-1 rounded-lg border border-line px-3 py-2 font-mono text-[11px] uppercase tracking-[0.12em] text-dim transition-colors hover:border-line-bright hover:text-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={busy || !userId}
            className={cn(
              "flex-1 rounded-lg px-3 py-2 font-mono text-[11px] uppercase tracking-[0.12em] transition-colors",
              busy || !userId
                ? "bg-line text-dim"
                : "bg-gold text-base hover:bg-gold/90",
            )}
          >
            {busy ? "Adding…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
