import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { VoiceStatusRow } from "@/components/chat/voice-status-row";

describe("VoiceStatusRow", () => {
  it("stays in the layout, empty, so that screen readers announce what appears in it", () => {
    render(<VoiceStatusRow status="idle" />);

    const row = screen.getByRole("status");
    expect(row).toBeEmptyDOMElement();
    expect(row).not.toHaveClass("empty:hidden");
    expect(row).not.toHaveClass("hidden");
  });

  it("asks the user to allow the microphone", () => {
    render(<VoiceStatusRow status="starting" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "マイクの許可を待っています…",
    );
  });

  it("says it is transcribing", () => {
    render(<VoiceStatusRow status="transcribing" />);

    expect(screen.getByRole("status")).toHaveTextContent("文字起こし中…");
  });

  it("says nothing while recording or stopping", () => {
    const { rerender } = render(<VoiceStatusRow status="recording" />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();

    rerender(<VoiceStatusRow status="stopping" />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
