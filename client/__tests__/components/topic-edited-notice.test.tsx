import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TopicEditedNotice } from "@/components/chat/topic-edited-notice";

describe("TopicEditedNotice", () => {
  it("shows the edit as a single line without actions", () => {
    render(<TopicEditedNotice content="トピックを「UDP」に変更しました" />);

    expect(
      screen.getByText("トピックを「UDP」に変更しました"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
