"use client";

import { useMemo, useState } from "react";
import { useMarket, changePct } from "@/lib/market";
import { tickerSymbol, issuer } from "@/lib/ticker";
import { fmtPrice, fmtCompact } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Sparkline } from "@/components/Sparkline";
import { TierBadge, Delta, useFlash } from "@/components/ui";
import type { ModelStock } from "@/lib/types";

type SortKey = "price" | "change" | "volume" | "symbol";

export function Watchlist({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { models, history, open, volume, loading } = useMarket();
  const [sort, setSort] = useState<SortKey>("change");
  const [asc, setAsc] = useState(false);

  const rows = useMemo(() => {
    const arr = [...models];
    arr.sort((a, b) => {
      let av: number | string;
      let bv: number | string;
      if (sort === "price") {
        av = a.price;
        bv = b.price;
      } else if (sort === "change") {
        av = changePct(a.price, open[a.model_id]);
        bv = changePct(b.price, open[b.model_id]);
      } else if (sort === "volume") {
        av = volume[a.model_id] ?? 0;
        bv = volume[b.model_id] ?? 0;
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
      <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 border-b border-line px-3 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-dim">
        <Th label="Instrument" k="symbol" cur={sort} asc={asc} onClick={toggle} />
        <Th label="Last" k="price" cur={sort} asc={asc} onClick={toggle} align="right" />
        <Th label="Chg" k="change" cur={sort} asc={asc} onClick={toggle} align="right" />
        <span className="w-[88px] text-right">Trend</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && models.length === 0 && (
          <div className="space-y-px p-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse bg-panel/60" />
            ))}
          </div>
        )}
        {rows.map((m) => (
          <Row
            key={m.model_id}
            model={m}
            pct={changePct(m.price, open[m.model_id])}
            spark={(history[m.model_id] ?? []).map((p) => p.value)}
            vol={volume[m.model_id] ?? 0}
            selected={selected === m.model_id}
            onSelect={() => onSelect(m.model_id)}
          />
        ))}
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
}: {
  label: string;
  k: SortKey;
  cur: SortKey;
  asc: boolean;
  onClick: (k: SortKey) => void;
  align?: "left" | "right";
}) {
  return (
    <button
      onClick={() => onClick(k)}
      className={cn(
        "transition-colors hover:text-muted",
        cur === k && "text-gold",
        align === "right" && "text-right",
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
  vol,
  selected,
  onSelect,
}: {
  model: ModelStock;
  pct: number;
  spark: number[];
  vol: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const flash = useFlash(model.price);
  return (
    <button
      onClick={onSelect}
      className={cn(
        "grid w-full grid-cols-[1fr_auto_auto_auto] items-center gap-3 border-b border-line/50 px-3 py-2 text-left transition-colors",
        selected ? "bg-gold/[0.06]" : "hover:bg-panel/60",
        flash === "up" && "animate-[flash-up_0.7s_ease-out]",
        flash === "down" && "animate-[flash-down_0.7s_ease-out]",
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "font-mono text-sm font-semibold",
              selected ? "text-gold" : "text-ink",
            )}
          >
            {tickerSymbol(model.model_id)}
          </span>
          <TierBadge tier={model.tier} />
        </div>
        <div className="truncate font-mono text-[10px] text-dim">
          {model.name} · {issuer(model.provider, model.model_id)}
        </div>
      </div>
      <div className="text-right">
        <div className="tabular font-mono text-sm text-ink">
          {fmtPrice(model.price)}
        </div>
        <div className="tabular font-mono text-[9px] text-dim">
          V {fmtCompact(vol)}
        </div>
      </div>
      <div className="w-16 text-right">
        <Delta pct={pct} className="text-xs" />
      </div>
      <div className="flex w-[88px] justify-end">
        <Sparkline data={spark} positive={pct >= 0} />
      </div>
    </button>
  );
}
