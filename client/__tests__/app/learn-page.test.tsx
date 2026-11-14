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
let hookOverrides: Record<string, unknown> = {};
const startQuestions = vi.fn(() => true);

const stableRouter = { replace, push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => stableRouter,
  useSearchParams: () => new URLSearchParams(currentSearch),
}));
const stableConversation = {
  status: "off",
  stop: vi.fn(),
  error: null,
  speechError: null,
};
const stableHook = {
  messages: [],
  isConnected: false,
  isReconnecting: false,
  isLoading: false,
  isSessionEnded: false,
  isGeneratingNote: false,
  generatedNote: null,
  endConfirmation: null,
  pendingQuestions: null,
  startQuestions,
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
};
vi.mock("@/hooks/use-chat-websocket", () => ({
  useChatWebSocket: () => ({ ...stableHook, ...hookOverrides }),
}));
vi.mock("@/hooks/use-voice-conversation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/use-voice-conversation")>()),
  useVoiceConversation: () => stableConversation,
}));
const errorToast = vi.fn();
vi.mock("@/hooks/use-error-toast", () => ({
  useErrorToast: (...args: unknown[]) => errorToast(...args),
}));
let coarsePointer = false;
vi.mock("@/hooks/use-coarse-pointer", () => ({
  useCoarsePointer: () => coarsePointer,
}));
const useSideQuestionsMock = vi.fn();
const removeByAnchorMessage = vi.fn();
const reloadSide = vi.fn();
let sideThreads: unknown[] = [];
let sideLoadFailed = false;
vi.mock("@/hooks/use-side-questions", () => ({
  useSideQuestions: (sessionId: string | null, enabled: boolean) => {
    useSideQuestionsMock(sessionId, enabled);
    return {
      threads: enabled ? sideThreads : [],
      draft: null,
      open: new Set(),
      streaming: null,
      error: null,
      loadFailed: enabled && sideLoadFailed,
      reload: reloadSide,
      startDraft: vi.fn(),
      send: vi.fn(),
      toggle: vi.fn(),
      openThread: vi.fn(),
      foldAll: vi.fn(),
      removeByAnchorMessage,
    };
  },
}));
const setNavbarCenter = vi.fn();
vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({ setNavbarCenter }),
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
    hookOverrides = {};
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

describe("LearnPage の「質問を聞く」", () => {
  const inSession = {
    isConnected: true,
    sessionId: "s1",
    sessionType: "learning",
    messages: [
      { role: "user", content: "二分探索" },
      { role: "assistant", content: "声かけ" },
      { role: "user", content: "真ん中と比べます" },
      { role: "assistant", content: "受け止め" },
    ],
  };
  const button = () => screen.queryByRole("button", { name: /^質問を聞く/ });

  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    hookOverrides = {};
    fetchActiveSession.mockResolvedValue(null);
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("たまっている質問があるとき、最後の応答の下に数つきで出す", async () => {
    hookOverrides = { ...inSession, pendingQuestions: 2 };
    await renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: "質問を聞く（2）" }),
    );
    expect(startQuestions).toHaveBeenCalledOnce();
  });

  it.each([0, null])("数が %s のときは出さない", async (count) => {
    hookOverrides = { ...inSession, pendingQuestions: count };
    await renderPage();
    expect(screen.getByText("受け止め")).toBeInTheDocument();
    expect(button()).toBeNull();
  });

  it("終了の確認が出ているときは出さない", async () => {
    hookOverrides = {
      ...inSession,
      pendingQuestions: 2,
      endConfirmation: { creates_note: true },
    };
    await renderPage();
    expect(
      screen.getByRole("button", { name: "ノートを作成して終了" }),
    ).toBeInTheDocument();
    expect(button()).toBeNull();
  });

  it("インプットのセッションでは出さない", async () => {
    hookOverrides = {
      ...inSession,
      sessionType: "explore",
      pendingQuestions: 2,
    };
    await renderPage();
    expect(button()).toBeNull();
  });

  it("応答の生成中は出さない", async () => {
    hookOverrides = { ...inSession, pendingQuestions: 2, isLoading: true };
    await renderPage();
    expect(button()).toBeNull();
  });

  it("終了したセッションでは出さない", async () => {
    hookOverrides = { ...inSession, pendingQuestions: 2, isSessionEnded: true };
    await renderPage();
    expect(button()).toBeNull();
  });
});

describe("LearnPage の横の質問", () => {
  const thread = {
    id: "q1",
    parentId: null,
    anchorMessageId: "a1",
    anchorSideMessageId: null,
    quote: "索引",
    occurrence: 0,
    depth: 0,
    messages: [
      { id: "su1", role: "user", content: "索引とは？" },
      { id: "sa1", role: "assistant", content: "行の位置を指す一覧" },
    ],
  };
  const session = (sessionType: string) => ({
    isConnected: true,
    sessionId: "s1",
    sessionType,
    messages: [
      { role: "user", content: "インデックスとは？" },
      { id: "a1", role: "assistant", content: "索引を使って探します" },
    ],
  });
  const panel = () => screen.queryByRole("complementary", { name: "質問" });

  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    hookOverrides = {};
    coarsePointer = false;
    sideThreads = [thread];
    sideLoadFailed = false;
    fetchActiveSession.mockResolvedValue(null);
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("shows the panel and marks answers selectable in an explore session", async () => {
    hookOverrides = session("explore");
    await renderPage();

    expect(useSideQuestionsMock).toHaveBeenLastCalledWith("s1", true);
    expect(panel()).toBeInTheDocument();
    const answer = screen
      .getByText("索引を使って探します")
      .closest("[data-message-id]");
    expect(answer).toHaveAttribute("data-message-id", "a1");
    expect(answer).toHaveAttribute("data-side-selectable");
  });

  it("tells that earlier side questions could not be loaded and offers a reload", async () => {
    sideThreads = [];
    sideLoadFailed = true;
    hookOverrides = session("explore");
    await renderPage();

    expect(errorToast).toHaveBeenCalledWith(
      "これまでの質問を読み込めませんでした",
      { label: "再読み込み", onClick: reloadSide },
    );
  });

  it("panel is not rendered with no threads and no draft", async () => {
    sideThreads = [];
    hookOverrides = session("explore");
    await renderPage();

    expect(panel()).toBeNull();
  });

  it("learn page does not render the ask button or panel for a learning session", async () => {
    hookOverrides = session("learning");
    await renderPage();

    expect(useSideQuestionsMock).toHaveBeenLastCalledWith(null, false);
    expect(panel()).toBeNull();
    expect(
      screen
        .getByText("索引を使って探します")
        .closest("[data-side-selectable]"),
    ).toBeNull();
  });

  it("learn page does not render the ask button or panel on coarse pointer", async () => {
    coarsePointer = true;
    hookOverrides = session("explore");
    await renderPage();

    expect(useSideQuestionsMock).toHaveBeenLastCalledWith(null, false);
    expect(panel()).toBeNull();
    expect(
      screen
        .getByText("索引を使って探します")
        .closest("[data-side-selectable]"),
    ).toBeNull();
  });

  it("an answer still streaming cannot be selected", async () => {
    hookOverrides = { ...session("explore"), isLoading: true };
    await renderPage();

    expect(
      screen
        .getByText("索引を使って探します")
        .closest("[data-side-selectable]"),
    ).toBeNull();
  });

  it("removes side questions of a reply taken back by a cancel", async () => {
    hookOverrides = session("explore");
    let rerender: (ui: React.ReactElement) => void = () => {};
    await act(async () => {
      ({ rerender } = render(<LearnPage />));
    });

    hookOverrides = { ...session("explore"), messages: [] };
    await act(async () => {
      rerender(<LearnPage />);
    });

    expect(removeByAnchorMessage).toHaveBeenCalledWith("a1");
  });
});
