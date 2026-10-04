import { BookOpenIcon, LightbulbIcon, TargetIcon } from "lucide-react";
import type { ComponentType } from "react";
import type { IntakeSummary } from "@/hooks/use-chat-websocket";

const ROWS: {
  key: keyof IntakeSummary;
  label: string;
  Icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}[] = [
  { key: "purpose", label: "目的", Icon: TargetIcon },
  { key: "source", label: "教材", Icon: BookOpenIcon },
  { key: "prior_knowledge", label: "今の理解", Icon: LightbulbIcon },
];

export function IntakeSummarySection({ intake }: { intake: IntakeSummary }) {
  const rows = ROWS.filter(({ key }) => intake[key] !== "");
  return (
    <section aria-label="学習の前提" className="space-y-3">
      <h2 className="px-0.5 text-sm font-semibold">学習の前提</h2>
      <dl className="space-y-3 text-sm">
        {rows.map(({ key, label, Icon }) => (
          <div key={key} className="flex items-start gap-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-text">
              <Icon aria-hidden className="size-3.5" />
            </span>
            <div className="min-w-0 space-y-0.5">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="break-words leading-snug">{intake[key]}</dd>
            </div>
          </div>
        ))}
      </dl>
    </section>
  );
}
