import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

describe("next.config", () => {
  it("keeps the development indicator away from the account area at the bottom left of the sidebar", () => {
    expect(nextConfig.devIndicators).toEqual({ position: "top-right" });
  });
});
