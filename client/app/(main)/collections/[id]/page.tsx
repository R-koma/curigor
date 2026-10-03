import Link from "next/link";
import { headers } from "next/headers";
import { RotateCcwIcon } from "lucide-react";
import { fetchAPI, getToken } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { CollectionActions } from "@/components/collections/collection-actions";
import type { CollectionDetail } from "@/lib/collections";

export const dynamic = "force-dynamic";

export default async function CollectionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const collection = await fetchAPI<CollectionDetail>(
    `/api/collections/${id}`,
    { token },
  );

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-l-4 border-muted-foreground/40 pl-4">
        <h1 className="text-2xl font-bold">{collection.name}</h1>
        <CollectionActions
          collectionId={collection.id}
          name={collection.name}
        />
      </div>

      <section className="mb-10">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          ノート（{collection.notes.length}件）
        </h2>
        <ol className="space-y-2">
          {collection.notes.map((note) => (
            <li key={note.id}>
              <Link
                href={`/notes/${note.id}`}
                className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3 hover:border-foreground/20"
              >
                <span className="truncate font-medium">{note.topic}</span>
                <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                  <RotateCcwIcon className="h-3.5 w-3.5" />
                  {note.review_count}回
                  {note.is_established && (
                    <Badge variant="secondary">定着</Badge>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
