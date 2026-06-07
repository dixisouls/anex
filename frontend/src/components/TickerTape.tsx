"use client";

import { usePathname } from "next/navigation";
import { useMarket, changePct } from "@/lib/market";
import { useUser } from "@/lib/user";
import { tickerSymbol } from "@/lib/ticker";
import { fmtPrice, fmtPct } from "@/lib/format";
import { cn } from "@/lib/cn";

export function TickerTape() {
  const { models, open } = useMarket();
  const { authed } = useUser();
  const pathname = usePathname();

  if (pathname === "/login" || !authed) return null;

  if (models.length === 0) {
    return (
      <div className="flex h-8 items-center border-b border-line bg-panel px-4">
        <span className="font-mono text-[10px] tracking-[0.2em] text-dim">
          AWAITING MARKET DATA…
        </span>
      </div>
    );
  }

  const items = [...models, ...models]; // duplicate for seamless loop

  return (
    <div className="group relative flex h-8 items-center overflow-hidden border-b border-line bg-panel">
      <div className="flex shrink-0 animate-[marquee_70s_linear_infinite] whitespace-nowrap group-hover:[animation-play-state:paused]">
        {items.map((m, i) => {
          const pct = changePct(m.price, open[m.model_id]);
          const up = pct > 0;
          const flat = pct === 0;
          return (
            <span
              key={`${m.model_id}-${i}`}
              className="flex items-center gap-2 border-r border-line/60 px-4 font-mono text-[11px]"
            >
              <span className="font-semibold text-ink">
                {tickerSymbol(m.model_id)}
              </span>
              <span className="tabular text-muted">{fmtPrice(m.price)}</span>
              <span
                className={cn(
                  "tabular",
                  flat ? "text-dim" : up ? "text-up" : "text-down",
                )}
              >
                {!flat && (up ? "\u25B2" : "\u25BC")}
                {fmtPct(pct)}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
