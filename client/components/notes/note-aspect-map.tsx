import { ChevronRightIcon, NetworkIcon } from "lucide-react";

import { intakeRows } from "@/components/chat/intake-summary";
import type { IntakeSummary } from "@/hooks/use-chat-websocket";
import {
  aspectAnchorId,
  type AspectMap,
  type AspectNode,
} from "@/lib/aspect-map";
import { COVERAGE_DISPLAY, type Coverage } from "@/lib/status-display";
import { TONE_CLASSES } from "@/lib/tone";

export type { AspectMap } from "@/lib/aspect-map";

const MAX_DEPTH = 2;
const COVERAGE_ORDER: Coverage[] = ["covered", "partial", "uncovered"];

function coverageOf(node: AspectNode): Coverage {
  return node.coverage in COVERAGE_DISPLAY ? node.coverage : "uncovered";
}

function countCoverage(
  nodes: readonly AspectNode[],
  depth = 0,
  counts: Record<Coverage, number> = { covered: 0, partial: 0, uncovered: 0 },
): Record<Coverage, number> {
  for (const node of nodes) {
    counts[coverageOf(node)] += 1;
    if (node.children && depth < MAX_DEPTH) {
      countCoverage(node.children, depth + 1, counts);
    }
  }
  return counts;
}

function CoverageOverview({ aspects }: { aspects: readonly AspectNode[] }) {
  const counts = countCoverage(aspects);
  const total = COVERAGE_ORDER.reduce((sum, c) => sum + counts[c], 0);
  return (
    <div className="space-y-2.5">
      <div
        className="flex h-1.5 overflow-hidden rounded-full bg-muted"
        aria-hidden
      >
        {COVERAGE_ORDER.filter((c) => c !== "uncovered").map((c) => (
          <div
            key={c}
            className={TONE_CLASSES[COVERAGE_DISPLAY[c].tone].marker}
            style={{ width: `${(counts[c] / total) * 100}%` }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {COVERAGE_ORDER.map((c) => {
          const meta = COVERAGE_DISPLAY[c];
          const Icon = meta.icon;
          return (
            <li key={c} className="flex items-center gap-1">
              <Icon
                className={`size-3.5 ${TONE_CLASSES[meta.tone].text}`}
                aria-hidden
              />
              {meta.label}
              <span className="tabular-nums text-foreground">{counts[c]}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function AspectRow({ node, depth }: { node: AspectNode; depth: number }) {
  const meta = COVERAGE_DISPLAY[coverageOf(node)];
  const Icon = meta.icon;
  const nameClass =
    depth === 0 ? "text-sm font-medium" : "text-sm text-foreground/90";
  const head = (
    <>
      <Icon
        className={`size-4 shrink-0 ${TONE_CLASSES[meta.tone].text}`}
        aria-label={meta.label}
        role="img"
      />
      <span className={`min-w-0 flex-1 break-words ${nameClass}`}>
        {node.name}
      </span>
    </>
  );
  const rowClass =
    "flex min-h-8 items-center gap-2 rounded-md px-2 py-1 pointer-coarse:min-h-11";

  if (!node.summary) {
    return <div className={rowClass}>{head}</div>;
  }
  return (
    <details className="group/aspect">
      <summary
        className={`${rowClass} cursor-pointer list-none transition-colors hover:bg-muted [&::-webkit-details-marker]:hidden`}
      >
        {head}
        <ChevronRightIcon
          className="size-3.5 shrink-0 text-muted-foreground transition-transform group-open/aspect:rotate-90 motion-reduce:transition-none"
          aria-hidden
        />
      </summary>
      <p className="pb-1.5 pl-8 pr-2 text-xs leading-5 text-muted-foreground">
        {node.summary}
      </p>
    </details>
  );
}

function AspectItem({ node, depth }: { node: AspectNode; depth: number }) {
  return (
    <li>
      <div
        id={node.id ? aspectAnchorId(node.id) : undefined}
        className="scroll-mt-8 rounded-md max-md:scroll-mt-14 target:bg-brand-soft"
      >
        <AspectRow node={node} depth={depth} />
      </div>
      {node.children && node.children.length > 0 && depth < MAX_DEPTH && (
        <ul className="ml-4 border-l border-border pl-2">
          {node.children.map((child, idx) => (
            <AspectItem
              key={`${child.name}-${idx}`}
              node={child}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function IntakeDetails({ intake }: { intake: IntakeSummary }) {
  const rows = intakeRows(intake);
  if (rows.length === 0) return null;
  return (
    <details className="group/intake border-t pt-3">
      <summary className="flex min-h-8 w-fit cursor-pointer list-none items-center gap-1 text-xs text-muted-foreground hover:text-foreground pointer-coarse:min-h-11 [&::-webkit-details-marker]:hidden">
        <ChevronRightIcon
          className="size-3.5 transition-transform group-open/intake:rotate-90 motion-reduce:transition-none"
          aria-hidden
        />
        学習の前提
      </summary>
      <dl
        aria-label="学習の前提"
        className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 pl-4 text-sm"
      >
        {rows.map(({ key, label }) => (
          <div key={key} className="contents">
            <dt className="text-xs leading-5 text-muted-foreground">{label}</dt>
            <dd className="break-words leading-5">{intake[key]}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

export function NoteAspectMap({
  aspectMap,
  intake,
}: {
  aspectMap: AspectMap;
  intake?: IntakeSummary | null;
}) {
  if (!aspectMap.aspects || aspectMap.aspects.length === 0) {
    return null;
  }
  return (
    <section id="aspect-map" className="scroll-mt-8 max-md:scroll-mt-14">
      <div className="mb-4 flex items-center gap-2">
        <NetworkIcon className="size-4 text-muted-foreground" />
        <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          観点マップ
        </h2>
      </div>
      <div className="space-y-4 rounded-lg border bg-card p-4">
        <CoverageOverview aspects={aspectMap.aspects} />
        <ul className="-mx-2 space-y-0.5">
          {aspectMap.aspects.map((aspect, idx) => (
            <AspectItem key={`${aspect.name}-${idx}`} node={aspect} depth={0} />
          ))}
        </ul>
        {intake && <IntakeDetails intake={intake} />}
      </div>
    </section>
  );
}
