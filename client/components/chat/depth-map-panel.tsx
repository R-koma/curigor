import { stageDots, stageMessage, type ProgressAspect } from "@/lib/progress";

const STAGE_COUNT = 4;

function AspectRow({ aspect }: { aspect: ProgressAspect }) {
  const dots = stageDots(aspect.reached_stage);
  return (
    <li className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{aspect.name}</span>
        {aspect.is_core && (
          <span className="shrink-0 text-xs text-muted-foreground">中核</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span
          className="flex shrink-0 gap-0.5"
          aria-label={`${STAGE_COUNT} 段階中 ${dots} 段階`}
        >
          {Array.from({ length: STAGE_COUNT }, (_, i) => (
            <span
              key={i}
              className={`h-1.5 w-3 rounded-full ${i < dots ? "bg-blue-500" : "bg-muted"}`}
            />
          ))}
        </span>
        <span className="text-xs text-muted-foreground">
          {stageMessage(aspect.reached_stage)}
        </span>
      </div>
    </li>
  );
}

export function DepthMapPanel({
  aspects,
  reached,
  target,
}: {
  aspects: ProgressAspect[];
  reached: number;
  target: number;
}) {
  const core = aspects.filter((a) => a.is_core);
  const related = aspects.filter((a) => !a.is_core);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">説明できた観点</span>
        <span className="text-xs tabular-nums text-muted-foreground">
          {reached}/{target}
        </span>
      </div>
      <ul aria-label="中核の観点" className="space-y-3">
        {core.map((a) => (
          <AspectRow key={a.name} aspect={a} />
        ))}
      </ul>
      {related.length > 0 && (
        <>
          <div className="h-px bg-border" />
          <ul aria-label="関連する観点" className="space-y-3 opacity-80">
            {related.map((a) => (
              <AspectRow key={a.name} aspect={a} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
