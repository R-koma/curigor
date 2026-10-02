import { CheckIcon, ChevronDownIcon } from "lucide-react";
import type { LearningProgress } from "@/hooks/use-chat-websocket";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { DepthMapPanel } from "@/components/chat/depth-map-panel";

export function LearningProgressIndicator({
  progress,
  highlighted = false,
}: {
  progress: LearningProgress;
  highlighted?: boolean;
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
          data-highlighted={highlighted ? "true" : undefined}
          className="group flex cursor-pointer items-center gap-2 rounded-full border bg-muted/40 py-1 pl-3 pr-2 text-xs font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 data-[state=open]:bg-muted data-[highlighted=true]:border-blue-500/60 data-[highlighted=true]:bg-blue-500/10"
        >
          <span>観点</span>
          {bar}
          <ChevronDownIcon
            aria-hidden
            className="size-3.5 text-muted-foreground transition-transform group-data-[state=open]:rotate-180"
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="max-h-[70vh] w-[min(22rem,calc(100vw-2rem))] overflow-y-auto p-4"
      >
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
    <span role="status" aria-live="polite" className="flex">
      {notice && (
        <span
          key={notice}
          className="flex max-w-xs items-start gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-700 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-right-2 dark:text-blue-300"
        >
          <CheckIcon aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          <span className="break-words">{notice}</span>
        </span>
      )}
    </span>
  );
}
