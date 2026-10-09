import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import { NoteList } from "@/components/notes/note-list";
import type { CollectionSummary } from "@/lib/collections";
import { PAGE_TITLES } from "@/lib/nav-links";
import { PageHeading } from "@/components/layout/page-heading";

interface NoteResponse {
  id: string;
  topic: string;
  content: string;
  summary: string | null;
  status: string;
  category: string | null;
  collection_id: string | null;
  created_at: string;
  updated_at: string;
  review_count: number;
}

export default async function NotesPage() {
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const [{ notes }, { collections }] = await Promise.all([
    fetchAPI<{ notes: NoteResponse[] }>("/api/notes", { token }),
    fetchAPI<{ collections: CollectionSummary[] }>("/api/collections", {
      token,
    }).catch(() => ({ collections: [] as CollectionSummary[] })),
  ]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <PageHeading
          title={PAGE_TITLES["/notes"]}
          description={`ノート ${notes.length} 件`}
        />
      </div>
      <NoteList notes={notes} collections={collections} />
    </div>
  );
}
