"use client";

import { cn } from "@/lib/cn";
import type { SubtaskState } from "@/lib/pipeline";

const STAGES = [
  { id: "auctioned", label: "Auctioned" },
  { id: "hired", label: "Hired" },
  { id: "executing", label: "Executing" },
  { id: "judged", label: "Judged" },
] as const;

/** 0–4: none → auctioned → hired → executing → judged */
export function pipelineStageIndex(sub: SubtaskState): number {
  if (sub.skipped) return 0;
  switch (sub.stage) {
    case "posted":
      return 0;
    case "ranked":
      return 1;
    case "hired":
      return 2;
    case "executed":
      return 3;
    case "scored":
      return 4;
    default:
      return 0;
  }
}

export function StepPipeline({ sub }: { sub: SubtaskState }) {
  const idx = pipelineStageIndex(sub);

  return (
    <div className="mt-3">
      {/* Segmented track with breakpoints */}
      <div className="grid grid-cols-4 gap-1">
        {STAGES.map((stage, i) => {
          const done = idx > i + 1 || idx === 4;
          const active = idx === i + 1 && idx < 4;
          const pending = !done && !active;

          return (
            <div key={stage.id} className="relative h-1 overflow-hidden rounded-full bg-line/80">
              {done && (
                <div className="absolute inset-0 z-10 rounded-full bg-up/80" />
              )}
              {active && (
                <div className="absolute inset-0 overflow-hidden rounded-full bg-gold/80">
                  <div className="absolute inset-y-0 w-2/5 animate-[pipeline-stroke_1.1s_linear_infinite] bg-gradient-to-r from-transparent via-white/55 to-transparent" />
                </div>
              )}
              {pending && <div className="absolute inset-0 rounded-full bg-faint/40" />}
            </div>
          );
        })}
      </div>

      <div className="mt-2 grid grid-cols-4 gap-1">
        {STAGES.map((stage, i) => {
          const done = idx > i + 1 || idx === 4;
          const active = idx === i + 1 && idx < 4;
          const pending = !done && !active;

          return (
            <div key={stage.id} className="text-center">
              <span
                className={cn(
                  "font-mono text-[9px] uppercase tracking-[0.1em]",
                  done && "text-up",
                  active && "font-medium text-gold",
                  pending && "text-faint",
                  !done && !active && !pending && "text-faint",
                )}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
