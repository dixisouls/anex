"use client";

import { BrokerModelSelect } from "./BrokerModelSelect";
import { useNetwork } from "@/lib/networkContext";
import { cn } from "@/lib/cn";

export function NetworkHeader({ agentCount }: { agentCount: number }) {
  const { agentsOpen, setAgentsOpen } = useNetwork();

  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-line/60 bg-panel/30 px-4 py-3 backdrop-blur-md">
      <div className="min-w-0 flex-1">
        <h1 className="text-sm font-semibold text-ink">Network</h1>
        <p className="mt-0.5 text-[11px] text-dim">
          Agent workflow
        </p>
      </div>
      <BrokerModelSelect />
      <button
        type="button"
        onClick={() => setAgentsOpen(!agentsOpen)}
        className={cn(
          "border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] transition-colors",
          agentsOpen
            ? "border-gold-dim bg-gold/10 text-gold"
            : "border-line text-dim hover:border-line-bright hover:text-muted",
        )}
      >
        Agents · {agentCount}
      </button>
    </header>
  );
}
