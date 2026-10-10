import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  NoteTabBar,
  NoteTabSection,
  NoteTabsProvider,
} from "@/components/notes/note-tabs";
import type { NoteTab } from "@/lib/note-tabs";

const CONTROLS: Record<NoteTab, string[]> = {
  note: ["summary", "content"],
  understanding: ["feedback", "aspect-map"],
  connections: ["collection"],
};

function renderTabs({
  initialTab = "note",
  understandingLevel = "medium",
  suggestedLinkCount = 0,
}: {
  initialTab?: NoteTab;
  understandingLevel?: string | null;
  suggestedLinkCount?: number;
} = {}) {
  return render(
    <NoteTabsProvider initialTab={initialTab}>
      <NoteTabBar
        controls={CONTROLS}
        understandingLevel={understandingLevel}
        suggestedLinkCount={suggestedLinkCount}
      />
      <NoteTabSection tab="note" id="summary">
        要約
      </NoteTabSection>
      <NoteTabSection tab="understanding" as="aside" id="feedback">
        評価
      </NoteTabSection>
      <NoteTabSection tab="connections" id="collection">
        まとめノート
      </NoteTabSection>
    </NoteTabsProvider>,
  );
}

const section = (id: string) => document.getElementById(id)!;
const hiddenOnPhones = (id: string) =>
  section(id).classList.contains("max-md:hidden");

const scrollIntoView = vi.fn();

beforeEach(() => {
  scrollIntoView.mockClear();
  Element.prototype.scrollIntoView = scrollIntoView;
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("NoteTabs", () => {
  it("shows only the initial tab's sections on phones", () => {
    renderTabs();
    expect(screen.getByRole("tab", { name: "ノート" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(hiddenOnPhones("summary")).toBe(false);
    expect(hiddenOnPhones("feedback")).toBe(true);
    expect(hiddenOnPhones("collection")).toBe(true);
  });

  it("never hides sections from md up", () => {
    renderTabs();
    for (const id of ["summary", "feedback", "collection"]) {
      expect(section(id).classList.contains("hidden")).toBe(false);
    }
  });

  it("renders the aside as an aside", () => {
    renderTabs();
    expect(section("feedback").tagName).toBe("ASIDE");
  });

  it("switches the visible sections when a tab is chosen", () => {
    renderTabs();
    fireEvent.click(screen.getByRole("tab", { name: /理解度/ }));
    expect(screen.getByRole("tab", { name: /理解度/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(hiddenOnPhones("feedback")).toBe(false);
    expect(hiddenOnPhones("summary")).toBe(true);
  });

  it("starts on the tab the server chose", () => {
    renderTabs({ initialTab: "understanding" });
    expect(hiddenOnPhones("feedback")).toBe(false);
  });

  it("points each tab at its sections", () => {
    renderTabs();
    expect(screen.getByRole("tab", { name: "ノート" })).toHaveAttribute(
      "aria-controls",
      "summary content",
    );
  });

  it("marks the understanding tab with the latest level", () => {
    renderTabs({ understandingLevel: "medium" });
    expect(screen.getByRole("tab", { name: /理解度/ })).toHaveTextContent(
      "理解度中",
    );
  });

  it("leaves the understanding tab unmarked without feedback", () => {
    renderTabs({ understandingLevel: null });
    expect(screen.getByRole("tab", { name: /理解度/ })).toHaveTextContent(
      /^理解度$/,
    );
  });

  it("counts unanswered connection suggestions", () => {
    renderTabs({ suggestedLinkCount: 2 });
    expect(
      screen.getByRole("tab", { name: /つながり\s*2\s*件の候補/ }),
    ).toBeInTheDocument();
  });

  it("leaves the connections tab unmarked without suggestions", () => {
    renderTabs({ suggestedLinkCount: 0 });
    expect(screen.getByRole("tab", { name: /つながり/ })).toHaveTextContent(
      /^つながり$/,
    );
  });

  it("moves between tabs with the arrow keys and wraps around", () => {
    renderTabs();
    const note = screen.getByRole("tab", { name: "ノート" });
    fireEvent.keyDown(note, { key: "ArrowRight" });
    const understanding = screen.getByRole("tab", { name: /理解度/ });
    expect(understanding).toHaveAttribute("aria-selected", "true");
    expect(understanding).toHaveFocus();
    expect(understanding).toHaveAttribute("tabindex", "0");
    expect(note).toHaveAttribute("tabindex", "-1");

    fireEvent.keyDown(understanding, { key: "ArrowLeft" });
    fireEvent.keyDown(screen.getByRole("tab", { name: "ノート" }), {
      key: "ArrowLeft",
    });
    expect(screen.getByRole("tab", { name: /つながり/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("opens the tab of the section in the URL hash", () => {
    window.history.replaceState(null, "", "/#feedback");
    renderTabs();
    expect(hiddenOnPhones("feedback")).toBe(false);
    expect(scrollIntoView).toHaveBeenCalled();
  });

  it("stays on the initial tab for a malformed hash", () => {
    window.history.replaceState(null, "", "/#%E0%A4%A");
    renderTabs();
    expect(hiddenOnPhones("summary")).toBe(false);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("follows hash changes after mount", () => {
    renderTabs();
    window.history.replaceState(null, "", "/#collection");
    fireEvent(window, new HashChangeEvent("hashchange"));
    expect(hiddenOnPhones("collection")).toBe(false);
  });

  it("brings the tabs back to the top after switching from far down", () => {
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(
      function (this: Element) {
        const top = this.getAttribute("role") === "tablist" ? 56 : -400;
        return { top } as DOMRect;
      },
    );
    renderTabs();
    fireEvent.click(screen.getByRole("tab", { name: /理解度/ }));
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("does not scroll when the tabs are already in view", () => {
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(
      () => ({ top: 120 }) as DOMRect,
    );
    renderTabs();
    fireEvent.click(screen.getByRole("tab", { name: /理解度/ }));
    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});
