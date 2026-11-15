import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LearnPage from "@/app/(main)/learn/page";
import { fetchAPI } from "@/lib/api";
import { DESKTOP_WIDTH, setMediaQuery } from "../stubs/match-media";

const replace = vi.fn();
const startLearning = vi.fn();
const startExplore = vi.fn();
const resumeSession = vi.fn();
const loadResumableMessages = vi.fn();
const toastFn = vi.fn();
const toastError = vi.fn();
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
  disconnect: vi.fn(),
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
const setPageHelpIds = vi.fn();
vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({ setNavbarCenter, setPageHelpIds }),
}));
vi.mock("@/context/usage-hints-context", () => ({
  useActiveHint: () => null,
}));
vi.mock("@/components/hints/usage-hint", () => ({ UsageHint: () => null }));
vi.mock("@/components/chat/chat-input", () => ({ ChatInput: () => null }));
vi.mock("sonner", () => ({
  toast: Object.assign((m: string) => toastFn(m), {
    info: (m: string) => toastInfo(m),
    error: (m: string) => toastError(m),
  }),
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

  it("改善点からの理解するは、確認なしでそのまま始める", async () => {
    currentSearch = "note=n1&feedback=f1&item=2";
    await renderPage();
    expect(startExplore).toHaveBeenCalledWith("", {
      source: { note_id: "n1", feedback_id: "f1", improvement_index: 2 },
    });
    expect(screen.queryByText("終了して始める")).not.toBeInTheDocument();
  });

  it("学習メモからの学習は、確認なしでそのまま始める", async () => {
    currentSearch = "memo=m1";
    await renderPage();
    expect(startLearning).toHaveBeenCalledWith("改元", {
      study_memo_id: "m1",
    });
    expect(screen.queryByText("終了して始める")).not.toBeInTheDocument();
  });

  it("開始画面に「前回の会話」を出さず、進行中の取得もしない", async () => {
    await renderPage();
    expect(screen.queryByText("前回の会話")).not.toBeInTheDocument();
    expect(fetchAPI).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/dialogue-sessions"),
    );
  });

  it("開始画面の使い方をスマホの上のバーへ渡し、セッションが始まったら取り下げる", async () => {
    const view = render(<LearnPage />);
    await act(async () => {});
    expect(setPageHelpIds).toHaveBeenLastCalledWith(["learn_start"]);

    hookOverrides = { isConnected: true };
    await act(async () => {
      view.rerender(<LearnPage />);
    });
    expect(setPageHelpIds).toHaveBeenLastCalledWith(null);
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
    expect(toastInfo).toHaveBeenCalledWith("このセッションは終了しています");
    expect(replace).toHaveBeenCalledWith("/learn");
  });

  it.each(["session_not_resumable", "session_outdated", "session_not_found"])(
    "再開の接続が %s で断られたら、知らせて開始画面へ移る",
    async (code) => {
      currentSearch = "session=s1";
      hookOverrides = { errorCode: code };
      loadResumableMessages.mockResolvedValue({
        sessionType: "learning",
        status: "disconnect",
        noteId: null,
        topic: "改元",
        messages: [{ role: "user", content: "改元" }],
      });
      await renderPage();
      expect(toastInfo).toHaveBeenCalledWith("このセッションは終了しています");
      expect(stableHook.resetSession).toHaveBeenCalled();
      expect(replace).toHaveBeenCalledWith("/learn");
    },
  );
});

describe("LearnPage で保存中の会話から別の会話へ移る", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    hookOverrides = {};
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("A につながったまま B を開くと、リセットして B を再開し、URL を A へ戻さない", async () => {
    const resumable = (topic: string) => ({
      sessionType: "learning",
      status: "in_progress",
      noteId: null,
      topic,
      messages: [{ role: "user", content: topic }],
    });
    loadResumableMessages.mockImplementation(async (id: string) =>
      resumable(id === "A" ? "トピックA" : "トピックB"),
    );
    currentSearch = "session=A";
    const view = render(<LearnPage />);
    await act(async () => {});
    expect(resumeSession).toHaveBeenLastCalledWith("A", expect.anything());

    hookOverrides = { sessionId: "A", isConnected: true };
    replace.mockClear();
    stableHook.resetSession.mockClear();
    currentSearch = "session=B";
    await act(async () => {
      view.rerender(<LearnPage />);
    });

    expect(stableHook.resetSession).toHaveBeenCalled();
    expect(resumeSession).toHaveBeenLastCalledWith("B", expect.anything());
    expect(replace).not.toHaveBeenCalledWith("/learn?session=A");
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

describe("LearnPage の終了の 3 択", () => {
  const inSession = {
    isConnected: true,
    sessionId: "s1",
    sessionType: "learning",
    sessionTopic: "二分探索",
    messages: [
      { role: "user", content: "二分探索" },
      { role: "assistant", content: "声かけ" },
      { role: "user", content: "真ん中と比べます" },
      { role: "assistant", content: "受け止め" },
    ],
  };

  async function openDialog() {
    const header = setNavbarCenter.mock.calls
      .map((c) => c[0])
      .filter(Boolean)
      .at(-1);
    render(<>{header}</>);
    await userEvent.click(screen.getByRole("button", { name: /終了する/ }));
  }

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    currentSearch = "session=s1";
    hookOverrides = inSession;
    setMediaQuery(DESKTOP_WIDTH, true);
    loadResumableMessages.mockResolvedValue({
      sessionType: "learning",
      status: "in_progress",
      noteId: null,
      topic: "二分探索",
      messages: [],
    });
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("ヘッダーの「終了する」は 3 択を開き、終了はまだ送らない", async () => {
    const endSession = vi.fn();
    hookOverrides = { ...inSession, endSession };
    await renderPage();
    await openDialog();
    expect(
      await screen.findByText("セッションをどうしますか？"),
    ).toBeInTheDocument();
    expect(endSession).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: /終了してノートを作成/ }),
    );
    expect(endSession).toHaveBeenCalledOnce();
    await waitFor(() =>
      expect(
        screen.queryByText("セッションをどうしますか？"),
      ).not.toBeInTheDocument(),
    );
  });

  it("保存すると dashboard へ移り通知を出す。二度押しても一度だけ", async () => {
    await renderPage();
    await openDialog();
    const save = await screen.findByRole("button", {
      name: /保存して後で続ける/,
    });
    await userEvent.click(save);
    await userEvent.click(save);
    expect(stableHook.disconnect).toHaveBeenCalledTimes(1);
    expect(stableHook.disconnect.mock.invocationCallOrder[0]).toBeLessThan(
      stableRouter.push.mock.invocationCallOrder[0],
    );
    expect(stableRouter.push).toHaveBeenCalledTimes(1);
    expect(stableRouter.push).toHaveBeenCalledWith("/dashboard");
    expect(toastFn).toHaveBeenCalledWith(
      "保存しました。「続きから」で再開できます",
    );
  });

  it("捨てる: 確認の後に DELETE し、書きかけを消して /learn へ移る", async () => {
    sessionStorage.setItem("curigor:draft:session:s1", "書きかけ");
    await renderPage();
    await openDialog();
    await userEvent.click(
      await screen.findByRole("button", { name: "保存せずに捨てる" }),
    );
    expect(fetchAPI).not.toHaveBeenCalledWith(
      "/api/dialogue-sessions/s1",
      expect.anything(),
    );
    await userEvent.click(screen.getByRole("button", { name: "捨てる" }));
    expect(fetchAPI).toHaveBeenCalledWith("/api/dialogue-sessions/s1", {
      method: "DELETE",
    });
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull();
    expect(replace).toHaveBeenCalledWith("/learn");
  });

  it("捨てるのに失敗したら通知を出し、ページに残る", async () => {
    sessionStorage.setItem("curigor:draft:session:s1", "書きかけ");
    vi.mocked(fetchAPI).mockRejectedValueOnce(new Error("x"));
    await renderPage();
    await openDialog();
    await userEvent.click(
      await screen.findByRole("button", { name: "保存せずに捨てる" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "捨てる" }));
    expect(toastError).toHaveBeenCalledWith(
      "会話を消せませんでした。もう一度お試しください",
    );
    expect(replace).not.toHaveBeenCalledWith("/learn");
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBe("書きかけ");
  });

  it("会話での終了の確認も 3 択で出る", async () => {
    hookOverrides = {
      ...inSession,
      endConfirmation: { creates_note: true },
    };
    await renderPage();
    expect(
      screen.getByRole("button", { name: /保存して後で続ける/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "保存せずに捨てる" }),
    ).toBeInTheDocument();
  });
});
