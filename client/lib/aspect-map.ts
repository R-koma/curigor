import type { Coverage } from "@/lib/status-display";

export interface AspectNode {
  id?: string;
  name: string;
  summary: string;
  coverage: Coverage;
  children?: AspectNode[];
}

export interface AspectMap {
  root: string;
  aspects: AspectNode[];
}

export function aspectAnchorId(id: string): string {
  return `aspect-${id}`;
}

function find(nodes: readonly AspectNode[], id: string): AspectNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    const hit = find(node.children ?? [], id);
    if (hit) return hit;
  }
  return null;
}

export function findAspectName(
  map: AspectMap | null,
  id: string,
): string | null {
  if (!map) return null;
  return find(map.aspects, id)?.name ?? null;
}
