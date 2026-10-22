import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LearnPage from "@/app/(main)/learn/page";

const replace = vi.fn();
const startLearning = vi.fn();
const startExplore = vi.fn();
const resumeSession = vi.fn();
const loadResumableMessages = vi.fn();
const fetchActiveSession = vi.fn();
const toastInfo = vi.fn();
let currentSearch = "";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(currentSearch),
}));
vi.mock("@/hooks/use-chat-websocket", () => ({
  useChatWebSocket: () => ({
    messages: [],
    isConnected: false,
    isReconnecting: false,
    isLoading: false,
    isSessionEnded: false,
    isGeneratingNote: false,
    generatedNote: null,
    endConfirmation: null,
    noteSkipped: false,
    dismissEndConfirmation: vi.fn(),
    error: null,
    errorCode: null,
    editingMessage: null,
    editingRawTranscript: null,
    editingAutoSent: false,
    speechBus: {},
    sessionId: null,
    progress: null,
    sessionType: null,
    generatedStudyMemo: null,
    startExplore,
    sessionTopic: null,
    startLearning,
    resumeSession,
    sendMessage: vi.fn(),
    editTopic: vi.fn(),
    endSession: vi.fn(),
    cancelLastMessage: vi.fn(),
    clearEditingMessage: vi.fn(),
    resetSession: vi.fn(),
  }),
}));
vi.mock("@/hooks/use-voice-conversation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/use-voice-conversation")>()),
  useVoiceConversation: () => ({
    status: "off",
    stop: vi.fn(),
    error: null,
    speechError: null,
  }),
}));
vi.mock("@/hooks/use-error-toast", () => ({ useErrorToast: () => {} }));
vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({ setNavbarCenter: vi.fn() }),
}));
vi.mock("@/context/usage-hints-context", () => ({
  useActiveHint: () => null,
}));
vi.mock("@/components/hints/usage-hint", () => ({ UsageHint: () => null }));
vi.mock("@/components/chat/chat-input", () => ({ ChatInput: () => null }));
vi.mock("sonner", () => ({ toast: { info: (m: string) => toastInfo(m) } }));
vi.mock("@/lib/active-session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/active-session")>()),
  fetchActiveSession: () => fetchActiveSession(),
}));
vi.mock("@/lib/api", () => ({
  getToken: async () => "token",
  fetchAPI: vi.fn(async (path: string) => {
    if (path.startsWith("/api/study-memos/")) {
      return { id: "m1", topic: "改元" };
    }
    return null;
  }),
}));
vi.mock("@/lib/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/session")>()),
  loadResumableMessages: (id: string) => loadResumableMessages(id),
}));

const activeReview = {
  session_id: "s0",
  session_type: "review",
  status: "in_progress",
  started_at: "2026-10-19T12:13:13Z",
  topic: "元号の歴史",
  note_id: "n1",
};

async function renderPage() {
  await act(async () => {
    render(<LearnPage />);
  });
}

describe("LearnPage の開始と進行中のセッション", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("改善点からの理解するは、進行中のセッションが無ければそのまま始める", async () => {
    currentSearch = "note=n1&feedback=f1&item=2";
    fetchActiveSession.mockResolvedValue(null);
    await renderPage();
    expect(startExplore).toHaveBeenCalledWith("", {
      source: { note_id: "n1", feedback_id: "f1", improvement_index: 2 },
    });
  });

  it("改善点からの理解するをキャンセルすると、始めずにノートへ戻る", async () => {
    currentSearch = "note=n1&feedback=f1&item=2";
    fetchActiveSession.mockResolvedValue(activeReview);
    await renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "キャンセル" }),
    );
    expect(startExplore).not.toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith("/notes/n1");
  });

  it("学習メモからの学習は、確かめてから始める", async () => {
    currentSearch = "memo=m1";
    fetchActiveSession.mockResolvedValue(activeReview);
    await renderPage();
    expect(startLearning).not.toHaveBeenCalled();
    await userEvent.click(
      await screen.findByRole("button", { name: "終了して始める" }),
    );
    expect(startLearning).toHaveBeenCalledWith("改元", {
      study_memo_id: "m1",
    });
  });

  it("学習メモからの学習をキャンセルすると、学習メモへ戻る", async () => {
    currentSearch = "memo=m1";
    fetchActiveSession.mockResolvedValue(activeReview);
    await renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "キャンセル" }),
    );
    expect(startLearning).not.toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith("/study-memos/m1");
  });

  it("終了したセッションの URL を開くと、知らせて開始画面へ移る", async () => {
    currentSearch = "session=s1";
    loadResumableMessages.mockResolvedValue({
      sessionType: "explore",
      status: "abandoned",
      noteId: null,
      topic: "改元",
      messages: [],
    });
    await renderPage();
    expect(resumeSession).not.toHaveBeenCalled();
    expect(toastInfo).toHaveBeenCalledWith(
      "このセッションは終了しています。新しいセッションを始めると、進行中のセッションは終了します",
    );
    expect(replace).toHaveBeenCalledWith("/learn");
  });
});
