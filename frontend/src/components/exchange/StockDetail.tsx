"use client";

import { useEffect, useState } from "react";
import { useMarket, changePct } from "@/lib/market";
import { tickerSymbol, issuer } from "@/lib/ticker";
import { fmtPrice, fmtCompact, fmtNum, fmtSignedPrice, fmtTime } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Delta, TierBadge, Panel, PanelHeader, useFlash } from "@/components/ui";
import { ChartModeToggle, PriceChart, type ChartMode } from "./PriceChart";
import type { ModelStock } from "@/lib/types";

export function StockDetail({ model }: { model: ModelStock }) {
  const { open, volume, earnings: earningsMap, loadEarnings, loadHistory } = useMarket();
  const flash = useFlash(model.price);
  const [chartMode, setChartMode] = useState<ChartMode>("line");

  const openPrice = open[model.model_id] ?? model.session_open;
  const pct = changePct(model.price, openPrice);
  const abs = openPrice != null ? model.price - openPrice : 0;
  const k = model.shares * model.credits;

  useEffect(() => {
    loadEarnings(model.model_id);
    loadHistory(model.model_id);
  }, [model.model_id, loadEarnings, loadHistory]);

  const earnings = (earningsMap[model.model_id] ?? []).slice(0, 8);

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-2xl font-bold tracking-tight text-ink">
              {tickerSymbol(model.model_id)}
            </h1>
            <TierBadge tier={model.tier} />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-dim">
              {issuer(model.provider, model.model_id)}
            </span>
          </div>
          <p className="mt-0.5 font-mono text-xs text-muted">{model.name}</p>
        </div>
        <div className="text-right">
          <div
            className={cn(
              "tabular px-1 font-mono text-3xl font-semibold leading-none",
              flash === "up" && "animate-[flash-up_0.7s_ease-out]",
              flash === "down" && "animate-[flash-down_0.7s_ease-out]",
            )}
          >
            {fmtPrice(model.price)}
          </div>
          <div className="mt-1 flex items-center justify-end gap-2 text-sm">
            <span
              className={cn(
                "tabular font-mono",
                abs >= 0 ? "text-up" : "text-down",
              )}
            >
              {fmtSignedPrice(abs)}
            </span>
            <Delta pct={pct} className="text-sm" />
            <span className="font-mono text-[10px] text-dim">session</span>
          </div>
          <div className="mt-2 grid grid-cols-4 gap-2 font-mono text-[10px]">
            <div>
              <span className="text-dim">BID </span>
              <span className="text-up">{fmtPrice(model.bid ?? model.price)}</span>
            </div>
            <div>
              <span className="text-dim">ASK </span>
              <span className="text-down">{fmtPrice(model.ask ?? model.price)}</span>
            </div>
            <div>
              <span className="text-dim">FAIR </span>
              <span>{fmtPrice(model.fundamental ?? model.price)}</span>
            </div>
            <div>
              <span className="text-dim">HI/LO </span>
              <span>
                {fmtPrice(model.day_high ?? model.price)}/
                {fmtPrice(model.day_low ?? model.price)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <Panel className="min-h-[260px] flex-1">
        <PanelHeader
          title="Price"
          right={
            <div className="flex items-center gap-2">
              <ChartModeToggle mode={chartMode} onChange={setChartMode} />
              <span className="font-mono text-[10px] text-dim">
                AMM · constant-product
              </span>
            </div>
          }
        />
        <div className="h-[calc(100%-33px)] min-h-[220px] p-1">
          <PriceChart
            modelId={model.model_id}
            mode={chartMode}
            onModeChange={setChartMode}
            showToggle={false}
          />
        </div>
      </Panel>

      {/* AMM pool + earnings */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Liquidity pool" />
          <div className="grid grid-cols-2 gap-px bg-line">
            <PoolCell label="Shares (S)" value={fmtNum(model.shares, 1)} />
            <PoolCell label="Credits (C)" value={fmtPrice(model.credits)} />
            <PoolCell label="Invariant k" value={fmtCompact(k)} />
            <PoolCell
              label="Session vol"
              value={`${fmtCompact(volume[model.model_id] ?? 0)} sh`}
            />
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Fundamentals · earnings" />
          <div className="max-h-40 overflow-y-auto">
            {earnings.length === 0 && (
              <div className="p-3 font-mono text-[11px] text-dim">
                Earnings post when this model wins judged work.
              </div>
            )}
            {earnings.map((e, i) => {
              const pos = e.amount >= 0;
              return (
                <div
                  key={e.event_id ?? `${e.ts}-${e.agent_id}-${i}`}
                  className="flex items-center justify-between border-b border-line/40 px-3 py-1.5 font-mono text-[11px]"
                >
                  <span className="tabular text-dim">{fmtTime(e.ts)}</span>
                  <span className="truncate px-2 text-muted">{e.agent_id}</span>
                  <span className="tabular text-dim">
                    {e.judge_score != null ? `J${e.judge_score.toFixed(2)}` : "—"}
                  </span>
                  <span className={cn("tabular w-16 text-right", pos ? "text-up" : "text-down")}>
                    {fmtSignedPrice(e.amount)}
                  </span>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function PoolCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-panel p-2.5">
      <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-dim">
        {label}
      </div>
      <div className="tabular font-mono text-sm text-ink">{value}</div>
    </div>
  );
}
