import {
  aspectAnchorId,
  findAspectName,
  type AspectMap,
} from "@/lib/aspect-map";
import {
  REVIEW_RESULT_LABELS,
  type ReviewResult,
  type ReviewResultStatus,
} from "@/lib/feedback";
import { Badge } from "@/components/ui/badge";

const STATUS_VARIANT: Record<
  ReviewResultStatus,
  "success" | "warning" | "outline"
> = {
  explained: "success",
  explained_with_hint: "warning",
  not_explained: "warning",
  not_asked: "outline",
};

export function ReviewResultList({
  results,
  aspectMap,
}: {
  results: ReviewResult[];
  aspectMap: AspectMap | null;
}) {
  return (
    <section aria-labelledby="review-results-heading">
      <h3
        id="review-results-heading"
        className="mb-2 text-xs font-medium text-muted-foreground"
      >
        要点ごとの結果
      </h3>
      <ul className="space-y-3">
        {results.map((result) => {
          const aspectName = result.aspect_id
            ? findAspectName(aspectMap, result.aspect_id)
            : null;
          return (
            <li key={result.point_id} className="space-y-1">
              <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                <p className="min-w-0 flex-1 basis-48 break-words text-sm leading-6 text-foreground/90">
                  {result.question}
                </p>
                <Badge
                  variant={STATUS_VARIANT[result.status]}
                  className="shrink-0 font-normal"
                >
                  {REVIEW_RESULT_LABELS[result.status]}
                </Badge>
              </div>
              <p className="break-words text-xs leading-5 text-muted-foreground">
                {result.point}
              </p>
              {result.aspect_id && aspectName && (
                <a
                  href={`#${aspectAnchorId(result.aspect_id)}`}
                  className="block text-2xs text-brand-text underline-offset-2 hover:underline"
                >
                  観点: {aspectName}
                </a>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
