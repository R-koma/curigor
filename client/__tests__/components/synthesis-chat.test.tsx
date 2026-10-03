import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SynthesisChat } from "@/components/collections/synthesis-chat";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const hookState = {
  messages: [] as { role: "user" | "assistant"; content: string }[],
  isLoading: false,
  isSessionEnded: false,
  isGeneratingNote: false,
  isSynthesisSaved: false,
  error: null as string | null,
  editingMessage: null as string | null,
  startSynthesis: vi.fn(),
  sendMessage: vi.fn(),
  endSession: vi.fn(),
  cancelLastMessage: vi.fn(),
  clearEditingMessage: vi.fn(),
};
vi.mock("@/hooks/use-chat-websocket", () => ({
  useChatWebSocket: () => hookState,
}));

beforeEach(() => {
  push.mockReset();
  hookState.messages = [];
  hookState.isSynthesisSaved = false;
  hookState.startSynthesis.mockReset();
  hookState.sendMessage.mockReset();
  hookState.endSession.mockReset();
});

describe("SynthesisChat", () => {
  it("starts the dialogue for the collection", async () => {
    render(<SynthesisChat collectionId="c1" collectionName="Linuxのしくみ" />);

    await userEvent.click(screen.getByRole("button", { name: "説明を始める" }));

    expect(hookState.startSynthesis).toHaveBeenCalledWith("c1");
  });

  it("returns to the collection once the insights are saved", () => {
    hookState.isSynthesisSaved = true;
    render(<SynthesisChat collectionId="c1" collectionName="Linuxのしくみ" />);

    expect(push).toHaveBeenCalledWith("/collections/c1#synthesis");
  });
});
