import { describe, it, expect } from "vitest";
import { foldByCollection, targetForName } from "@/lib/collections";

const note = (id: string, collection_id: string | null = null) => ({
  id,
  collection_id,
});

describe("foldByCollection", () => {
  it("folds notes of the same collection into one row at the first note's position", () => {
    const items = foldByCollection(
      [note("a", "c1"), note("b"), note("c", "c1")],
      { c1: "Linuxのしくみ" },
    );

    expect(items).toEqual([
      {
        kind: "collection",
        collectionId: "c1",
        name: "Linuxのしくみ",
        notes: [note("a", "c1"), note("c", "c1")],
      },
      { kind: "note", note: note("b") },
    ]);
  });

  it("keeps notes whose collection name is unknown as plain notes", () => {
    expect(foldByCollection([note("a", "gone")], {})).toEqual([
      { kind: "note", note: note("a", "gone") },
    ]);
  });
});

describe("targetForName", () => {
  it("prefers the existing collection with the same name", () => {
    const collections = [
      { id: "c1", name: "A", note_count: 0, created_at: "", updated_at: "" },
    ];
    expect(targetForName(" A ", collections)).toEqual({ collectionId: "c1" });
    expect(targetForName("B", collections)).toEqual({ newName: "B" });
  });
});
