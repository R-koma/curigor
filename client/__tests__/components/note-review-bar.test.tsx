import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NoteReviewBar } from "@/components/notes/note-review-bar";

describe("NoteReviewBar", () => {
  it("starts a review of the note from the bottom of phone screens", () => {
    const { container } = render(<NoteReviewBar noteId="n1" />);
    expect(screen.getByRole("link", { name: "復習する" })).toHaveAttribute(
      "href",
      "/review/n1",
    );
    expect(container.firstElementChild).toHaveClass(
      "sticky",
      "bottom-0",
      "md:hidden",
    );
  });
});
