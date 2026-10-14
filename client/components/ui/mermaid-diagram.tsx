"use client";

import { useEffect, useId, useState } from "react";
import { useTheme } from "next-themes";
import { Spinner } from "@/components/ui/spinner";
import { renderMermaid, type DiagramTheme } from "@/lib/mermaid";

type DiagramResult = { status: "drawn"; svg: string } | { status: "failed" };

export function DiagramPending() {
  return (
    <div className="my-3 flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner size="sm" />
      <span>図を描いています…</span>
    </div>
  );
}

export function MermaidDiagram({ code }: { code: string }) {
  const { resolvedTheme } = useTheme();
  const theme: DiagramTheme = resolvedTheme === "dark" ? "dark" : "default";
  const id = `mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const key = `${theme}\n${code}`;
  const [result, setResult] = useState<{
    key: string;
    value: DiagramResult;
  } | null>(null);

  useEffect(() => {
    let active = true;
    renderMermaid(id, code, theme).then(
      (svg) => {
        if (active) setResult({ key, value: { status: "drawn", svg } });
      },
      () => {
        if (active) setResult({ key, value: { status: "failed" } });
      },
    );
    return () => {
      active = false;
    };
  }, [id, code, theme, key]);

  const current = result?.key === key ? result.value : null;
  if (!current) return <DiagramPending />;
  if (current.status === "failed") {
    return (
      <div className="my-3">
        <p className="text-sm text-muted-foreground">
          図を表示できませんでした
        </p>
        <pre className="mt-1 overflow-x-auto rounded-lg bg-muted p-3 text-sm">
          <code>{code}</code>
        </pre>
      </div>
    );
  }
  return (
    <div
      role="img"
      aria-label="図"
      className="my-3 overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: current.svg }}
    />
  );
}
