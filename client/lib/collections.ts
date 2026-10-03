import { fetchAPI } from "@/lib/api";

export interface CollectionSummary {
  id: string;
  name: string;
  note_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionNote {
  id: string;
  topic: string;
  summary: string | null;
  status: string;
  created_at: string;
  review_count: number;
  is_established: boolean;
}

export interface CollectionDetail {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  notes: CollectionNote[];
}

export type NoteListItem<T> =
  | { kind: "note"; note: T }
  | { kind: "collection"; collectionId: string; name: string; notes: T[] };

export function foldByCollection<T extends { collection_id?: string | null }>(
  notes: readonly T[],
  names: Readonly<Record<string, string>>,
): NoteListItem<T>[] {
  const items: NoteListItem<T>[] = [];
  const groups = new Map<string, T[]>();
  for (const note of notes) {
    const id = note.collection_id;
    if (!id || !(id in names)) {
      items.push({ kind: "note", note });
      continue;
    }
    const group = groups.get(id);
    if (group) {
      group.push(note);
      continue;
    }
    const created = [note];
    groups.set(id, created);
    items.push({
      kind: "collection",
      collectionId: id,
      name: names[id],
      notes: created,
    });
  }
  return items;
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

export interface SynthesisConnection {
  id: string;
  title: string;
  note_ids: string[];
  explanation: string;
  question: string;
}

export interface Synthesis {
  collection_id: string;
  content: string;
  connections: SynthesisConnection[];
  contradictions: { note_ids: string[]; description: string }[];
  gaps: string[];
  generated_at: string;
  is_stale: boolean;
  changed_note_ids: string[];
  insights: {
    id: string;
    connection_title: string;
    content: string;
    created_at: string;
  }[];
}

export async function generateSynthesis(
  collectionId: string,
): Promise<Synthesis> {
  return fetchAPI<Synthesis>(`/api/collections/${collectionId}/synthesis`, {
    method: "POST",
  });
}
