import { headers } from "next/headers";

export const dynamic = "force-dynamic";
import { fetchAPI, getToken } from "@/lib/api";
import { Markdown } from "@/components/ui/markdown";
import { NoteDates, NoteHeader } from "@/components/notes/note-header";
import { NoteReviewBar } from "@/components/notes/note-review-bar";
import { UsageHint } from "@/components/hints/usage-hint";
import { NoteFeedbackSummary } from "@/components/notes/note-feedback-summary";
import { NoteFeedbackPanel } from "@/components/notes/note-feedback-panel";
import { NoteAspectMap } from "@/components/notes/note-aspect-map";
import type { AspectMap } from "@/lib/aspect-map";
import { NoteCollectionPicker } from "@/components/notes/note-collection-picker";
import { NoteEditForm } from "@/components/notes/note-edit-form";
import { NoteLinks } from "@/components/notes/note-links";
import type { NoteLink } from "@/lib/note-links";
import {
  NoteRevisions,
  type NoteRevision,
} from "@/components/notes/note-revisions";
import type { IntakeSummary } from "@/hooks/use-chat-websocket";
import { newestFirst, type Feedback } from "@/lib/feedback";
import {
  NoteTabBar,
  NoteTabSection,
  NoteTabsProvider,
} from "@/components/notes/note-tabs";
import { initialNoteTab, type NoteTab } from "@/lib/note-tabs";
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
  searchParams: Promise<{ edit?: string; feedback?: string }>;
}) {
  const { id } = await params;
  const { edit, feedback: feedbackParam } = await searchParams;
  const isEditing = edit === "1";
  const justUpdated = feedbackParam === "updated";
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const [note, { feedbacks }, { revisions }, { links }] = await Promise.all([
    fetchAPI(`/api/notes/${id}`, { token }) as Promise<Note>,
    fetchAPI(`/api/notes/${id}/feedbacks`, { token }) as Promise<{
      feedbacks: Feedback[];
    }>,
    fetchAPI(`/api/notes/${id}/revisions`, { token }) as Promise<{
      revisions: NoteRevision[];
    }>,
    (
      fetchAPI(`/api/notes/${id}/links`, { token }) as Promise<{
        links: NoteLink[];
      }>
    ).catch(() => ({ links: [] as NoteLink[] })),
  ]);

  const aspectMap = note.aspect_map?.aspects?.length ? note.aspect_map : null;
  const tabControls: Record<NoteTab, string[]> = {
    note: [
      "summary",
      "content",
      ...(revisions.length > 0 ? ["revisions"] : []),
    ],
    understanding: ["feedback", ...(aspectMap ? ["aspect-map"] : [])],
    connections: ["collection", ...(links.length > 0 ? ["links"] : [])],
  };
  const latestFeedback = newestFirst(feedbacks)[0] ?? null;
  const suggestedLinkCount = links.filter(
    (link) => link.status === "suggested",
  ).length;
  const feedbackBody = (
    <>
      <div className="mb-4 flex items-center gap-2">
        <MessageSquareIcon className="size-4 text-muted-foreground" />
        <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          フィードバック
        </h2>
      </div>
      <NoteFeedbackPanel
        noteId={note.id}
        feedbacks={feedbacks}
        justUpdated={justUpdated}
        aspectMap={isEditing ? null : aspectMap}
      />
    </>
  );
  const asideClassName =
    "scroll-mt-8 lg:sticky lg:top-8 lg:max-h-[calc(100vh-4rem)] lg:self-start lg:overflow-y-auto";
  const sectionLinkClassName =
    "text-muted-foreground transition-colors hover:text-foreground";

  return (
    <NoteTabsProvider initialTab={initialNoteTab(feedbackParam)}>
      <div className="min-h-full bg-background">
        <div className="mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-12">
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
          {!isEditing && <UsageHint id="note_detail" className="mb-6" />}
          {!isEditing && (
            <NoteTabBar
              controls={tabControls}
              understandingLevel={latestFeedback?.understanding_level ?? null}
              suggestedLinkCount={suggestedLinkCount}
            />
          )}
          {!isEditing && (
            <NoteTabSection tab="connections" id="collection">
              <NoteCollectionPicker
                noteId={note.id}
                collectionId={note.collection_id}
                suggestedCollection={note.suggested_collection}
              />
            </NoteTabSection>
          )}

          {!isEditing && <NoteFeedbackSummary feedbacks={feedbacks} />}

          {!isEditing && (
            <nav
              aria-label="セクション"
              className="mb-10 flex flex-wrap gap-x-6 gap-y-2 border-b border-border pb-4 text-sm max-md:hidden"
            >
              <a href="#summary" className={sectionLinkClassName}>
                要約
              </a>
              <a href="#content" className={sectionLinkClassName}>
                内容
              </a>
              {aspectMap && (
                <a href="#aspect-map" className={sectionLinkClassName}>
                  観点マップ
                </a>
              )}
              {revisions.length > 0 && (
                <a href="#revisions" className={sectionLinkClassName}>
                  復習で深まった点
                </a>
              )}
              {links.length > 0 && (
                <a href="#links" className={sectionLinkClassName}>
                  関連するノート
                </a>
              )}
              <a href="#feedback" className={sectionLinkClassName}>
                フィードバック
              </a>
            </nav>
          )}

          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-12">
            <main
              data-slot="note-main"
              className={
                isEditing
                  ? "min-w-0 space-y-10"
                  : "min-w-0 max-md:contents md:space-y-10"
              }
            >
              {isEditing ? (
                <NoteEditForm
                  noteId={note.id}
                  initialTopic={note.topic}
                  initialSummary={note.summary ?? ""}
                  initialContent={note.content}
                />
              ) : (
                <>
                  <NoteTabSection tab="note">
                    <section
                      id="summary"
                      className="scroll-mt-8 rounded-lg bg-brand-soft p-4 max-md:scroll-mt-14 md:rounded-none md:border-l-4 md:border-primary/70 md:bg-transparent md:p-0 md:pl-6"
                    >
                      <div className="mb-3 flex items-center gap-1.5">
                        <SparklesIcon className="size-3.5 text-primary" />
                        <span className="text-xs font-medium uppercase tracking-[0.14em] text-primary">
                          要約
                        </span>
                      </div>
                      <Markdown className="text-base text-foreground/80 md:text-lg [&_p]:my-3 [&_p]:leading-8">
                        {note.summary}
                      </Markdown>
                    </section>
                  </NoteTabSection>

                  <NoteTabSection tab="note">
                    <section
                      id="content"
                      className="scroll-mt-8 max-md:scroll-mt-14"
                    >
                      <div className="mb-4 flex items-center gap-2">
                        <FileTextIcon className="size-4 text-muted-foreground" />
                        <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                          内容
                        </h2>
                      </div>
                      <Markdown variant="article">{note.content}</Markdown>
                    </section>
                  </NoteTabSection>

                  {aspectMap && (
                    <NoteTabSection tab="understanding">
                      <NoteAspectMap
                        aspectMap={aspectMap}
                        intake={note.intake}
                      />
                    </NoteTabSection>
                  )}

                  {revisions.length > 0 && (
                    <NoteTabSection tab="note">
                      <NoteRevisions revisions={revisions} />
                    </NoteTabSection>
                  )}

                  {links.length > 0 && (
                    <NoteTabSection tab="connections">
                      <NoteLinks noteId={note.id} links={links} />
                    </NoteTabSection>
                  )}

                  <NoteTabSection tab="note" className="md:hidden">
                    <p className="flex gap-3 text-xs text-muted-foreground">
                      <NoteDates
                        createdAt={note.created_at}
                        updatedAt={note.updated_at}
                      />
                    </p>
                  </NoteTabSection>
                </>
              )}
            </main>

            {isEditing ? (
              <aside id="feedback" className={asideClassName}>
                {feedbackBody}
              </aside>
            ) : (
              <NoteTabSection
                tab="understanding"
                as="aside"
                id="feedback"
                className={`${asideClassName} max-md:-order-1 max-md:scroll-mt-14`}
              >
                {feedbackBody}
              </NoteTabSection>
            )}
          </div>
        </div>
        {!isEditing && <NoteReviewBar noteId={note.id} />}
      </div>
    </NoteTabsProvider>
  );
}
