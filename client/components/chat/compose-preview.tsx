"use client";

import { Markdown } from "@/components/ui/markdown";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { closeOpenBlocks } from "@/lib/chat-markdown";
import { hasRichContent } from "@/lib/compose-insert";

const PREVIEW_DELAY_MS = 300;

export function ComposePreview({ value }: { value: string }) {
  const debounced = useDebouncedValue(value, PREVIEW_DELAY_MS);
  if (!hasRichContent(value) || !hasRichContent(debounced)) return null;

  return (
    <section
      aria-label="表示の確認"
      className="mb-2 max-h-48 overflow-y-auto rounded-xl border bg-background px-3 py-2"
    >
      <p className="mb-1 text-2xs text-muted-foreground">表示の確認</p>
      <Markdown
        variant="chat"
        className="text-sm [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
      >
        {closeOpenBlocks(debounced)}
      </Markdown>
    </section>
  );
}
