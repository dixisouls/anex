"use client";

import { useEffect, useMemo, useState } from "react";
import { useMarket, changePct } from "@/lib/market";
import { useFeed } from "@/lib/feed";
import { tickerSymbol, issuer } from "@/lib/ticker";
import {
  fmtPrice,
  fmtNum,
  fmtPct,
  fmtSignedPrice,
  fmtTime,
} from "@/lib/format";
import { cn } from "@/lib/cn";
import { PriceChart } from "./PriceChart";
import type { TradeExecutedEvent } from "@/lib/types";

function deltaClass(n: number) {
  if (n > 0) return "text-up";
  if (n < 0) return "text-down";
  return "text-muted";
}

export function BloombergTerminal({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { models, modelMap, open, volume, loadHistory } = useMarket();
  const { events } = useFeed();
  const [query, setQuery] = useState("");
  const [filterBySelected, setFilterBySelected] = useState(false);

  const active = selected ? modelMap[selected] : undefined;

  useEffect(() => {
    for (const m of models) loadHistory(m.model_id);
    if (selected) loadHistory(selected);
  }, [models, selected, loadHistory]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return models;
    return models.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        m.model_id.toLowerCase().includes(q) ||
        tickerSymbol(m.model_id).toLowerCase().includes(q),
    );
  }, [models, query]);

  const trades = useMemo(
    () =>
      events.filter(
        (e): e is TradeExecutedEvent => e.type === "trade_executed",
      ),
    [events],
  );

  const shownTrades = useMemo(
    () =>
      filterBySelected && selected
        ? trades.filter((t) => t.model_id === selected)
        : trades,
    [trades, filterBySelected, selected],
  );

  const activeOpen = active
    ? open[active.model_id] ?? active.session_open
    : undefined;
  const activePct = active ? changePct(active.price, activeOpen) : 0;
  const activeChange =
    active && activeOpen != null ? active.price - activeOpen : 0;

  return (
    <div className="flex h-full min-h-[600px] flex-col border border-amber-dim/50 bg-black font-mono text-amber">
      {/* Command bar */}
      <div className="flex items-center justify-between gap-3 border-b border-amber-dim/50 bg-amber/10 px-3 py-1.5">
        <div className="flex items-center gap-2">
          <span className="bg-amber px-1.5 py-px text-[10px] font-bold tracking-[0.2em] text-black">
            ANEX
          </span>
          <span className="text-[11px] tracking-[0.2em] text-amber/90">
            MODEL EQUITY TERMINAL
          </span>
          <span className="text-[10px] text-amber/50">{"<GO>"}</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-amber/60">
          <span>{models.length} SECURITIES</span>
          <span className="hidden sm:inline">
            {new Date().toLocaleDateString("en-US")}
          </span>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[320px_1fr]">
        {/* Left — securities monitor */}
        <div className="flex min-h-0 flex-col border-b border-amber-dim/40 lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2 border-b border-amber-dim/40 px-2 py-1.5">
            <span className="text-[10px] text-amber/50">SRCH</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="filter securities…"
              className="w-full bg-transparent text-[11px] text-amber placeholder:text-amber/30 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-[1fr_auto_auto] gap-2 border-b border-amber-dim/40 px-2 py-1 text-[9px] uppercase tracking-[0.14em] text-amber/50">
            <span>Security</span>
            <span className="text-right">Last</span>
            <span className="text-right">Chg%</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {filtered.map((m) => {
              const pct = changePct(m.price, open[m.model_id] ?? m.session_open);
              const sel = m.model_id === selected;
              return (
                <button
                  key={m.model_id}
                  type="button"
                  onClick={() => onSelect(m.model_id)}
                  className={cn(
                    "grid w-full grid-cols-[1fr_auto_auto] items-center gap-2 border-b border-amber-dim/20 px-2 py-1 text-left transition-colors hover:bg-amber/10",
                    sel && "bg-amber/15",
                  )}
                >
                  <span className="flex min-w-0 flex-col leading-tight">
                    <span className="truncate text-[11px] font-semibold text-amber">
                      {tickerSymbol(m.model_id)}
                    </span>
                    <span className="truncate text-[9px] text-amber/40">
                      {issuer(m.provider, m.model_id)}
                    </span>
                  </span>
                  <span className="tabular text-right text-[11px] text-amber/90">
                    {fmtPrice(m.price)}
                  </span>
                  <span
                    className={cn(
                      "tabular w-12 text-right text-[11px]",
                      deltaClass(pct),
                    )}
                  >
                    {fmtPct(pct)}
                  </span>
                </button>
              );
            })}
            {filtered.length === 0 && (
              <div className="px-2 py-3 text-[11px] text-amber/40">
                No securities match “{query}”.
              </div>
            )}
          </div>
        </div>

        {/* Right — quote + chart + trades */}
        <div className="flex min-h-0 flex-col">
          {/* Quote header */}
          <div className="border-b border-amber-dim/40 px-3 py-2">
            {active ? (
              <>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="text-lg font-bold tracking-[0.12em] text-amber">
                    {tickerSymbol(active.model_id)}
                  </span>
                  <span className="text-[11px] text-amber/60">
                    {active.name}
                  </span>
                  <span className="text-[10px] uppercase tracking-[0.16em] text-amber/40">
                    {issuer(active.provider, active.model_id)} · {active.tier}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <span className="tabular text-2xl font-semibold text-amber">
                    {fmtPrice(active.price)}
                  </span>
                  <span
                    className={cn(
                      "tabular text-sm",
                      deltaClass(activeChange),
                    )}
                  >
                    {fmtSignedPrice(activeChange)} ({fmtPct(activePct)})
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-[10px] sm:grid-cols-4">
                  <Field label="BID" value={fmtPrice(active.bid ?? active.price)} />
                  <Field label="ASK" value={fmtPrice(active.ask ?? active.price)} />
                  <Field label="FAIR" value={fmtPrice(active.fundamental ?? active.price)} />
                  <Field label="OPEN" value={fmtPrice(activeOpen)} />
                  <Field label="HI/LO" value={`${fmtPrice(active.day_high ?? active.price)}/${fmtPrice(active.day_low ?? active.price)}`} />
                  <Field label="SPRD" value={`${fmtNum(active.spread_bps ?? 0, 0)} bps`} />
                  <Field label="VOL" value={fmtNum(volume[active.model_id] ?? active.volume ?? 0, 0)} />
                  <Field label="EXEC" value={active.executable ? "YES" : "NO"} />
                </div>
              </>
            ) : (
              <span className="text-[11px] text-amber/50">
                Select a security from the monitor.
              </span>
            )}
          </div>

          {/* Chart */}
          <div className="h-48 shrink-0 border-b border-amber-dim/40 px-1 py-1 lg:h-56">
            {active ? (
              <PriceChart modelId={active.model_id} />
            ) : (
              <div className="grid h-full place-items-center text-[11px] text-amber/40">
                No chart
              </div>
            )}
          </div>

          {/* Trades blotter */}
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex items-center justify-between border-b border-amber-dim/40 px-3 py-1.5">
              <span className="text-[10px] uppercase tracking-[0.18em] text-amber/60">
                Time &amp; sales {filterBySelected && active && `· ${tickerSymbol(active.model_id)}`}
              </span>
              <button
                type="button"
                onClick={() => setFilterBySelected((v) => !v)}
                disabled={!selected}
                className={cn(
                  "border px-2 py-px text-[9px] uppercase tracking-[0.16em] transition-colors disabled:opacity-30",
                  filterBySelected
                    ? "border-amber bg-amber text-black"
                    : "border-amber-dim/60 text-amber/70 hover:bg-amber/10",
                )}
              >
                {filterBySelected ? "Filtered" : "Filter by stock"}
              </button>
            </div>
            <div className="grid grid-cols-[auto_1fr_auto_auto] gap-2 border-b border-amber-dim/30 px-3 py-1 text-[9px] uppercase tracking-[0.14em] text-amber/50">
              <span>Time</span>
              <span>Inst</span>
              <span className="text-right">Shares</span>
              <span className="text-right">Price</span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {shownTrades.length === 0 && (
                <div className="px-3 py-3 text-[11px] text-amber/40">
                  No prints yet. Trades stream here live.
                </div>
              )}
              {shownTrades.map((t) => {
                const buy = t.side === "buy";
                return (
                  <button
                    key={t.event_id}
                    type="button"
                    onClick={() => onSelect(t.model_id)}
                    className="grid w-full grid-cols-[auto_1fr_auto_auto] items-center gap-2 border-b border-amber-dim/15 px-3 py-1 text-left text-[11px] transition-colors hover:bg-amber/10"
                  >
                    <span className="tabular text-amber/50">
                      {fmtTime(t.ts)}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="font-semibold text-amber">
                        {tickerSymbol(t.model_id)}
                      </span>
                      <span className={buy ? "text-up" : "text-down"}>
                        {buy ? "B" : "S"}
                      </span>
                    </span>
                    <span className="tabular text-right text-amber/70">
                      {fmtNum(t.shares, 2)}
                    </span>
                    <span className="tabular text-right text-amber/90">
                      {fmtPrice(t.price)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 sm:flex-col sm:items-start sm:justify-start sm:gap-0">
      <span className="text-[9px] uppercase tracking-[0.16em] text-amber/40">
        {label}
      </span>
      <span className="tabular text-amber/90">{value}</span>
    </div>
  );
}
