import { CheckIcon, ChevronDownIcon } from "lucide-react";
import type { LearningProgress } from "@/hooks/use-chat-websocket";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { TooltipLabel } from "@/components/ui/tooltip";
import { DepthMapPanel } from "@/components/chat/depth-map-panel";
import { IntakeSummarySection } from "@/components/chat/intake-summary";

export function canOpenProgressPanel(progress: LearningProgress): boolean {
  return (progress.aspects?.length ?? 0) > 0 || Boolean(progress.intake);
}

export function LearningProgressIndicator({
  progress,
  highlighted = false,
  open,
  onOpenChange,
}: {
  progress: LearningProgress;
  highlighted?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
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
            className={`h-1.5 w-4 rounded-full ${i < reached ? "bg-brand" : "bg-muted"}`}
          />
        ))}
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {reached}/{progress.target_count}
      </span>
    </>
  );

  if (!canOpenProgressPanel(progress)) {
    return (
      <TooltipLabel label={title}>
        <div className="flex items-center gap-2" tabIndex={0}>
          {bar}
        </div>
      </TooltipLabel>
    );
  }

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <TooltipLabel label={title}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label="観点ごとの到達度を表示"
            data-highlighted={highlighted ? "true" : undefined}
            className="group flex cursor-pointer items-center gap-2 rounded-full border bg-muted/40 py-1 pl-2 pr-2 md:pl-3 text-xs font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 data-[state=open]:bg-muted data-[highlighted=true]:border-brand/60 data-[highlighted=true]:bg-brand-soft"
          >
            <span className="hidden md:inline">観点</span>
            {bar}
            <ChevronDownIcon
              aria-hidden
              className="size-3.5 text-muted-foreground"
            />
          </button>
        </PopoverTrigger>
      </TooltipLabel>
      <PopoverContent
        align="start"
        className="max-h-[70vh] w-[min(45rem,calc(100vw-2rem))] overflow-y-auto p-4 sm:p-6"
      >
        <div className="space-y-5 sm:space-y-6">
          {progress.intake && (
            <>
              <IntakeSummarySection intake={progress.intake} />
              {aspects.length > 0 && <hr className="border-border/60" />}
            </>
          )}
          {aspects.length > 0 && (
            <DepthMapPanel
              aspects={aspects}
              reached={reached}
              target={progress.target_count}
            />
          )}
        </div>
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
          className="flex max-w-xs items-start gap-1.5 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand-text motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-right-2"
        >
          <CheckIcon aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          <span className="break-words">{notice}</span>
        </span>
      )}
    </span>
  );
}
