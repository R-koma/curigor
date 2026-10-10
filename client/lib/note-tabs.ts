export type NoteTab = "note" | "understanding" | "connections";

export const NOTE_TABS: readonly NoteTab[] = [
  "note",
  "understanding",
  "connections",
];

export const NOTE_TAB_LABELS: Record<NoteTab, string> = {
  note: "ノート",
  understanding: "理解度",
  connections: "つながり",
};

const TAB_BY_ID: Record<string, NoteTab> = {
  summary: "note",
  content: "note",
  revisions: "note",
  feedback: "understanding",
  "aspect-map": "understanding",
  collection: "connections",
  links: "connections",
};

export function initialNoteTab(feedbackParam: string | undefined): NoteTab {
  return feedbackParam === "updated" ? "understanding" : "note";
}

export function tabForHash(hash: string): NoteTab | null {
  let id: string;
  try {
    id = decodeURIComponent(hash.replace(/^#/, ""));
  } catch {
    return null;
  }
  if (Object.hasOwn(TAB_BY_ID, id)) return TAB_BY_ID[id];
  if (id.startsWith("aspect-")) return "understanding";
  return null;
}
