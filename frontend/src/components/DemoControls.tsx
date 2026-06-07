"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useMarket } from "@/lib/market";
import { cn } from "@/lib/cn";

export function DemoControls() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const { refreshAll } = useMarket();

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setNote(null);
    try {
      await fn();
      setNote(`${label} ok`);
      refreshAll();
    } catch (e) {
      setNote(e instanceof Error ? e.message : `${label} failed`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "border border-line px-2 py-1 font-mono text-[10px] tracking-[0.18em] text-muted transition-colors hover:border-line-bright hover:text-ink",
          open && "border-gold-dim text-gold",
        )}
      >
        SIM
      </button>
      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-full z-50 mt-1 w-52 border border-line bg-raised p-2 shadow-xl shadow-black/60">
            <p className="mb-2 px-1 font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
              Simulation controls
            </p>
            <div className="flex flex-col gap-1">
              <CtrlButton
                label="Seed market"
                busy={busy === "Seed"}
                onClick={() => run("Seed", () => api.seed())}
              />
              <CtrlButton
                label="Start sim"
                busy={busy === "Start"}
                onClick={() =>
                  run("Start", () =>
                    api.simStart({ n_posters: 2, n_investors: 3 }),
                  )
                }
              />
              <CtrlButton
                label="Stop sim"
                busy={busy === "Stop"}
                onClick={() => run("Stop", () => api.simStop())}
              />
            </div>
            {note && (
              <p className="mt-2 px-1 font-mono text-[9px] text-muted">{note}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function CtrlButton({
  label,
  busy,
  onClick,
}: {
  label: string;
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <button
      disabled={busy}
      onClick={onClick}
      className="flex items-center justify-between border border-line px-2 py-1.5 text-left font-mono text-[11px] text-ink transition-colors hover:border-gold-dim hover:text-gold disabled:opacity-50"
    >
      {label}
      {busy && <span className="text-dim">…</span>}
    </button>
  );
}
