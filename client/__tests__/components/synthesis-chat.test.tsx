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
  hookState.isSessionEnded = false;
  hookState.error = null;
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

  async function renderStarted() {
    render(<SynthesisChat collectionId="c1" collectionName="Linuxのしくみ" />);
    await userEvent.click(screen.getByRole("button", { name: "説明を始める" }));
  }

  it("shows the saving text and hides the input once ended", async () => {
    hookState.isSessionEnded = true;
    await renderStarted();

    expect(
      screen.getByText("説明をまとめに反映しています"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("offers a way back when saving fails", async () => {
    hookState.isSessionEnded = true;
    hookState.error = "ノート生成に失敗しました";
    await renderStarted();

    expect(screen.getByText("説明の反映に失敗しました。")).toBeInTheDocument();
    expect(
      screen.queryByText("ノート生成に失敗しました"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("説明をまとめに反映しています"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "テーマに戻る" })).toHaveAttribute(
      "href",
      "/collections/c1",
    );
  });

  it("lets the first answer be edited", async () => {
    hookState.messages = [
      { role: "assistant", content: "最初の質問" },
      { role: "user", content: "最初の回答" },
      { role: "assistant", content: "次の質問" },
    ];
    await renderStarted();

    await userEvent.click(screen.getByTitle("編集して再送信"));

    expect(hookState.cancelLastMessage).toHaveBeenCalled();
  });
});
