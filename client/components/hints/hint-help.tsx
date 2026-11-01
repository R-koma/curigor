"use client";

import { useId } from "react";
import { CircleHelpIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { TooltipLabel } from "@/components/ui/tooltip";
import { HINT_TEXT, type HintId } from "@/lib/hints";
import { cn } from "@/lib/utils";

export function HintHelp({
  ids,
  align = "end",
  className,
}: {
  ids: readonly HintId[];
  align?: "start" | "center" | "end";
  className?: string;
}) {
  const headingId = useId();

  return (
    <Popover>
      <TooltipLabel label="使い方を見る">
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="使い方を見る"
            className={cn(
              "shrink-0 text-muted-foreground hover:bg-transparent hover:text-foreground aria-expanded:bg-transparent aria-expanded:text-foreground dark:hover:bg-transparent pointer-coarse:size-11",
              className,
            )}
          >
            <CircleHelpIcon className="size-4" />
          </Button>
        </PopoverTrigger>
      </TooltipLabel>
      <PopoverContent
        align={align}
        aria-labelledby={headingId}
        className="w-80 max-w-[calc(100vw-2rem)]"
      >
        <HintHelpSection ids={ids} headingId={headingId} />
      </PopoverContent>
    </Popover>
  );
}

export function HintHelpSection({
  ids,
  headingId,
  className,
}: {
  ids: readonly HintId[];
  headingId?: string;
  className?: string;
}) {
  return (
    <section aria-labelledby={headingId} className={className}>
      <h2 id={headingId} className="mb-2 text-sm font-semibold">
        使い方
      </h2>
      <ul className="space-y-2 text-sm leading-relaxed text-muted-foreground">
        {ids.map((id) => (
          <li key={id}>{HINT_TEXT[id]}</li>
        ))}
      </ul>
    </section>
  );
}
