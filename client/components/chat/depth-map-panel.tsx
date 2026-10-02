import { CheckIcon } from "lucide-react";
import {
  stageDots,
  stageLabel,
  stageMessage,
  type ProgressAspect,
} from "@/lib/progress";

const STAGE_COUNT = 4;
const ACHIEVED_DOTS = 3;

function StageBar({ dots }: { dots: number }) {
  return (
    <span
      role="img"
      aria-label={`${STAGE_COUNT} 段階中 ${dots} 段階`}
      className="flex w-full gap-1"
    >
      {Array.from({ length: STAGE_COUNT }, (_, i) => (
        <span
          key={i}
          className={`h-1.5 flex-1 rounded-full transition-colors ${
            i < dots
              ? dots >= ACHIEVED_DOTS
                ? "bg-blue-600"
                : "bg-blue-400/70"
              : "bg-muted"
          }`}
        />
      ))}
    </span>
  );
}

function AspectRow({ aspect }: { aspect: ProgressAspect }) {
  const dots = stageDots(aspect.reached_stage);
  const label = stageLabel(aspect.reached_stage);
  const achieved = dots >= ACHIEVED_DOTS;
  return (
    <li className="space-y-2 rounded-lg bg-muted/40 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 text-sm font-medium">
          {achieved && (
            <CheckIcon
              role="img"
              aria-label="達成"
              className="size-4 shrink-0 text-blue-600"
            />
          )}
          <span className="break-words">{aspect.name}</span>
        </span>
        {label && (
          <span className="shrink-0 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-300">
            {label}
          </span>
        )}
      </div>
      <StageBar dots={dots} />
      <p className="text-xs leading-relaxed text-muted-foreground">
        {stageMessage(aspect.reached_stage)}
      </p>
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
  const main = aspects.filter((a) => a.is_core);
  const related = aspects.filter((a) => !a.is_core);
  return (
    <div className="space-y-4">
      <section className="space-y-2">
        <div className="flex items-baseline justify-between px-0.5">
          <h2 className="text-sm font-semibold">押さえたい観点</h2>
          <span className="text-xs tabular-nums text-muted-foreground">
            {reached}/{target} 達成
          </span>
        </div>
        <ul aria-label="押さえたい観点" className="space-y-2">
          {main.map((a) => (
            <AspectRow key={a.name} aspect={a} />
          ))}
        </ul>
      </section>
      {related.length > 0 && (
        <section className="space-y-2">
          <h2 className="px-0.5 text-sm font-semibold text-muted-foreground">
            広げられる観点
          </h2>
          <ul aria-label="広げられる観点" className="space-y-2">
            {related.map((a) => (
              <AspectRow key={a.name} aspect={a} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
