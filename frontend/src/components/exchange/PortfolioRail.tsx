"use client";

import { useMarket, changePct } from "@/lib/market";
import { tickerSymbol } from "@/lib/ticker";
import { fmtPrice, fmtNum } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Delta } from "@/components/ui";

export function PortfolioRail({
  onSelect,
}: {
  onSelect: (id: string) => void;
}) {
  const { portfolio, modelMap, open } = useMarket();

  if (!portfolio) {
    return (
      <div className="p-3 font-mono text-[11px] text-dim">
        Opening trading account…
      </div>
    );
  }

  const holdings = portfolio.holdings.filter((h) => h.shares > 0.0001);
  const investedPct =
    portfolio.total > 0 ? (portfolio.holdings_value / portfolio.total) * 100 : 0;

  return (
    <div className="flex flex-col">
      <div className="grid grid-cols-2 gap-px bg-line">
        <div className="bg-panel p-3">
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
            Net worth
          </div>
          <div className="tabular font-mono text-lg text-gold">
            {fmtPrice(portfolio.total)}
          </div>
        </div>
        <div className="bg-panel p-3">
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
            Cash
          </div>
          <div className="tabular font-mono text-lg text-ink">
            {fmtPrice(portfolio.credits)}
          </div>
        </div>
      </div>

      <div className="h-1 w-full bg-line">
        <div
          className="h-full bg-gold/60 transition-all"
          style={{ width: `${Math.min(100, investedPct)}%` }}
        />
      </div>

      <div className="px-3 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-dim">
        Holdings · {fmtPrice(portfolio.holdings_value)} invested
      </div>

      <div className="max-h-64 overflow-y-auto">
        {holdings.length === 0 && (
          <div className="px-3 pb-3 font-mono text-[11px] text-dim">
            No positions yet. Buy a model-stock to begin.
          </div>
        )}
        {holdings.map((h) => {
          const m = modelMap[h.model_id];
          const pct = m
            ? changePct(m.price, open[h.model_id] ?? m.session_open)
            : 0;
          return (
            <button
              key={h.model_id}
              onClick={() => onSelect(h.model_id)}
              className="flex w-full items-center justify-between border-t border-line/50 px-3 py-2 text-left transition-colors hover:bg-panel/60"
            >
              <div>
                <div className="font-mono text-xs font-semibold text-ink">
                  {tickerSymbol(h.model_id)}
                </div>
                <div className="tabular font-mono text-[10px] text-dim">
                  {fmtNum(h.shares, 2)} sh
                </div>
              </div>
              <div className="text-right">
                <div className="tabular font-mono text-xs text-ink">
                  {fmtPrice(h.value)}
                </div>
                <Delta pct={pct} className="text-[10px]" showArrow={false} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
