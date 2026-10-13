"use client";

import { CheckIcon, ChevronDownIcon } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { TooltipLabel } from "@/components/ui/tooltip";
import {
  exploreProgress,
  type ExploreOverview,
  type ExploreOverviewAspect,
} from "@/lib/explore";

function AspectRow({ aspect }: { aspect: ExploreOverviewAspect }) {
  return (
    <li className="flex gap-3 py-3 first:pt-0 last:pb-0">
      <span
        className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full ${
          aspect.explained ? "bg-brand text-white" : "border-2 border-border"
        }`}
      >
        {aspect.explained && <CheckIcon aria-hidden className="size-3" />}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-start justify-between gap-2">
          <span className="break-words text-sm font-medium leading-snug">
            {aspect.name}
          </span>
          {aspect.explained && (
            <span className="shrink-0 rounded-full bg-brand-soft px-2 py-0.5 text-2xs font-medium text-brand-text">
              教わった
            </span>
          )}
        </div>
        {aspect.summary && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {aspect.summary}
          </p>
        )}
      </div>
    </li>
  );
}

function AspectSection({
  title,
  aspects,
  muted = false,
}: {
  title: string;
  aspects: ExploreOverviewAspect[];
  muted?: boolean;
}) {
  return (
    <section className="space-y-3">
      <h2
        className={`px-0.5 text-sm font-semibold ${muted ? "text-muted-foreground" : ""}`}
      >
        {title}
      </h2>
      <ul aria-label={title} className="divide-y divide-border/60 px-0.5">
        {aspects.map((a) => (
          <AspectRow key={a.aspect_id} aspect={a} />
        ))}
      </ul>
    </section>
  );
}

export function ExploreOverviewPanel({
  overview,
}: {
  overview: ExploreOverview;
}) {
  const core = overview.aspects.filter((a) => a.is_core);
  const related = overview.aspects.filter((a) => !a.is_core);
  return (
    <div className="space-y-5">
      <AspectSection
        title="押さえたい観点"
        aspects={core.length > 0 ? core : overview.aspects}
      />
      {core.length > 0 && related.length > 0 && (
        <div className="border-t pt-4">
          <AspectSection title="広げられる観点" aspects={related} muted />
        </div>
      )}
    </div>
  );
}

export function ExploreOverviewIndicator({
  overview,
  highlighted = false,
}: {
  overview: ExploreOverview;
  highlighted?: boolean;
}) {
  const { reached, target } = exploreProgress(overview);
  return (
    <Popover>
      <TooltipLabel label="トピックの全体像と、教わった観点を表示">
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label="全体像を表示"
            data-highlighted={highlighted ? "true" : undefined}
            className="group flex cursor-pointer items-center gap-2 rounded-full border bg-muted/40 py-1 pl-2 pr-2 text-xs font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 data-[state=open]:bg-muted data-[highlighted=true]:border-brand/60 data-[highlighted=true]:bg-brand-soft md:pl-3"
          >
            <span className="hidden md:inline">全体像</span>
            <span className="text-xs tabular-nums text-muted-foreground">
              {reached}/{target}
            </span>
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
        <ExploreOverviewPanel overview={overview} />
      </PopoverContent>
    </Popover>
  );
}
