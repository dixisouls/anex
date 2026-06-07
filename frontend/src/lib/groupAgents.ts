import { agentCategory, type Category } from "./agents";
import type { Agent, Tier } from "./types";

const TIER_RANK: Record<Tier, number> = { pro: 3, flash: 2, lite: 1 };

export interface CapabilityGroup {
  capability_id: string;
  name: string;
  category: Category;
  variants: Agent[];
  bestReputation: number;
}

export function groupAgentsByCapability(list: Agent[]): CapabilityGroup[] {
  const map = new Map<string, Agent[]>();
  for (const agent of list) {
    const key = agent.capability_id;
    const bucket = map.get(key);
    if (bucket) bucket.push(agent);
    else map.set(key, [agent]);
  }

  const groups: CapabilityGroup[] = [];
  for (const variants of map.values()) {
    variants.sort(
      (a, b) => TIER_RANK[b.service_tier] - TIER_RANK[a.service_tier],
    );
    const lead = variants[0];
    groups.push({
      capability_id: lead.capability_id,
      name: lead.name,
      category: agentCategory(lead.agent_id),
      variants,
      bestReputation: Math.max(...variants.map((v) => v.reputation)),
    });
  }

  return groups.sort((a, b) => b.bestReputation - a.bestReputation);
}
