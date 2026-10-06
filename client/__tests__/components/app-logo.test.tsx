import { readFileSync } from "node:fs";
import path from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppLogo } from "@/components/brand/app-logo";

function shapes(markup: string): string[] {
  return [...markup.matchAll(/<(rect|path|circle|g)\b([^>]*)>/g)].map(
    ([, tag, attrs]) =>
      tag +
      [
        ...attrs.matchAll(
          /\b(x|y|width|height|rx|r|cx|cy|d|transform|fill)="([^"]*)"/g,
        ),
      ]
        .map(([, k, v]) => `${k}=${v.toUpperCase()}`)
        .join(" "),
  );
}

describe("AppLogo", () => {
  it("is hidden from assistive technology", () => {
    const { container } = render(<AppLogo />);
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("draws the same shapes and colors as the favicon", () => {
    const favicon = readFileSync(
      path.resolve(__dirname, "../../app/icon.svg"),
      "utf8",
    );
    const { container } = render(<AppLogo />);
    expect(shapes(favicon)).not.toHaveLength(0);
    expect(shapes(container.innerHTML)).toEqual(shapes(favicon));
  });
});
