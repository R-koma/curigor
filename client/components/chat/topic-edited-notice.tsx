import { PencilIcon } from "lucide-react";

export function TopicEditedNotice({ content }: { content: string }) {
  return (
    <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
      <PencilIcon aria-hidden className="size-3.5" />
      <span>{content}</span>
    </div>
  );
}
