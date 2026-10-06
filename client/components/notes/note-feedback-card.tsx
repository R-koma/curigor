import { EmptyState } from "@/components/ui/empty-state";
import Link from "next/link";
import { RotateCcwIcon, TrendingUpIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FeedbackUpdatedNotice } from "@/components/notes/feedback-updated-notice";
import { Badge } from "@/components/ui/badge";
import { understandingBadge } from "@/lib/badge";
import {
  feedbackSourceLabel,
  formatFeedbackDate,
  splitFeedbackItems,
  type Feedback,
} from "@/lib/feedback";
import { FEEDBACK_DISPLAY } from "@/lib/status-display";
import { TONE_CLASSES } from "@/lib/tone";

interface FeedbackSectionProps {
  label: string;
  items: string[];
  tone: "positive" | "improvement";
}

function FeedbackSection({ label, items, tone }: FeedbackSectionProps) {
  const { tone: toneName, icon: Icon } = FEEDBACK_DISPLAY[tone];
  const toneStyles = TONE_CLASSES[toneName];

  return (
    <div className={`border-l-2 ${toneStyles.border} pl-3`}>
      <h3
        className={`mb-2 flex items-center gap-1.5 text-xs font-medium ${toneStyles.text}`}
      >
        <Icon className="size-3.5" aria-hidden />
        {label}
      </h3>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li
            key={index}
            className="flex gap-2 text-sm leading-6 text-foreground/90"
          >
            <span
              className={`mt-2 size-1.5 shrink-0 rounded-full ${toneStyles.marker}`}
              aria-hidden
            />
            <span className="min-w-0 break-words">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function FeedbackSections({ feedback }: { feedback: Feedback }) {
  const strengths = splitFeedbackItems(feedback.strength);
  const improvements = splitFeedbackItems(feedback.improvements);

  return (
    <div className="space-y-4">
      {strengths.length > 0 && (
        <FeedbackSection label="強み" items={strengths} tone="positive" />
      )}
      {improvements.length > 0 && (
        <FeedbackSection
          label="改善点"
          items={improvements}
          tone="improvement"
        />
      )}
    </div>
  );
}

export function FeedbackWhen({ feedback }: { feedback: Feedback }) {
  const source = feedbackSourceLabel(feedback.session_type);
  const date = formatFeedbackDate(feedback.created_at);
  return (
    <time dateTime={feedback.created_at}>
      {source ? `${date} の${source}` : date}
    </time>
  );
}

export function NoteFeedbackCard({
  feedback,
  reviewHref,
  justUpdated = false,
}: {
  feedback: Feedback;
  reviewHref?: string;
  justUpdated?: boolean;
}) {
  const understanding = understandingBadge(feedback.understanding_level);
  const hasImprovements = splitFeedbackItems(feedback.improvements).length > 0;

  return (
    <article className="rounded-lg border bg-card p-4">
      {justUpdated && <FeedbackUpdatedNotice />}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Badge variant={understanding.variant} className="gap-1 font-normal">
          <TrendingUpIcon className="size-3.5" aria-hidden />
          理解度: {understanding.label}
        </Badge>
        <span className="text-xs text-muted-foreground">
          <FeedbackWhen feedback={feedback} />
        </span>
      </div>
      <div className="mt-4">
        <FeedbackSections feedback={feedback} />
      </div>
      {reviewHref && hasImprovements && (
        <div className="mt-4 border-t pt-4">
          <p className="text-xs text-muted-foreground">
            次の復習では、この改善点を重点的に確認します。
          </p>
          <Button asChild variant="outline" size="sm" className="mt-2 w-full">
            <Link href={reviewHref}>
              <RotateCcwIcon aria-hidden />
              復習する
            </Link>
          </Button>
        </div>
      )}
    </article>
  );
}

export function NoteFeedbackEmpty() {
  return (
    <EmptyState
      title="フィードバックはまだありません"
      className="rounded-lg border border-dashed bg-card/50 py-8"
    />
  );
}
