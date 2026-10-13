"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import {
  EXPLORE_START_TEXT,
  exploreAspectRequest,
  type ExploreOverview,
} from "@/lib/explore";

export function ExploreAspectChoices({
  overview,
  disabled = false,
  onChoose,
}: {
  overview: ExploreOverview;
  disabled?: boolean;
  onChoose: (text: string) => boolean | void;
}) {
  const sentRef = useRef(false);
  const choose = (text: string) => {
    if (sentRef.current) return;
    sentRef.current = true;
    if (onChoose(text) === false) sentRef.current = false;
  };

  return (
    <div role="group" aria-label="学び始める観点" className="mt-3 space-y-2">
      <p className="text-sm text-muted-foreground">
        どこから始めますか？ 気になる観点を選べます。
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="brand"
          disabled={disabled}
          onClick={() => choose(EXPLORE_START_TEXT)}
        >
          {EXPLORE_START_TEXT}
        </Button>
        {overview.aspects.map((a) => (
          <Button
            key={a.aspect_id}
            variant="outline"
            className="h-auto whitespace-normal text-left"
            disabled={disabled}
            onClick={() => choose(exploreAspectRequest(a.name))}
          >
            {a.name}
          </Button>
        ))}
      </div>
    </div>
  );
}
