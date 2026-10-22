import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReviewPage from "@/app/(main)/review/[noteId]/page";

const replace = vi.fn();
const push = vi.fn();
const resumeSession = vi.fn();
const loadResumableMessages = vi.fn();
const startReview = vi.fn();
const toastInfo = vi.fn();
const fetchActiveSession = vi.fn();
let currentSearch = "";
const markNoteViewed = vi.fn();
const pause = vi.fn();
const resume = vi.fn();
const hookState = {
  sessionId: null as string | null,
  notePeekAvailable: false,
  isLoading: false,
  isSessionEnded: false,
};
const voiceState = { status: "off" };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push, refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(currentSearch),
}));
vi.mock("@/hooks/use-chat-websocket", () => ({
  useChatWebSocket: () => ({
    messages: [],
    isReconnecting: false,
    isLoading: hookState.isLoading,
    isSessionEnded: hookState.isSessionEnded,
    isGeneratingNote: false,
    feedback: null,
    endConfirmation: null,
    noteSkipped: false,
    dismissEndConfirmation: vi.fn(),
    error: null,
    editingMessage: null,
    editingRawTranscript: null,
    editingAutoSent: false,
    speechBus: {},
    sessionId: hookState.sessionId,
    startReview,
    resumeSession,
    sendMessage: vi.fn(),
    endSession: vi.fn(),
    cancelLastMessage: vi.fn(),
    clearEditingMessage: vi.fn(),
    notePeekAvailable: hookState.notePeekAvailable,
    markNoteViewed,
  }),
}));
vi.mock("@/hooks/use-voice-conversation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/use-voice-conversation")>()),
  useVoiceConversation: () => ({
    status: voiceState.status,
    pause,
    resume,
    stop: vi.fn(),
    error: null,
    speechError: null,
  }),
}));
vi.mock("@/hooks/use-error-toast", () => ({ useErrorToast: () => {} }));
vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({ setNavbarCenter: vi.fn() }),
}));
vi.mock("@/components/review/review-start-screen", () => ({
  ReviewStartScreen: ({ onStart }: { onStart: () => void }) => (
    <button type="button" onClick={onStart}>
      復習を開始する
    </button>
  ),
}));
vi.mock("sonner", () => ({ toast: { info: (m: string) => toastInfo(m) } }));
vi.mock("@/lib/active-session", () => ({
  fetchActiveSession: () => fetchActiveSession(),
}));
vi.mock("@/components/chat/chat-input", () => ({ ChatInput: () => null }));
vi.mock("@/components/chat/voice-panel", () => ({ VoicePanel: () => null }));
vi.mock("@/lib/api", () => ({
  getToken: async () => "token",
  fetchAPI: vi.fn(async (path: string) => {
    if (path.endsWith("/feedbacks")) return { feedbacks: [] };
    return {
      id: "n1",
      topic: "二分探索",
      content: "本文",
      summary: "要約",
      aspect_map: null,
    };
  }),
}));
vi.mock("@/lib/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/session")>()),
  loadResumableMessages: (id: string) => loadResumableMessages(id),
}));

const params = Promise.resolve({ noteId: "n1" });

async function renderPage() {
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(<ReviewPage params={params} />);
  });
  return result;
}

describe("ReviewPage の URL とセッション", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    hookState.sessionId = null;
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("開始した復習のセッション ID を URL に書く", async () => {
    hookState.sessionId = "s1";
    await renderPage();
    expect(replace).toHaveBeenCalledWith("/review/n1?session=s1");
  });

  it("URL を書き換えた後に再開処理を走らせない", async () => {
    const { rerender } = await renderPage();
    hookState.sessionId = "s1";
    await act(async () => rerender(<ReviewPage params={params} />));
    currentSearch = "session=s1";
    await act(async () => rerender(<ReviewPage params={params} />));
    expect(loadResumableMessages).not.toHaveBeenCalled();
    expect(resumeSession).not.toHaveBeenCalled();
  });

  it("?session= で再開したセッションでは URL を書き換えない", async () => {
    currentSearch = "session=s1";
    loadResumableMessages.mockResolvedValue({
      sessionType: "review",
      status: "in_progress",
      noteId: "n1",
      topic: null,
      messages: [
        { role: "user", content: "二分探索" },
        { role: "assistant", content: "説明してみて" },
      ],
    });
    hookState.sessionId = "s1";
    await renderPage();
    expect(resumeSession).toHaveBeenCalledWith("s1", [
      { role: "assistant", content: "説明してみて" },
    ]);
    expect(replace).not.toHaveBeenCalled();
  });

  it("再開できない状態のセッションなら開始画面の URL に戻す", async () => {
    currentSearch = "session=s1";
    loadResumableMessages.mockResolvedValue({
      sessionType: "review",
      status: "completed",
      noteId: "n1",
      topic: null,
      messages: [],
    });
    await renderPage();
    expect(replace).toHaveBeenCalledWith("/review/n1");
    expect(resumeSession).not.toHaveBeenCalled();
    expect(toastInfo).toHaveBeenCalledWith("このセッションは終了しています");
  });

  it("別のセッションを始めて終了したセッションなら、その理由を知らせる", async () => {
    currentSearch = "session=s1";
    loadResumableMessages.mockResolvedValue({
      sessionType: "review",
      status: "abandoned",
      noteId: "n1",
      topic: null,
      messages: [],
    });
    await renderPage();
    expect(replace).toHaveBeenCalledWith("/review/n1");
    expect(toastInfo).toHaveBeenCalledWith(
      "このセッションは終了しています。新しいセッションを始めると、進行中のセッションは終了します",
    );
  });
});

describe("ReviewPage の開始", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    hookState.sessionId = null;
  });

  it("進行中のセッションが無ければそのまま復習を始める", async () => {
    fetchActiveSession.mockResolvedValue(null);
    await renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(startReview).toHaveBeenCalledWith("n1");
  });

  it("進行中のセッションがあれば、確かめてから復習を始める", async () => {
    fetchActiveSession.mockResolvedValue({
      session_id: "s0",
      session_type: "explore",
      status: "in_progress",
      started_at: "2026-10-19T12:22:08Z",
      topic: "改元",
      note_id: null,
    });
    await renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(startReview).not.toHaveBeenCalled();
    await userEvent.click(
      await screen.findByRole("button", { name: "終了して始める" }),
    );
    expect(startReview).toHaveBeenCalledWith("n1");
  });
});

describe("ReviewPage のノートを見る", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "session=s1";
    hookState.sessionId = "s1";
    hookState.notePeekAvailable = true;
    hookState.isLoading = false;
    hookState.isSessionEnded = false;
    voiceState.status = "off";
    Element.prototype.scrollIntoView ??= () => {};
    loadResumableMessages.mockResolvedValue({
      sessionType: "review",
      status: "in_progress",
      noteId: "n1",
      topic: null,
      messages: [
        { role: "user", content: "二分探索" },
        { role: "assistant", content: "説明してみて" },
      ],
    });
  });

  const peekButton = () =>
    screen.queryByRole("button", { name: "ノートを見る" });

  it("開けるときだけボタンを出す", async () => {
    await renderPage();
    expect(peekButton()).toBeInTheDocument();
  });

  it.each([
    ["開けない", { notePeekAvailable: false }],
    ["応答の生成中", { isLoading: true }],
    ["セッションの終了後", { isSessionEnded: true }],
  ])("%sはボタンを出さない", async (_, state) => {
    Object.assign(hookState, state);
    await renderPage();
    expect(peekButton()).not.toBeInTheDocument();
  });

  it("閉じたときにノートを見たことを記録する", async () => {
    await renderPage();
    await userEvent.click(peekButton()!);
    expect(screen.getByText("本文")).toBeInTheDocument();
    expect(markNoteViewed).not.toHaveBeenCalled();

    await userEvent.click(
      screen.getByRole("button", { name: "閉じて説明する" }),
    );

    expect(markNoteViewed).toHaveBeenCalledTimes(1);
  });

  it("声で話している間に開くと聞き取りを止め、閉じると再開する", async () => {
    voiceState.status = "listening";
    await renderPage();
    await userEvent.click(peekButton()!);
    expect(pause).toHaveBeenCalledTimes(1);

    await userEvent.click(
      screen.getByRole("button", { name: "閉じて説明する" }),
    );

    expect(resume).toHaveBeenCalledTimes(1);
  });

  it("開く前に止めていた聞き取りは、閉じても再開しない", async () => {
    voiceState.status = "paused";
    await renderPage();
    await userEvent.click(peekButton()!);
    await userEvent.click(
      screen.getByRole("button", { name: "閉じて説明する" }),
    );

    expect(pause).not.toHaveBeenCalled();
    expect(resume).not.toHaveBeenCalled();
  });
});
