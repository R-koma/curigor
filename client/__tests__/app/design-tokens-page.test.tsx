import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import DesignTokensPage from "@/app/design-tokens/page";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("design tokens page", () => {
  it("lists every token section outside production", () => {
    render(<DesignTokensPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "デザイントークン" }),
    ).toBeInTheDocument();
    for (const name of [
      "色",
      "トーン",
      "ボタン",
      "バッジ",
      "文字サイズ",
      "重なり順",
      "グラデーション",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name }),
      ).toBeInTheDocument();
    }
  });

  it("responds with not found in production", () => {
    vi.stubEnv("NODE_ENV", "production");
    let thrown: unknown;
    try {
      DesignTokensPage();
    } catch (error) {
      thrown = error;
    }
    expect((thrown as { digest?: string } | undefined)?.digest).toMatch(
      /404|NOT_FOUND/,
    );
  });
});
