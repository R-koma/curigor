import type { LearningProgress } from "@/hooks/use-chat-websocket";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { DepthMapPanel } from "@/components/chat/depth-map-panel";

export function LearningProgressIndicator({
  progress,
}: {
  progress: LearningProgress;
}) {
  const reached = Math.min(
    progress.reached_aspects.length,
    progress.target_count,
  );
  const title =
    progress.reached_aspects.length > 0
      ? `説明できた観点: ${progress.reached_aspects.join("、")}`
      : "まだ説明できた観点はありません";
  const aspects = progress.aspects ?? [];

  const bar = (
    <>
      <div className="flex gap-0.5">
        {Array.from({ length: progress.target_count }, (_, i) => (
          <span
            key={i}
            className={`h-1.5 w-4 rounded-full ${i < reached ? "bg-blue-500" : "bg-muted"}`}
          />
        ))}
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {reached}/{progress.target_count}
      </span>
    </>
  );

  if (aspects.length === 0) {
    return (
      <div className="flex items-center gap-2" title={title}>
        {bar}
      </div>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          title={title}
          aria-label="観点ごとの到達度を表示"
          className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/30"
        >
          {bar}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <DepthMapPanel
          aspects={aspects}
          reached={reached}
          target={progress.target_count}
        />
      </PopoverContent>
    </Popover>
  );
}

export function ProgressAdvanceNotice({ notice }: { notice: string | null }) {
  return (
    <span
      role="status"
      aria-live="polite"
      className="max-w-xs truncate text-xs text-blue-600 motion-safe:animate-in motion-safe:fade-in-0 dark:text-blue-400"
    >
      {notice ?? ""}
    </span>
  );
}
