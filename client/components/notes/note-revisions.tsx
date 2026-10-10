import { SproutIcon } from "lucide-react";
import { Markdown } from "@/components/ui/markdown";

export interface NoteRevision {
  id: string;
  content: string;
  created_at: string;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

export function NoteRevisions({ revisions }: { revisions: NoteRevision[] }) {
  if (revisions.length === 0) {
    return null;
  }

  return (
    <section id="revisions" className="scroll-mt-8 max-md:scroll-mt-14">
      <div className="mb-4 flex items-center gap-2">
        <SproutIcon className="size-4 text-muted-foreground" />
        <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          復習で深まった点
        </h2>
      </div>
      <div className="space-y-6">
        {revisions.map((revision) => (
          <div key={revision.id} className="border-l-2 border-primary/40 pl-4">
            <div className="mb-2 text-xs text-muted-foreground">
              {formatDate(revision.created_at)} の復習
            </div>
            <Markdown variant="article">{revision.content}</Markdown>
          </div>
        ))}
      </div>
    </section>
  );
}
