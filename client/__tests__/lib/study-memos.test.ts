import { describe, it, expect } from "vitest";
import {
  exploreFromImprovementHref,
  groupStudyMemo,
  memosForImprovement,
  priorityAspectIds,
  type NoteStudyMemo,
  type StudyMemo,
  type StudyMemoAspect,
} from "@/lib/study-memos";

const aspect = (
  aspect_id: string,
  question_indices: number[] = [],
  term_indices: number[] = [],
  is_core = false,
): StudyMemoAspect => ({
  aspect_id,
  name: `観点${aspect_id}`,
  is_core,
  question_indices,
  term_indices,
});

const memo = (overview: StudyMemoAspect[], counts = [3, 3]): StudyMemo => ({
  id: "m1",
  topic: "Linux",
  source: "",
  summary: "",
  overview,
  glossary: Array.from({ length: counts[1] }, (_, i) => ({
    term: `用語${i}`,
    reading: "",
    meaning: `意味${i}`,
  })),
  questions: Array.from({ length: counts[0] }, (_, i) => ({
    question: `問${i}`,
    answer: `答${i}`,
  })),
  created_at: "2026-10-17T00:00:00Z",
});

describe("groupStudyMemo", () => {
  it("groups questions and terms under their aspects in overview order", () => {
    const groups = groupStudyMemo(
      memo([aspect("a", [2, 0], [1], true), aspect("b", [1], [0, 2])]),
    );

    expect(groups.map((g) => g.name)).toEqual(["観点a", "観点b"]);
    expect(groups[0].questions.map((q) => q.question)).toEqual(["問2", "問0"]);
    expect(groups[0].terms.map((t) => t.term)).toEqual(["用語1"]);
    expect(groups[0].isCore).toBe(true);
    expect(groups[1].terms.map((t) => t.term)).toEqual(["用語0", "用語2"]);
  });

  it("leaves out aspects with no questions or terms", () => {
    const groups = groupStudyMemo(
      memo([aspect("a", [0, 1, 2], [0, 1, 2]), aspect("b")]),
    );

    expect(groups.map((g) => g.key)).toEqual(["a"]);
  });

  it("puts unassigned questions and terms in a last group named after them", () => {
    const groups = groupStudyMemo(memo([aspect("a", [0], [0])]));

    expect(groups).toHaveLength(2);
    expect(groups[1]).toMatchObject({
      key: "other",
      name: "観点に入らなかった疑問と用語",
      isCore: false,
    });
    expect(groups[1].questions.map((q) => q.question)).toEqual(["問1", "問2"]);
    expect(groups[1].terms.map((t) => t.term)).toEqual(["用語1", "用語2"]);
  });

  it("puts everything in one group named 疑問と用語 when no aspect has indices", () => {
    const groups = groupStudyMemo(memo([aspect("a"), aspect("b")]));

    expect(groups.map((g) => g.key)).toEqual(["other"]);
    expect(groups[0].name).toBe("疑問と用語");
    expect(groups[0].questions).toHaveLength(3);
    expect(groups[0].terms).toHaveLength(3);
  });

  it("returns no groups when the memo has no questions or terms", () => {
    expect(groupStudyMemo(memo([aspect("a")], [0, 0]))).toEqual([]);
  });

  it("treats missing index fields as empty", () => {
    const old = {
      aspect_id: "a",
      name: "観点a",
      is_core: false,
    } as StudyMemoAspect;

    const groups = groupStudyMemo(memo([old]));

    expect(groups.map((g) => g.key)).toEqual(["other"]);
  });

  it("skips out-of-range and repeated indices", () => {
    const groups = groupStudyMemo(
      memo([aspect("a", [0, 9, -1], [0]), aspect("b", [0, 1], [])]),
    );

    expect(groups[0].questions.map((q) => q.question)).toEqual(["問0"]);
    expect(groups[1].questions.map((q) => q.question)).toEqual(["問1"]);
  });
});

const noteMemo = (
  id: string,
  feedback_id: string | null,
  improvement_index: number | null,
  aspect_id: string | null,
): NoteStudyMemo => ({
  id,
  topic: "Linux",
  created_at: "2026-10-18T00:00:00Z",
  feedback_id,
  improvement_index,
  aspect_id,
});

describe("memosForImprovement", () => {
  it("picks memos of that feedback item, newest first", () => {
    const memos = [
      noteMemo("a", "f1", 0, "x"),
      noteMemo("b", "f1", 1, "y"),
      noteMemo("c", "f2", 0, "z"),
      noteMemo("d", "f1", 0, null),
    ];
    expect(memosForImprovement(memos, "f1", 0).map((m) => m.id)).toEqual([
      "a",
      "d",
    ]);
  });
});

describe("priorityAspectIds", () => {
  it("only counts memos of the latest feedback with an aspect", () => {
    const memos = [
      noteMemo("a", "f1", 0, "x"),
      noteMemo("b", "f2", 0, "y"),
      noteMemo("c", "f2", 1, null),
      noteMemo("d", null, null, "w"),
    ];
    expect(priorityAspectIds(memos, "f2")).toEqual(new Set(["y"]));
    expect(priorityAspectIds(memos, null)).toEqual(new Set());
  });
});

describe("exploreFromImprovementHref", () => {
  it("builds the learn link", () => {
    expect(exploreFromImprovementHref("n1", "f1", 2)).toBe(
      "/learn?mode=explore&note=n1&feedback=f1&item=2",
    );
  });
});
