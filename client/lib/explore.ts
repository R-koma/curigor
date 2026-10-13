export interface ExploreOverviewAspect {
  aspect_id: string;
  name: string;
  summary: string;
  is_core: boolean;
  explained: boolean;
}

export interface ExploreOverview {
  aspects: ExploreOverviewAspect[];
}

export const EXPLORE_START_TEXT = "最初から";

export function isExploreOverview(value: unknown): value is ExploreOverview {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as { aspects?: unknown }).aspects)
  );
}

export function exploreAspectRequest(name: string): string {
  return `「${name}」から教えてください`;
}

export function exploreProgress(overview: ExploreOverview): {
  reached: number;
  target: number;
  complete: boolean;
} {
  const core = overview.aspects.filter((a) => a.is_core);
  const counted = core.length > 0 ? core : overview.aspects;
  const reached = counted.filter((a) => a.explained).length;
  return {
    reached,
    target: counted.length,
    complete: counted.length > 0 && reached === counted.length,
  };
}

export function awaitingFirstExplanation(overview: ExploreOverview): boolean {
  return (
    overview.aspects.length > 0 && overview.aspects.every((a) => !a.explained)
  );
}
