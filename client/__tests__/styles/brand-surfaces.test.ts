import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

function source(file: string): string {
  return readFileSync(path.resolve(__dirname, "../..", file), "utf8");
}

describe("opengraph-image", () => {
  const og = source("app/opengraph-image.tsx").toLowerCase();

  it.each(["#1e1b4b", "#312e81", "#4338ca", "#c7d2fe"])(
    "no longer uses the indigo %s",
    (hex) => {
      expect(og).not.toContain(hex);
    },
  );

  it.each(["#172554", "#1e3a8a", "#1d4ed8", "#bfdbfe"])(
    "uses the blue %s",
    (hex) => {
      expect(og).toContain(hex);
    },
  );
});

describe("landing CTA", () => {
  it("keeps the button text on a color that does not change with the theme", () => {
    expect(source("components/landing/landing-cta.tsx")).toContain(
      "text-brand-deep",
    );
  });
});

describe("dashboard new learning button", () => {
  const dashboard = source("app/(main)/dashboard/page.tsx");

  it("takes its blue from the brand-strong token", () => {
    expect(dashboard).toContain("bg-brand-strong");
    expect(dashboard).toContain("hover:bg-brand-strong/90");
    expect(dashboard).toContain("[a]:hover:bg-brand-strong/90");
    expect(dashboard).not.toContain("bg-brand-deep");
  });

  it("does not rotate the plus icon on hover", () => {
    expect(dashboard).not.toContain("rotate-90");
    expect(dashboard).not.toContain("group-hover/button");
  });
});
