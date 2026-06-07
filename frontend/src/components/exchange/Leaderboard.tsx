"use client";

import { useMarket } from "@/lib/market";
import { useUser } from "@/lib/user";
import { fmtPrice } from "@/lib/format";
import { cn } from "@/lib/cn";

export function Leaderboard() {
  const { leaderboard } = useMarket();
  const { name } = useUser();

  const ranked = leaderboard
    .filter((u) => u.net_worth != null)
    .slice(0, 12);
  const top = ranked[0]?.net_worth ?? 1;

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {ranked.length === 0 && (
          <div className="p-3 font-mono text-[11px] text-dim">
            No traders ranked yet.
          </div>
        )}
        {ranked.map((u, i) => {
          const me = u.name === name && !u.is_sim;
          const pct = top > 0 ? ((u.net_worth ?? 0) / top) * 100 : 0;
          return (
            <div
              key={u.user_id}
              className={cn(
                "relative flex items-center justify-between border-b border-line/40 px-3 py-1.5 font-mono text-[11px]",
                me && "bg-gold/[0.07]",
              )}
            >
              <div
                className="absolute inset-y-0 left-0 bg-gold/[0.05]"
                style={{ width: `${pct}%` }}
              />
              <span className="relative flex items-center gap-2">
                <span className="tabular w-5 text-dim">{i + 1}</span>
                <span className={cn("truncate", me ? "text-gold" : "text-ink")}>
                  {u.name}
                </span>
                {u.is_sim && (
                  <span className="text-[8px] uppercase tracking-[0.15em] text-faint">
                    bot
                  </span>
                )}
              </span>
              <span className="tabular relative text-ink">
                {fmtPrice(u.net_worth ?? 0)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
