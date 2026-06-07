"use client";

import { useNetwork } from "@/lib/networkContext";
import { cn } from "@/lib/cn";
import type { Tier } from "@/lib/types";

const TIERS: { id: Tier; label: string }[] = [
  { id: "pro", label: "Pro" },
  { id: "flash", label: "Flash" },
  { id: "lite", label: "Lite" },
];

export function PreferredTierSelect() {
  const { preferredTier, setPreferredTier } = useNetwork();

  return (
    <div className="flex items-center gap-1.5 border border-line bg-panel/60 px-2 py-1">
      <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-dim">
        Tier
      </span>
      {TIERS.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => setPreferredTier(t.id)}
          className={cn(
            "rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors",
            preferredTier === t.id
              ? "bg-gold/15 text-gold"
              : "text-dim hover:text-muted",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
