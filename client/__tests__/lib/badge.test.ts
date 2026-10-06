import { describe, it, expect } from "vitest";
import { understandingBadge } from "@/lib/badge";

describe("understandingBadge", () => {
  it("never shows a low understanding as an error", () => {
    expect(understandingBadge("high")).toEqual({
      variant: "success",
      label: "高",
    });
    expect(understandingBadge("medium")).toEqual({
      variant: "info",
      label: "中",
    });
    expect(understandingBadge("low")).toEqual({
      variant: "warning",
      label: "低",
    });
  });

  it("falls back to the raw value for unknown levels", () => {
    expect(understandingBadge("unknown")).toEqual({
      variant: "secondary",
      label: "unknown",
    });
  });
});
