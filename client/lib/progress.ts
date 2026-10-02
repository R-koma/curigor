export type MapStage = "mentioned" | "defined" | "reasoned" | "applied";

export interface ProgressAspect {
  name: string;
  is_core: boolean;
  reached_stage: MapStage | null;
}

type AchievedStage = "defined" | "reasoned" | "applied";

export interface ProgressAdvance {
  name: string;
  stage: AchievedStage;
  others: number;
}

const STAGE_DOTS: Record<MapStage, number> = {
  mentioned: 1,
  defined: 2,
  reasoned: 3,
  applied: 4,
};

const NEXT_STEP: Record<MapStage | "none", string> = {
  none: "まだ話していません",
  mentioned: "次は、どういうものかを説明してみましょう",
  defined: "次は、なぜ必要か・どう成り立つかを説明してみましょう",
  reasoned: "なぜ・仕組みまで説明できました",
  applied: "目的に沿った使い方まで説明できました",
};

const ACHIEVED: Record<AchievedStage, string> = {
  defined: "どういうものかを説明できました",
  reasoned: "なぜ・仕組みまで説明できました",
  applied: "目的に沿った使い方まで説明できました",
};

export function stageDots(stage: MapStage | null): number {
  return stage ? STAGE_DOTS[stage] : 0;
}

export function stageMessage(stage: MapStage | null): string {
  return NEXT_STEP[stage ?? "none"];
}

export function detectAdvance(
  prev: ProgressAspect[] | null,
  next: ProgressAspect[],
): ProgressAdvance | null {
  if (prev === null) return null;
  const before = new Map(prev.map((a) => [a.name, stageDots(a.reached_stage)]));
  const risen = next.filter((a) => {
    const now = stageDots(a.reached_stage);
    return now >= STAGE_DOTS.defined && now > (before.get(a.name) ?? 0);
  });
  if (risen.length === 0) return null;
  const top = risen.reduce((best, a) =>
    stageDots(a.reached_stage) > stageDots(best.reached_stage) ? a : best,
  );
  return {
    name: top.name,
    stage: top.reached_stage as AchievedStage,
    others: risen.length - 1,
  };
}

export function formatAdvance(advance: ProgressAdvance): string {
  const base = `${advance.name}: ${ACHIEVED[advance.stage]}`;
  return advance.others > 0 ? `${base}（ほか ${advance.others} 件）` : base;
}
