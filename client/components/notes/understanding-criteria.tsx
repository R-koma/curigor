import { ChevronRightIcon } from "lucide-react";

// 文言はプロンプト（server/graph/prompts/feedback.py）の評価基準と一致させる
const CRITERIA: { label: string; description: string }[] = [
  {
    label: "高",
    description:
      "中心となる考え方を正確に説明でき、具体例や応用にも触れられている",
  },
  {
    label: "中",
    description: "基本は理解しているが、曖昧な点や抜けている重要な考え方がある",
  },
  {
    label: "低",
    description:
      "重要な考え方に誤解があるか曖昧な点が多く、基礎からの復習が必要",
  },
];

export function UnderstandingCriteria() {
  return (
    <details className="group mt-2 text-xs text-muted-foreground">
      <summary className="flex min-h-6 w-fit cursor-pointer list-none items-center gap-1 [&::-webkit-details-marker]:hidden">
        <ChevronRightIcon
          className="size-3.5 transition-transform group-open:rotate-90 motion-reduce:transition-none"
          aria-hidden
        />
        理解度の基準
      </summary>
      <dl className="mt-2 space-y-1 pl-4">
        {CRITERIA.map((c) => (
          <div key={c.label} className="flex gap-2">
            <dt className="shrink-0 font-medium">{c.label}</dt>
            <dd>{c.description}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
