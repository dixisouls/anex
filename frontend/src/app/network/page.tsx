"use client";

import { useAgents } from "@/lib/useAgents";
import { NetworkProvider } from "@/lib/networkContext";
import { TaskComposer } from "@/components/network/TaskComposer";
import { TaskThread } from "@/components/network/TaskThread";
import { NetworkHeader } from "@/components/network/NetworkHeader";
import { AgentNetworkDrawer } from "@/components/network/AgentNetworkDrawer";

export default function NetworkPage() {
  const { agents, list, loading, error } = useAgents();

  return (
    <NetworkProvider>
      <div className="flex h-full flex-col overflow-hidden">
        {error && (
          <div className="shrink-0 border-b border-down/40 bg-down/10 px-4 py-2 font-mono text-[11px] text-down">
            Backend unreachable ({error}). Start the API on :8000 and seed the
            market.
          </div>
        )}
        <NetworkHeader agentCount={list.length} />
        <TaskThread agents={agents} />
        <TaskComposer />
        <AgentNetworkDrawer list={list} loading={loading} />
      </div>
    </NetworkProvider>
  );
}
