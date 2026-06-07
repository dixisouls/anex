"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface BuyCreditsContextValue {
  open: boolean;
  openBuyCredits: () => void;
  closeBuyCredits: () => void;
}

const BuyCreditsContext = createContext<BuyCreditsContextValue | null>(null);

export function BuyCreditsProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  const openBuyCredits = useCallback(() => setOpen(true), []);
  const closeBuyCredits = useCallback(() => setOpen(false), []);

  const value = useMemo(
    () => ({ open, openBuyCredits, closeBuyCredits }),
    [open, openBuyCredits, closeBuyCredits],
  );

  return (
    <BuyCreditsContext.Provider value={value}>
      {children}
    </BuyCreditsContext.Provider>
  );
}

export function useBuyCredits() {
  const ctx = useContext(BuyCreditsContext);
  if (!ctx) {
    throw new Error("useBuyCredits must be used within BuyCreditsProvider");
  }
  return ctx;
}
