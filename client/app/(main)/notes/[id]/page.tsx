import { headers } from "next/headers";

export const dynamic = "force-dynamic";
import { fetchAPI, getToken } from "@/lib/api";
import { Markdown } from "@/components/ui/markdown";
import { NoteHeader } from "@/components/notes/note-header";
import { NoteFeedbackPanel } from "@/components/notes/note-feedback-panel";
import {
  NoteAspectMap,
  type AspectMap,
} from "@/components/notes/note-aspect-map";
import { NoteCollectionPicker } from "@/components/notes/note-collection-picker";
import { NoteEditForm } from "@/components/notes/note-edit-form";
import {
  NoteRevisions,
  type NoteRevision,
} from "@/components/notes/note-revisions";
import type { IntakeSummary } from "@/hooks/use-chat-websocket";
import type { Feedback } from "@/lib/feedback";
import { SparklesIcon, FileTextIcon, MessageSquareIcon } from "lucide-react";

interface Note {
  id: string;
  topic: string;
  content: string;
  summary: string;
  status: string;
  category: string | null;
  collection_id: string | null;
  suggested_collection: string | null;
  aspect_map: AspectMap | null;
  intake: IntakeSummary | null;
  created_at: string;
  updated_at: string;
  review_count: number;
}

export default async function NotePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ edit?: string }>;
}) {
  const { id } = await params;
  const { edit } = await searchParams;
  const isEditing = edit === "1";
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const [note, { feedbacks }, { revisions }] = await Promise.all([
    fetchAPI(`/api/notes/${id}`, { token }) as Promise<Note>,
    fetchAPI(`/api/notes/${id}/feedbacks`, { token }) as Promise<{
      feedbacks: Feedback[];
    }>,
    fetchAPI(`/api/notes/${id}/revisions`, { token }) as Promise<{
      revisions: NoteRevision[];
    }>,
  ]);

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <NoteHeader
          id={note.id}
          topic={note.topic}
          status={note.status}
          category={note.category}
          createdAt={note.created_at}
          updatedAt={note.updated_at}
          reviewCount={note.review_count}
          summary={note.summary}
          content={note.content}
          isEditing={isEditing}
        />
        {!isEditing && (
          <NoteCollectionPicker
            noteId={note.id}
            collectionId={note.collection_id}
            suggestedCollection={note.suggested_collection}
          />
        )}

        {!isEditing && (
          <nav
            aria-label="セクション"
            className="mb-10 flex flex-wrap gap-x-6 gap-y-2 border-b border-border pb-4 text-sm"
          >
            <a
              href="#summary"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              要約
            </a>
            <a
              href="#content"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              内容
            </a>
            {note.aspect_map && note.aspect_map.aspects?.length > 0 && (
              <a
                href="#aspect-map"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                観点マップ
              </a>
            )}
            {revisions.length > 0 && (
              <a
                href="#revisions"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                復習で深まった点
              </a>
            )}
            <a
              href="#feedback"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              フィードバック
            </a>
          </nav>
        )}

        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-12">
          <main className="min-w-0 space-y-10">
            {isEditing ? (
              <NoteEditForm
                noteId={note.id}
                initialTopic={note.topic}
                initialSummary={note.summary ?? ""}
                initialContent={note.content}
              />
            ) : (
              <>
                <section
                  id="summary"
                  className="scroll-mt-8 border-l-4 border-primary/70 pl-6"
                >
                  <div className="mb-3 flex items-center gap-1.5">
                    <SparklesIcon className="size-3.5 text-primary" />
                    <span className="text-xs font-medium uppercase tracking-[0.14em] text-primary">
                      要約
                    </span>
                  </div>
                  <Markdown className="text-lg text-foreground/80 [&_p]:my-3 [&_p]:leading-8">
                    {note.summary}
                  </Markdown>
                </section>

                <section id="content" className="scroll-mt-8">
                  <div className="mb-4 flex items-center gap-2">
                    <FileTextIcon className="size-4 text-muted-foreground" />
                    <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                      内容
                    </h2>
                  </div>
                  <Markdown variant="article">{note.content}</Markdown>
                </section>

                {note.aspect_map && note.aspect_map.aspects?.length > 0 && (
                  <NoteAspectMap
                    aspectMap={note.aspect_map}
                    intake={note.intake}
                  />
                )}

                <NoteRevisions revisions={revisions} />
              </>
            )}
          </main>

          <aside
            id="feedback"
            className="scroll-mt-8 lg:sticky lg:top-8 lg:self-start"
          >
            <div className="mb-4 flex items-center gap-2">
              <MessageSquareIcon className="size-4 text-muted-foreground" />
              <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                フィードバック
              </h2>
            </div>
            <NoteFeedbackPanel noteId={note.id} feedbacks={feedbacks} />
          </aside>
        </div>
      </div>
    </div>
  );
}
