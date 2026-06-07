"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { useUser } from "@/lib/user";
import { useBuyCredits } from "@/lib/buyCredits";
import { useMarket } from "@/lib/market";
import { fmtPrice } from "@/lib/format";
import { DemoControls } from "./DemoControls";

const TABS = [
  { href: "/exchange", label: "Exchange" },
  { href: "/network", label: "Network" },
];

export function Nav() {
  const pathname = usePathname();
  const { name, email, isGuest, authed, logout } = useUser();
  const { portfolio } = useMarket();
  const { openBuyCredits } = useBuyCredits();

  if (pathname === "/login" || !authed) return null;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-base/90 px-4 backdrop-blur-md">
      <div className="flex items-center gap-7">
        <Link href="/exchange" className="group flex items-baseline gap-2">
          <span className="wordmark text-lg text-gold">ANEX</span>
          <span className="hidden font-mono text-[9px] uppercase tracking-[0.28em] text-dim sm:inline">
            Agent Network Exchange
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {TABS.map((t) => {
            const active = pathname?.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={cn(
                  "border-b-2 px-3 py-1.5 font-mono text-xs uppercase tracking-[0.16em] transition-colors",
                  active
                    ? "border-gold text-ink"
                    : "border-transparent text-dim hover:text-muted",
                )}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden items-center gap-3 border-l border-line pl-4 md:flex">
          <div className="flex flex-col items-end leading-none">
            <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
              Net worth
            </span>
            <span className="tabular font-mono text-sm text-gold">
              {portfolio ? fmtPrice(portfolio.total) : "—"}
            </span>
          </div>
          <div className="flex flex-col items-end leading-none">
            <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
              Cash
            </span>
            <div className="flex items-center gap-1.5">
              <span className="tabular font-mono text-sm text-ink">
                {portfolio ? fmtPrice(portfolio.credits) : "—"}
              </span>
              <button
                type="button"
                onClick={openBuyCredits}
                className="font-mono text-[9px] uppercase tracking-[0.12em] text-gold/80 transition-colors hover:text-gold"
              >
                + Buy
              </button>
            </div>
          </div>
        </div>
        <div className="hidden flex-col items-end border-l border-line pl-4 leading-none lg:flex">
          <span className="max-w-[12rem] truncate font-mono text-xs text-muted">
            {name ?? "…"}
            {isGuest && (
              <span className="ml-1 text-[9px] uppercase tracking-[0.2em] text-dim">
                guest
              </span>
            )}
          </span>
          {email && (
            <span className="max-w-[12rem] truncate font-mono text-[9px] text-dim">
              {email}
            </span>
          )}
        </div>
        <button
          onClick={logout}
          title="Sign out"
          className="border border-line px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-dim transition-colors hover:border-line-bright hover:text-muted"
        >
          Logout
        </button>
        <DemoControls />
      </div>
    </header>
  );
}
