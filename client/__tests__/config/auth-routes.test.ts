import { describe, expect, it } from "vitest";

import nextConfig from "@/next.config";
import sitemap from "@/app/sitemap";

describe("auth routes", () => {
  it("does not redirect /sign-up", async () => {
    const redirects = (await nextConfig.redirects?.()) ?? [];
    expect(redirects.map((redirect) => redirect.source)).not.toContain(
      "/sign-up",
    );
  });

  it("lists both entry pages in the sitemap", () => {
    const urls = sitemap().map((entry) => entry.url);
    expect(urls).toContainEqual(expect.stringMatching(/\/sign-in$/));
    expect(urls).toContainEqual(expect.stringMatching(/\/sign-up$/));
  });
});
