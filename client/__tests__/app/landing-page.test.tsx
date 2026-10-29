import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/auth-client", () => ({
  authClient: {
    useSession: () => ({ data: null, isPending: false }),
  },
}));

import Home, { metadata } from "@/app/page";
import {
  PRICING_FAQ,
  PRICING_NOTE_PHRASES,
  RELEASE_STAGE,
} from "@/components/landing/landing-copy";

describe("landing page", () => {
  it("renders a single h1 hero headline", () => {
    render(<Home />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("links to both the sign-up and sign-in pages", () => {
    const { container } = render(<Home />);
    expect(
      container.querySelectorAll('a[href="/sign-up"]').length,
    ).toBeGreaterThan(0);
    expect(
      container.querySelectorAll('a[href="/sign-in"]').length,
    ).toBeGreaterThan(0);
  });

  it("does not mention the protégé effect or make free the selling point", () => {
    const { container } = render(<Home />);
    const text = container.textContent ?? "";
    expect(text).not.toContain("プロテジェ");
    expect(text).not.toContain("無料で始める");
    expect(text).not.toContain("ずっと無料");
    const layout = readFileSync(
      path.resolve(__dirname, "../../app/layout.tsx"),
      "utf8",
    );
    for (const value of [
      metadata.description,
      String(metadata.title),
      layout,
    ]) {
      expect(value).not.toContain("プロテジェ");
      expect(value).not.toContain("無料");
    }
  });

  it("uses the same label on every sign-up link", () => {
    const { container } = render(<Home />);
    const labels = [...container.querySelectorAll('a[href="/sign-up"]')].map(
      (a) => a.textContent,
    );
    expect(new Set(labels)).toEqual(new Set(["はじめる", "新規登録"]));
  });

  it("shows both learning modes", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { level: 3, name: "説明する" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "理解する" }),
    ).toBeInTheDocument();
  });

  it("switches the sample dialogue by topic", async () => {
    render(<Home />);
    expect(
      screen.getByText(/夕焼けが赤く見えるのはなぜでしょう/),
    ).toBeVisible();

    await userEvent.click(screen.getByRole("tab", { name: "複利" }));

    expect(screen.getByText(/単利と比べて/)).toBeVisible();
    expect(screen.queryByText(/夕焼けが赤く見えるのはなぜでしょう/)).toBeNull();
  });

  it("links the in-page navigation to existing sections", () => {
    const { container } = render(<Home />);
    const nav = screen.getByRole("navigation", { name: "ページ内" });
    for (const link of within(nav).getAllByRole("link")) {
      const id = link.getAttribute("href")!.slice(1);
      expect(container.querySelector(`#${id}`)).not.toBeNull();
    }
  });

  it("shows the AI notice", () => {
    render(<Home />);
    expect(screen.getByText(/Curigor は AI です/)).toBeInTheDocument();
  });

  it("says free only for the beta period, without a card and with notice before pricing", async () => {
    const { container } = render(<Home />);
    expect(container.textContent).toContain(PRICING_NOTE_PHRASES.join(""));
    expect(screen.getByText(RELEASE_STAGE)).toBeInTheDocument();

    await userEvent.click(screen.getByText(PRICING_FAQ.question));

    expect(screen.getByText(PRICING_FAQ.answer)).toBeVisible();
  });
});
