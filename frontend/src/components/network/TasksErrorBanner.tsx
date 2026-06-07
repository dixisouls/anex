"use client";

import { useNetwork } from "@/lib/networkContext";
import { useUser } from "@/lib/user";

export function TasksErrorBanner() {
  const { tasksError } = useNetwork();
  const { continueAsGuest } = useUser();

  if (!tasksError) return null;

  const staleUser = tasksError.status === 404;

  return (
    <div className="shrink-0 border-b border-gold/30 bg-gold/10 px-4 py-2 font-mono text-[11px] text-gold">
      <span>
        Could not load saved task history
        {tasksError.message ? ` (${tasksError.message})` : ""}.
      </span>
      {staleUser ? (
        <span className="ml-1">
          Your session may be stale after a database reset.{" "}
          <button
            type="button"
            onClick={() => void continueAsGuest()}
            className="underline underline-offset-2 hover:text-ink"
          >
            Continue as guest
          </button>{" "}
          to start fresh.
        </span>
      ) : (
        <span className="ml-1 text-muted">
          Showing live feed only until history loads.
        </span>
      )}
    </div>
  );
}
