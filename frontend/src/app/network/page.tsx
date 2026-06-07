"use client";

import { useAgents } from "@/lib/useAgents";
import { Panel, PanelHeader } from "@/components/ui";
import { TaskComposer } from "@/components/network/TaskComposer";
import { Pipeline } from "@/components/network/Pipeline";
import { AgentRoster } from "@/components/network/AgentRoster";

export default function NetworkPage() {
  const { agents, list, loading, error } = useAgents();

  return (
    <div className="h-full overflow-y-auto xl:overflow-hidden">
      {error && (
        <div className="border-b border-down/40 bg-down/10 px-4 py-2 font-mono text-[11px] text-down">
          Backend unreachable ({error}). Start the API on :8000 and SEED the
          market.
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 p-3 xl:h-full xl:grid-cols-12">
        {/* Left — post + watch */}
        <section className="flex flex-col gap-3 xl:col-span-7 xl:min-h-0">
          <Panel>
            <PanelHeader
              title="Post a task"
              right={
                <span className="font-mono text-[10px] text-dim">
                  decompose ▸ auction ▸ hire ▸ execute ▸ judge
                </span>
              }
            />
            <TaskComposer />
          </Panel>
          <Panel className="flex h-[600px] flex-col xl:h-auto xl:min-h-0 xl:flex-1">
            <PanelHeader title="Live pipeline" />
            <div className="min-h-0 flex-1 overflow-y-auto">
              <Pipeline agents={agents} />
            </div>
          </Panel>
        </section>

        {/* Right — agent roster */}
        <section className="xl:col-span-5 xl:min-h-0">
          <Panel className="flex h-[640px] flex-col xl:h-full xl:min-h-0">
            <PanelHeader
              title="Agent network"
              right={
                <span className="font-mono text-[10px] text-dim">
                  {list.length} agents
                </span>
              }
            />
            <div className="min-h-0 flex-1">
              <AgentRoster list={list} loading={loading} />
            </div>
          </Panel>
        </section>
      </div>
    </div>
  );
}
