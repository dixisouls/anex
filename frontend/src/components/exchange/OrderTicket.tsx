"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/lib/user";
import { useMarket } from "@/lib/market";
import { cn } from "@/lib/cn";
import { fmtPrice, fmtNum } from "@/lib/format";
import { tickerSymbol } from "@/lib/ticker";
import type { ModelStock, Side } from "@/lib/types";

const MIN_POOL = 1.0;

function previewBuy(S: number, C: number, dc: number) {
  const k = S * C;
  const C2 = C + dc;
  const S2 = Math.max(MIN_POOL, k / C2);
  const sharesOut = S - S2;
  return { out: sharesOut, newPrice: C2 / S2, avg: dc / sharesOut };
}

function previewSell(S: number, C: number, ds: number) {
  const k = S * C;
  const S2 = S + ds;
  const C2 = Math.max(MIN_POOL, k / S2);
  const creditsOut = C - C2;
  return { out: creditsOut, newPrice: C2 / S2, avg: creditsOut / ds };
}

export function OrderTicket({ model }: { model: ModelStock }) {
  const { userId } = useUser();
  const { portfolio, refreshAll } = useMarket();
  const [side, setSide] = useState<Side>("buy");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const cash = portfolio?.credits ?? 0;
  const held =
    portfolio?.holdings.find((h) => h.model_id === model.model_id)?.shares ?? 0;

  const amt = parseFloat(amount);
  const valid = !Number.isNaN(amt) && amt > 0;

  const preview = useMemo(() => {
    if (!valid) return null;
    return side === "buy"
      ? previewBuy(model.shares, model.credits, amt)
      : previewSell(model.shares, model.credits, amt);
  }, [valid, side, amt, model.shares, model.credits]);

  const overLimit =
    valid && (side === "buy" ? amt > cash : amt > held);

  async function submit() {
    if (!userId || !valid || overLimit) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.trade(userId, model.model_id, side, amt);
      setMsg({
        ok: true,
        text:
          side === "buy"
            ? `Bought ${fmtNum(r.shares, 2)} @ ${fmtPrice(r.price)}`
            : `Sold for ${fmtPrice(r.credits)} @ ${fmtPrice(r.price)}`,
      });
      setAmount("");
      refreshAll();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Trade failed" });
    } finally {
      setBusy(false);
    }
  }

  // Floor (never round up) so sell amounts can't exceed the actual holding,
  // which would trip the client guard and the backend's strict shares check.
  const floor2 = (v: number) => Math.floor(v * 100) / 100;
  const floor6 = (v: number) => Math.floor(v * 1e6) / 1e6;
  const quickValues =
    side === "buy"
      ? [25, 100, 250]
      : [floor2(held * 0.25), floor2(held * 0.5), floor6(held)];

  return (
    <div className="flex flex-col">
      <div className="grid grid-cols-2 gap-px bg-line">
        {(["buy", "sell"] as Side[]).map((s) => (
          <button
            key={s}
            onClick={() => {
              setSide(s);
              setMsg(null);
            }}
            className={cn(
              "py-2 font-mono text-xs uppercase tracking-[0.2em] transition-colors",
              side === s
                ? s === "buy"
                  ? "bg-up/15 text-up"
                  : "bg-down/15 text-down"
                : "bg-panel text-dim hover:text-muted",
            )}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 p-3">
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
            {side === "buy" ? "Credits to spend" : "Shares to sell"}
          </span>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="tabular border border-line bg-base px-2 py-2 font-mono text-sm text-ink outline-none focus:border-gold-dim"
          />
        </label>

        <div className="flex gap-1">
          {quickValues.map((v, i) => (
            <button
              key={i}
              disabled={side === "sell" && held <= 0}
              onClick={() => setAmount(v > 0 ? String(v) : "")}
              className="flex-1 border border-line py-1 font-mono text-[10px] text-muted transition-colors hover:border-line-bright hover:text-ink disabled:opacity-40"
            >
              {side === "buy"
                ? v
                : i === 2
                  ? "MAX"
                  : `${(i + 1) * 25}%`}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-1.5 border-y border-line py-2 font-mono text-[11px]">
          <Row label="Available">
            {side === "buy"
              ? `${fmtPrice(cash)} cr`
              : `${fmtNum(held, 2)} sh`}
          </Row>
          <Row label="Mark price">{fmtPrice(model.price)}</Row>
          {preview && (
            <>
              <Row label={side === "buy" ? "Est. shares" : "Est. credits"}>
                <span className={side === "buy" ? "text-up" : "text-down"}>
                  {fmtNum(preview.out, 2)}
                </span>
              </Row>
              <Row label="Avg fill">{fmtPrice(preview.avg)}</Row>
              <Row label="New mark">{fmtPrice(preview.newPrice)}</Row>
            </>
          )}
        </div>

        <button
          disabled={!valid || overLimit || busy || !userId}
          onClick={submit}
          className={cn(
            "py-2.5 font-mono text-xs font-semibold uppercase tracking-[0.2em] transition-colors disabled:cursor-not-allowed disabled:opacity-40",
            side === "buy"
              ? "bg-up/20 text-up hover:bg-up/30"
              : "bg-down/20 text-down hover:bg-down/30",
          )}
        >
          {busy
            ? "Routing…"
            : overLimit
              ? "Insufficient"
              : `${side} ${tickerSymbol(model.model_id)}`}
        </button>

        {msg && (
          <p
            className={cn(
              "font-mono text-[10px]",
              msg.ok ? "text-up" : "text-down",
            )}
          >
            {msg.text}
          </p>
        )}
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-dim">{label}</span>
      <span className="tabular text-ink">{children}</span>
    </div>
  );
}
