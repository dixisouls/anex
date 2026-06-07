"use client";

import { useEffect, useMemo, useState } from "react";
import { useMarket, changePct, sparkSlopePositive, sparkWindow } from "@/lib/market";
import { tickerSymbol, issuer } from "@/lib/ticker";
import { fmtPrice, fmtCompact, fmtNum } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Sparkline } from "@/components/Sparkline";
import { TierBadge, Delta, useFlash } from "@/components/ui";
import type { ModelStock } from "@/lib/types";

type SortKey = "price" | "change" | "volume" | "symbol" | "spread" | "fair";

export function Watchlist({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { models, history, open, volume, loading, loadHistory } = useMarket();
  const [sort, setSort] = useState<SortKey>("change");
  const [asc, setAsc] = useState(false);

  useEffect(() => {
    for (const m of models) loadHistory(m.model_id);
  }, [models, loadHistory]);

  const rows = useMemo(() => {
    const arr = [...models];
    arr.sort((a, b) => {
      let av: number | string;
      let bv: number | string;
      if (sort === "price") {
        av = a.price;
        bv = b.price;
      } else if (sort === "change") {
        av = changePct(a.price, open[a.model_id] ?? a.session_open);
        bv = changePct(b.price, open[b.model_id] ?? b.session_open);
      } else if (sort === "volume") {
        av = volume[a.model_id] ?? a.volume ?? 0;
        bv = volume[b.model_id] ?? b.volume ?? 0;
      } else if (sort === "spread") {
        av = a.spread_bps ?? 0;
        bv = b.spread_bps ?? 0;
      } else if (sort === "fair") {
        av = a.vs_fair_pct ?? 0;
        bv = b.vs_fair_pct ?? 0;
      } else {
        av = tickerSymbol(a.model_id);
        bv = tickerSymbol(b.model_id);
      }
      if (av < bv) return asc ? -1 : 1;
      if (av > bv) return asc ? 1 : -1;
      return 0;
    });
    return arr;
  }, [models, sort, asc, open, volume]);

  function toggle(key: SortKey) {
    if (sort === key) setAsc((a) => !a);
    else {
      setSort(key);
      setAsc(key === "symbol");
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_auto_auto_auto] items-center gap-x-2 gap-y-1 border-b border-line px-3 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-dim xl:grid-cols-[minmax(0,1fr)_auto_auto]">
        <Th label="Instrument" k="symbol" cur={sort} asc={asc} onClick={toggle} />
        <Th label="Last" k="price" cur={sort} asc={asc} onClick={toggle} align="right" />
        <Th label="Chg" k="change" cur={sort} asc={asc} onClick={toggle} align="right" />
        <Th
          label="Sprd"
          k="spread"
          cur={sort}
          asc={asc}
          onClick={toggle}
          align="right"
          className="xl:hidden"
        />
        <span className="w-[88px] text-right xl:hidden">Trend</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && models.length === 0 && (
          <div className="space-y-px p-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse bg-panel/60" />
            ))}
          </div>
        )}
        {rows.map((m) => {
          const sessionOpen = open[m.model_id] ?? m.session_open;
          const spark = sparkWindow((history[m.model_id] ?? []).map((p) => p.value));
          return (
            <Row
              key={m.model_id}
              model={m}
              pct={changePct(m.price, sessionOpen)}
              spark={spark}
              sparkUp={sparkSlopePositive(spark)}
              vol={volume[m.model_id] ?? m.volume ?? 0}
              selected={selected === m.model_id}
              onSelect={() => onSelect(m.model_id)}
            />
          );
        })}
      </div>
    </div>
  );
}

function Th({
  label,
  k,
  cur,
  asc,
  onClick,
  align = "left",
  className,
}: {
  label: string;
  k: SortKey;
  cur: SortKey;
  asc: boolean;
  onClick: (k: SortKey) => void;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <button
      onClick={() => onClick(k)}
      className={cn(
        "transition-colors hover:text-muted",
        cur === k && "text-gold",
        align === "right" && "text-right",
        className,
      )}
    >
      {label}
      {cur === k && (asc ? " \u2191" : " \u2193")}
    </button>
  );
}

function Row({
  model,
  pct,
  spark,
  sparkUp,
  vol,
  selected,
  onSelect,
}: {
  model: ModelStock;
  pct: number;
  spark: number[];
  sparkUp: boolean;
  vol: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const flash = useFlash(model.price);
  const vsFair = model.vs_fair_pct ?? 0;
  return (
    <button
      onClick={onSelect}
      className={cn(
        "grid w-full grid-cols-[minmax(0,1fr)_auto_auto_auto_auto] items-center gap-x-2 gap-y-1 border-b border-line/50 px-3 py-2 text-left transition-colors xl:grid-cols-[minmax(0,1fr)_auto_auto]",
        selected ? "bg-gold/[0.06]" : "hover:bg-panel/60",
        flash === "up" && "animate-[flash-up_0.7s_ease-out]",
        flash === "down" && "animate-[flash-down_0.7s_ease-out]",
      )}
    >
      <div className="min-w-0 overflow-hidden pr-1">
        <div
          className={cn(
            "truncate font-mono text-sm font-semibold",
            selected ? "text-gold" : "text-ink",
          )}
        >
          {tickerSymbol(model.model_id)}
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-1.5">
          <TierBadge tier={model.tier} />
          <div className="min-w-0 flex-1 truncate font-mono text-[10px] text-dim">
            {model.name} · {issuer(model.provider, model.model_id)}
            {model.fundamental != null && (
              <span
                className={cn(
                  "ml-1",
                  vsFair > 2 ? "text-down" : vsFair < -2 ? "text-up" : "text-dim",
                )}
              >
                · {fmtNum(vsFair, 1)}% vs fair
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="whitespace-nowrap tabular-nums font-mono text-sm text-ink">
          {fmtPrice(model.price)}
        </div>
        <div className="whitespace-nowrap tabular-nums font-mono text-[9px] text-dim">
          V {fmtCompact(vol)}
        </div>
      </div>
      <div className="w-14 shrink-0 text-right">
        <Delta pct={pct} className="text-xs" />
      </div>
      <div className="tabular-nums w-10 shrink-0 text-right font-mono text-[9px] text-dim xl:hidden">
        {model.spread_bps != null ? `${fmtNum(model.spread_bps, 0)}` : "—"}
      </div>
      <div className="flex w-[88px] shrink-0 justify-end xl:hidden">
        <Sparkline data={spark} positive={sparkUp} />
      </div>
    </button>
  );
}
