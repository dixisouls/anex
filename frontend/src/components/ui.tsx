"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { fmtPct } from "@/lib/format";
import { TIER_CLASS, TIER_LABEL } from "@/lib/ticker";
import type { Tier } from "@/lib/types";

export function Panel({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "border border-line bg-panel/70 backdrop-blur-[1px]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PanelHeader({
  title,
  right,
  className,
}: {
  title: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between border-b border-line px-3 py-2",
        className,
      )}
    >
      <h2 className="font-mono text-[10px] uppercase tracking-[0.22em] text-dim">
        {title}
      </h2>
      {right}
    </div>
  );
}

export function TierBadge({
  tier,
  className,
}: {
  tier: Tier;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center border px-1.5 py-px font-mono text-[9px] font-semibold tracking-[0.18em]",
        TIER_CLASS[tier],
        className,
      )}
    >
      {TIER_LABEL[tier]}
    </span>
  );
}

export function Delta({
  pct,
  className,
  showArrow = true,
}: {
  pct: number;
  className?: string;
  showArrow?: boolean;
}) {
  const up = pct > 0;
  const flat = pct === 0;
  return (
    <span
      className={cn(
        "tabular font-mono",
        flat ? "text-muted" : up ? "text-up" : "text-down",
        className,
      )}
    >
      {showArrow && !flat && (up ? "\u25B2 " : "\u25BC ")}
      {fmtPct(pct)}
    </span>
  );
}

/** Briefly flashes a row/cell background when `value` changes. */
export function useFlash(value: number | undefined) {
  const prev = useRef<number | undefined>(value);
  const [dir, setDir] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (prev.current !== undefined && value !== undefined && value !== prev.current) {
      setDir(value > prev.current ? "up" : "down");
      const id = setTimeout(() => setDir(null), 700);
      prev.current = value;
      return () => clearTimeout(id);
    }
    prev.current = value;
  }, [value]);

  return dir;
}

export function ConnectionDot({
  status,
}: {
  status: "connecting" | "open" | "closed";
}) {
  const color =
    status === "open"
      ? "bg-up"
      : status === "connecting"
        ? "bg-gold"
        : "bg-down";
  const label =
    status === "open" ? "LIVE" : status === "connecting" ? "SYNC" : "OFF";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          color,
          status === "open" && "animate-[pulse-dot_2s_ease-in-out_infinite]",
        )}
      />
      <span className="font-mono text-[10px] tracking-[0.18em] text-muted">
        {label}
      </span>
    </span>
  );
}

export function Stat({
  label,
  value,
  sub,
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
        {label}
      </span>
      <span className="tabular font-mono text-sm text-ink">{value}</span>
      {sub && <span className="text-[10px] text-muted">{sub}</span>}
    </div>
  );
}
