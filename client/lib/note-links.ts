import { fetchAPI } from "@/lib/api";

export interface LinkedNote {
  id: string;
  topic: string;
  summary: string | null;
  collection_id: string | null;
  collection_name: string | null;
}

export interface NoteLink {
  id: string;
  status: "suggested" | "accepted";
  similarity: number;
  note: LinkedNote;
}

export async function updateNoteLink(
  noteId: string,
  linkId: string,
  status: "accepted" | "dismissed",
): Promise<void> {
  await fetchAPI(`/api/notes/${noteId}/links/${linkId}`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });
}
