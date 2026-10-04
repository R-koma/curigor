import { EmptyState } from "@/components/ui/empty-state";
import { TrendingUpIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { understandingBadge } from "@/lib/badge";
import { FEEDBACK_DISPLAY } from "@/lib/status-display";
import { TONE_CLASSES } from "@/lib/tone";

interface Feedback {
  id: string;
  understanding_level: string;
  strength: string;
  improvements: string;
  created_at: string;
}

function splitItems(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^[\s・\-*]+/, "").trim())
    .filter((line) => line.length > 0);
}

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
      <div
        className={`mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider ${toneStyles.text}`}
      >
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li
            key={index}
            className="flex gap-2 text-sm leading-6 text-foreground/90"
          >
            <span
              className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${toneStyles.marker}`}
              aria-hidden
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function NoteFeedbackCard({ feedback }: { feedback: Feedback }) {
  const strengths = splitItems(feedback.strength);
  const improvements = splitItems(feedback.improvements);
  const understanding = understandingBadge(feedback.understanding_level);

  return (
    <article className="rounded-lg border bg-card p-4">
      <Badge variant={understanding.variant} className="gap-1 font-normal">
        <TrendingUpIcon className="h-3.5 w-3.5" />
        理解度: {understanding.label}
      </Badge>
      <div className="mt-4 space-y-4">
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
