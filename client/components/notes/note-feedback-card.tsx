import { EmptyState } from "@/components/ui/empty-state";
import { TrendingUpIcon } from "lucide-react";
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

export function NoteFeedbackCard({ feedback }: { feedback: Feedback }) {
  const understanding = understandingBadge(feedback.understanding_level);

  return (
    <article className="rounded-lg border bg-card p-4">
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
