"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useUser } from "@/lib/user";

const PUBLIC_PATHS = new Set(["/login"]);

export function AuthGate({ children }: { children: ReactNode }) {
  const { ready, authed } = useUser();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.has(pathname ?? "");

  useEffect(() => {
    if (!ready) return;
    if (!authed && !isPublic) router.replace("/login");
    if (authed && isPublic) router.replace("/exchange");
  }, [ready, authed, isPublic, router]);

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center">
        <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-dim">
          Loading…
        </span>
      </div>
    );
  }

  // Avoid flashing protected content during the redirect tick.
  if (!authed && !isPublic) return null;
  if (authed && isPublic) return null;

  return <>{children}</>;
}
