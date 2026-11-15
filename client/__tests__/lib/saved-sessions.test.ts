import { describe, expect, it } from "vitest";
import {
  daysUntilExpiry,
  EXPIRY_WARNING_DAYS,
  findSavedReview,
  savedSessionHref,
  type SavedSession,
} from "@/lib/saved-sessions";

function make(overrides: Partial<SavedSession> = {}): SavedSession {
  return {
    session_id: "s1",
    session_type: "learning",
    topic: null,
    note_id: null,
    last_activity_at: "2026-11-15T00:00:00Z",
    expires_at: "2026-11-20T00:00:00Z",
    last_assistant_excerpt: null,
    progress: null,
    ...overrides,
  };
}

describe("savedSessionHref", () => {
  it("学習とインプットは /learn に戻る", () => {
    expect(savedSessionHref(make())).toBe("/learn?session=s1");
    expect(savedSessionHref(make({ session_type: "explore" }))).toBe(
      "/learn?session=s1",
    );
  });

  it("復習は note_id があれば復習画面に戻る", () => {
    expect(
      savedSessionHref(make({ session_type: "review", note_id: "n1" })),
    ).toBe("/review/n1?session=s1");
  });

  it("note_id の無い復習は null", () => {
    expect(savedSessionHref(make({ session_type: "review" }))).toBeNull();
  });
});

describe("findSavedReview", () => {
  it("同じ note_id の復習だけを返す", () => {
    const review = make({
      session_id: "r1",
      session_type: "review",
      note_id: "n1",
    });
    const learning = make({ session_id: "l1", note_id: "n1" });
    const other = make({
      session_id: "r2",
      session_type: "review",
      note_id: "n2",
    });
    expect(findSavedReview([learning, other, review], "n1")).toBe(review);
    expect(findSavedReview([learning, other], "n1")).toBeNull();
  });
});

describe("daysUntilExpiry", () => {
  const now = new Date("2026-11-15T00:00:00Z");

  it("切り上げの日数を返す", () => {
    const expires = new Date(now.getTime() + 4.2 * 86_400_000).toISOString();
    expect(daysUntilExpiry(expires, now)).toBe(5);
  });

  it("過ぎていれば 0", () => {
    expect(daysUntilExpiry("2026-11-10T00:00:00Z", now)).toBe(0);
  });

  it("警告は 7 日前から", () => {
    expect(EXPIRY_WARNING_DAYS).toBe(7);
  });
});
