import type { IntakeSummary } from "@/hooks/use-chat-websocket";

const ROWS: { key: keyof IntakeSummary; label: string }[] = [
  { key: "purpose", label: "目的" },
  { key: "source", label: "教材" },
  { key: "prior_knowledge", label: "今の理解" },
];

export function IntakeSummarySection({ intake }: { intake: IntakeSummary }) {
  const rows = ROWS.filter(({ key }) => intake[key] !== "");
  return (
    <section aria-label="学習の前提" className="space-y-2">
      <h2 className="px-0.5 text-sm font-semibold">学習の前提</h2>
      <dl className="space-y-1.5 rounded-lg bg-muted/40 px-3 py-2.5 text-sm">
        {rows.map(({ key, label }) => (
          <div key={key} className="flex gap-3">
            <dt className="w-16 shrink-0 text-xs leading-5 text-muted-foreground">
              {label}
            </dt>
            <dd className="min-w-0 break-words">{intake[key]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
