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
          className={`h-1 flex-1 rounded-full transition-colors ${
            i < dots
              ? dots >= ACHIEVED_DOTS
                ? "bg-brand"
                : "bg-brand/70"
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
    <li className="flex gap-3 py-3 first:pt-0 last:pb-0 sm:py-4 sm:first:pt-0 sm:last:pb-0">
      <span
        className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full ${
          achieved
            ? "bg-brand text-white"
            : dots > 0
              ? "border-2 border-brand/60"
              : "border-2 border-border"
        }`}
      >
        {achieved && (
          <CheckIcon role="img" aria-label="達成" className="size-3" />
        )}
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-start justify-between gap-2">
          <span className="break-words text-sm font-medium leading-snug">
            {aspect.name}
          </span>
          {label && (
            <span className="shrink-0 rounded-full bg-brand-soft px-2 py-0.5 text-2xs font-medium text-brand-text">
              {label}
            </span>
          )}
        </div>
        <StageBar dots={dots} />
        <p className="text-xs leading-relaxed text-muted-foreground">
          {stageMessage(aspect.reached_stage)}
        </p>
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
  const main = aspects.filter((a) => a.is_core);
  const related = aspects.filter((a) => !a.is_core);
  const ratio = target > 0 ? Math.min(reached / target, 1) : 0;
  return (
    <div className="space-y-5">
      <section className="space-y-3">
        <div className="space-y-2">
          <div className="flex items-baseline justify-between px-0.5">
            <h2 className="text-sm font-semibold">押さえたい観点</h2>
            <span className="text-xs tabular-nums text-muted-foreground">
              {reached}/{target} 達成
            </span>
          </div>
          <div
            aria-hidden
            className="h-1 overflow-hidden rounded-full bg-muted"
          >
            <div
              className="h-full rounded-full bg-brand transition-[width] duration-300"
              style={{ width: `${ratio * 100}%` }}
            />
          </div>
        </div>
        <ul
          aria-label="押さえたい観点"
          className="divide-y divide-border/60 px-0.5"
        >
          {main.map((a) => (
            <AspectRow key={a.name} aspect={a} />
          ))}
        </ul>
      </section>
      {related.length > 0 && (
        <section className="space-y-3 border-t pt-4">
          <h2 className="px-0.5 text-sm font-semibold text-muted-foreground">
            広げられる観点
          </h2>
          <ul
            aria-label="広げられる観点"
            className="divide-y divide-border/60 px-0.5"
          >
            {related.map((a) => (
              <AspectRow key={a.name} aspect={a} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
