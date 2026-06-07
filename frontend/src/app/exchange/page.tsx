"use client";

import { useEffect, useState } from "react";
import { useMarket } from "@/lib/market";
import { Panel, PanelHeader } from "@/components/ui";
import { Watchlist } from "@/components/exchange/Watchlist";
import { StockDetail } from "@/components/exchange/StockDetail";
import { OrderTicket } from "@/components/exchange/OrderTicket";
import { PortfolioRail } from "@/components/exchange/PortfolioRail";
import { TradeBlotter } from "@/components/exchange/TradeBlotter";
import { Leaderboard } from "@/components/exchange/Leaderboard";

export default function ExchangePage() {
  const { models, modelMap, error } = useMarket();
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (!selected && models.length > 0) setSelected(models[0].model_id);
  }, [models, selected]);

  const active = selected ? modelMap[selected] : undefined;

  return (
    <div className="h-full overflow-y-auto xl:overflow-hidden">
      {error && (
        <div className="border-b border-down/40 bg-down/10 px-4 py-2 font-mono text-[11px] text-down">
          Backend unreachable ({error}). Start the API on :8000, then SEED the
          market from the SIM menu.
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 p-3 xl:h-full xl:grid-cols-12">
        {/* Left — watchlist + leaderboard */}
        <section className="flex flex-col gap-3 xl:col-span-3 xl:min-h-0">
          <Panel className="flex h-[460px] flex-col xl:h-auto xl:min-h-0 xl:flex-1">
            <PanelHeader
              title="Watchlist"
              right={
                <span className="font-mono text-[10px] text-dim">
                  {models.length} listed
                </span>
              }
            />
            <div className="min-h-0 flex-1">
              <Watchlist selected={selected} onSelect={setSelected} />
            </div>
          </Panel>
          <Panel className="flex h-64 flex-col xl:h-[34%]">
            <PanelHeader title="Investor leaderboard" />
            <div className="min-h-0 flex-1">
              <Leaderboard />
            </div>
          </Panel>
        </section>

        {/* Center — selected instrument */}
        <section className="xl:col-span-6 xl:min-h-0">
          {active ? (
            <StockDetail model={active} />
          ) : (
            <Panel className="grid h-full min-h-[400px] place-items-center">
              <span className="font-mono text-sm text-dim">
                {models.length ? "Select an instrument" : "Loading market…"}
              </span>
            </Panel>
          )}
        </section>

        {/* Right — ticket + portfolio + blotter */}
        <section className="flex flex-col gap-3 xl:col-span-3 xl:min-h-0">
          {active && (
            <Panel>
              <PanelHeader title="Order ticket" />
              <OrderTicket model={active} />
            </Panel>
          )}
          <Panel>
            <PanelHeader title="Portfolio" />
            <PortfolioRail onSelect={setSelected} />
          </Panel>
          <Panel className="flex h-72 flex-col xl:min-h-0 xl:flex-1">
            <PanelHeader title="Tape · live prints" />
            <div className="min-h-0 flex-1">
              <TradeBlotter />
            </div>
          </Panel>
        </section>
      </div>
    </div>
  );
}
