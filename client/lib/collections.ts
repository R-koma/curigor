import { fetchAPI } from "@/lib/api";

export interface CollectionSummary {
  id: string;
  name: string;
  note_count: number;
  created_at: string;
  updated_at: string;
}

export type CollectionTarget =
  | { collectionId: string }
  | { newName: string }
  | null;

export async function listCollections(): Promise<CollectionSummary[]> {
  const { collections } = await fetchAPI<{ collections: CollectionSummary[] }>(
    "/api/collections",
  );
  return collections;
}

export async function assignNoteCollection(
  noteId: string,
  target: CollectionTarget,
): Promise<void> {
  const body =
    target === null
      ? {}
      : "collectionId" in target
        ? { collection_id: target.collectionId }
        : { new_collection_name: target.newName };
  await fetchAPI(`/api/notes/${noteId}/collection`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function dismissCollectionSuggestion(
  noteId: string,
): Promise<void> {
  await fetchAPI(`/api/notes/${noteId}/collection-suggestion`, {
    method: "DELETE",
  });
}

export function targetForName(
  name: string,
  collections: readonly CollectionSummary[],
): CollectionTarget {
  const existing = collections.find((c) => c.name === name.trim());
  return existing ? { collectionId: existing.id } : { newName: name.trim() };
}
