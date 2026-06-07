"use client";

import { motion } from "motion/react";
import { Markdown } from "@/components/Markdown";

/** Clean assistant-style message — output only, no stats. */
export function AgentChatMessage({ content }: { content: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
      className="flex justify-start pr-8"
    >
      <div className="max-w-[92%] rounded-2xl rounded-tl-md border border-line/40 bg-panel/80 px-4 py-3.5 shadow-sm">
        <div className="text-[14px] leading-relaxed text-ink [&_.md]:text-[14px]">
          <Markdown>{content}</Markdown>
        </div>
      </div>
    </motion.div>
  );
}
