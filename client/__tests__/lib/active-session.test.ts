import { describe, expect, it } from "vitest";
import { activeSessionHref, type ActiveSession } from "@/lib/active-session";

const base: ActiveSession = {
  session_id: "s1",
  session_type: "learning",
  status: "active",
  started_at: "2026-10-10T00:00:00Z",
  topic: "二分探索",
  note_id: null,
};

describe("activeSessionHref", () => {
  it("resumes a learning session on the learn page", () => {
    expect(activeSessionHref(base)).toBe("/learn?session=s1");
  });

  it("resumes a review session on its note's review page", () => {
    expect(
      activeSessionHref({ ...base, session_type: "review", note_id: "n1" }),
    ).toBe("/review/n1?session=s1");
  });

  it("has no destination for a review session without a note", () => {
    expect(activeSessionHref({ ...base, session_type: "review" })).toBeNull();
  });
});
