import { describe, expect, it } from "vitest";

import nextConfig from "@/next.config";
import sitemap from "@/app/sitemap";

describe("sign-up route", () => {
  it("redirects permanently to /sign-in", async () => {
    const redirects = await nextConfig.redirects!();
    expect(redirects).toContainEqual({
      source: "/sign-up",
      destination: "/sign-in",
      permanent: true,
    });
  });

  it("is not listed in the sitemap", () => {
    expect(sitemap().map((entry) => entry.url)).not.toContainEqual(
      expect.stringContaining("/sign-up"),
    );
  });
});
