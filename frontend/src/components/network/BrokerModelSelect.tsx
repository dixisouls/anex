"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useNetwork } from "@/lib/networkContext";
import { DEFAULT_BROKER_MODEL } from "@/lib/networkPrefs";
import { tickerSymbol } from "@/lib/ticker";
import { cn } from "@/lib/cn";
import type { ModelStock } from "@/lib/types";

export function BrokerModelSelect() {
  const { brokerModel, setBrokerModel } = useNetwork();
  const [models, setModels] = useState<ModelStock[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .getModels()
      .then((m) => {
        if (alive) setModels(m);
      })
      .catch(() => {
        /* offline */
      });
    return () => {
      alive = false;
    };
  }, []);

  const selected =
    models.find((m) => m.model_id === brokerModel) ??
    models.find((m) => m.model_id === DEFAULT_BROKER_MODEL);

  const label = selected?.name ?? "Gemini 3.5 Flash";

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 border border-line bg-panel/60 px-2.5 py-1.5 font-mono text-[10px] text-muted transition-colors hover:border-line-bright hover:text-ink"
      >
        <span className="uppercase tracking-[0.14em] text-dim">Broker</span>
        <span className="text-ink">{label}</span>
        <span className="text-dim">▾</span>
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close broker model menu"
            className="fixed inset-0 z-30"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-full z-40 mt-1 max-h-64 w-64 overflow-y-auto border border-line bg-raised shadow-lg">
            <div className="border-b border-line px-2 py-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-dim">
              Decompose & rerank
            </div>
            {models.length === 0 ? (
              <div className="px-3 py-2 font-mono text-[10px] text-dim">
                Loading models…
              </div>
            ) : (
              models.map((m) => (
                <button
                  key={m.model_id}
                  type="button"
                  onClick={() => {
                    setBrokerModel(m.model_id);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full flex-col gap-0.5 border-b border-line/40 px-3 py-2 text-left font-mono text-[10px] transition-colors hover:bg-panel",
                    m.model_id === brokerModel && "bg-gold/10 text-gold",
                  )}
                >
                  <span className="text-ink">
                    {tickerSymbol(m.model_id)} · {m.name}
                  </span>
                  <span className="uppercase tracking-[0.12em] text-dim">
                    {m.tier} · {m.model_id}
                  </span>
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
