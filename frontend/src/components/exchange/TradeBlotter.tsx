"use client";

import { useFeed } from "@/lib/feed";
import { tickerSymbol } from "@/lib/ticker";
import { fmtPrice, fmtNum, fmtTime } from "@/lib/format";
import { cn } from "@/lib/cn";
import type { TradeExecutedEvent } from "@/lib/types";

export function TradeBlotter() {
  const { events } = useFeed();
  const trades = events.filter(
    (e): e is TradeExecutedEvent => e.type === "trade_executed",
  );

  return (
    <div className="flex h-full flex-col">
      <div className="grid grid-cols-[auto_1fr_auto_auto] gap-2 border-b border-line px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.18em] text-dim">
        <span>Time</span>
        <span>Inst</span>
        <span className="text-right">Shares</span>
        <span className="text-right">Price</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {trades.length === 0 && (
          <div className="p-3 font-mono text-[11px] text-dim">
            No prints yet. Trades stream here live.
          </div>
        )}
        {trades.map((t) => {
          const buy = t.side === "buy";
          return (
            <div
              key={t.event_id}
              className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-2 border-b border-line/40 px-3 py-1.5 font-mono text-[11px]"
            >
              <span className="tabular text-dim">{fmtTime(t.ts)}</span>
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "inline-block h-1.5 w-1.5",
                    buy ? "bg-up" : "bg-down",
                  )}
                />
                <span className="font-semibold text-ink">
                  {tickerSymbol(t.model_id)}
                </span>
                <span className={buy ? "text-up" : "text-down"}>
                  {buy ? "B" : "S"}
                </span>
              </span>
              <span className="tabular text-right text-muted">
                {fmtNum(t.shares, 2)}
              </span>
              <span className="tabular text-right text-ink">
                {fmtPrice(t.price)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
