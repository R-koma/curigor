import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LearnPage from "@/app/(main)/learn/page";

let currentSearch = "";
let hookOverrides: Record<string, unknown> = {};
const sendMessage = vi.fn(() => true);
const conversationState = {
  status: "off",
  unsentText: "",
  stop: vi.fn(),
  error: null,
  speechError: null,
};

vi.mock("next/navigation", () => {
  const router = { replace: vi.fn(), push: vi.fn(), refresh: vi.fn() };
  return {
    useRouter: () => router,
    useSearchParams: () => new URLSearchParams(currentSearch),
  };
});
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
  startQuestions: vi.fn(),
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
  startExplore: vi.fn(),
  sessionTopic: null,
  startLearning: vi.fn(),
  resumeSession: vi.fn(),
  sendMessage,
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
  useVoiceConversation: () => conversationState,
}));
vi.mock("@/hooks/use-error-toast", () => ({ useErrorToast: () => {} }));
vi.mock("@/hooks/use-coarse-pointer", () => ({
  useCoarsePointer: () => false,
}));
const stableSide = {
  threads: [],
  draft: null,
  open: new Set(),
  streaming: null,
  error: null,
  loadFailed: false,
  reload: vi.fn(),
  startDraft: vi.fn(),
  send: vi.fn(),
  toggle: vi.fn(),
  openThread: vi.fn(),
  foldAll: vi.fn(),
  removeByAnchorMessage: vi.fn(),
};
vi.mock("@/hooks/use-side-questions", () => ({
  useSideQuestions: () => stableSide,
}));
vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({ setNavbarCenter: vi.fn() }),
}));
vi.mock("@/context/usage-hints-context", () => ({
  useActiveHint: () => null,
}));
vi.mock("@/components/hints/usage-hint", () => ({ UsageHint: () => null }));
vi.mock("@/components/chat/chat-input", () => ({
  ChatInput: ({
    value,
    onChange,
    onSend,
  }: {
    value: string;
    onChange: (v: string) => void;
    onSend: (content: string) => void;
  }) => (
    <div>
      <textarea
        aria-label="入力欄"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <button type="button" onClick={() => onSend(value)}>
        送信
      </button>
    </div>
  ),
}));
vi.mock("@/components/chat/voice-panel", () => ({ VoicePanel: () => null }));
vi.mock("sonner", () => ({ toast: { info: vi.fn() } }));
vi.mock("@/lib/active-session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/active-session")>()),
  fetchActiveSession: async () => null,
}));
vi.mock("@/lib/api", () => ({
  getToken: async () => "token",
  fetchAPI: vi.fn(async () => null),
}));
vi.mock("@/lib/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/session")>()),
  loadResumableMessages: async () => ({ messages: [] }),
}));

const inSession = {
  isConnected: true,
  messages: [{ role: "assistant", content: "説明してください" }],
};

async function renderPage() {
  let view!: ReturnType<typeof render>;
  await act(async () => {
    view = render(<LearnPage />);
  });
  return view;
}

describe("LearnPage の書きかけ", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    currentSearch = "";
    hookOverrides = {};
    conversationState.status = "off";
    conversationState.unsentText = "";
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("?session= で開くと保存した書きかけが入力欄に入る", async () => {
    sessionStorage.setItem("curigor:draft:session:s1", "説明の途中");
    currentSearch = "session=s1";
    hookOverrides = { ...inSession, sessionId: "s1" };
    await renderPage();
    expect(screen.getByLabelText("入力欄")).toHaveValue("説明の途中");
  });

  it("開始前の欄の書きかけが戻る", async () => {
    sessionStorage.setItem("curigor:draft:start:learning", "トピック");
    await renderPage();
    expect(screen.getByLabelText("入力欄")).toHaveValue("トピック");
  });

  it("インプットの開始前の欄は別に保存する", async () => {
    sessionStorage.setItem("curigor:draft:start:learning", "学習");
    sessionStorage.setItem("curigor:draft:start:explore", "インプット");
    currentSearch = "mode=explore";
    await renderPage();
    expect(screen.getByLabelText("入力欄")).toHaveValue("インプット");
  });

  it("送信すると保存が消える", async () => {
    currentSearch = "session=s1";
    hookOverrides = { ...inSession, sessionId: "s1" };
    await renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("入力欄"), "abc");
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBe("abc");
    await user.click(screen.getByRole("button", { name: "送信" }));
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull();
  });

  it("セッションが終わると保存が消える", async () => {
    sessionStorage.setItem("curigor:draft:session:s1", "書きかけ");
    currentSearch = "session=s1";
    hookOverrides = { ...inSession, sessionId: "s1" };
    let view!: ReturnType<typeof render>;
    await act(async () => {
      view = render(<LearnPage />);
    });
    expect(screen.getByLabelText("入力欄")).toHaveValue("書きかけ");
    hookOverrides = { ...inSession, sessionId: "s1", isSessionEnded: true };
    await act(async () => {
      view.rerender(<LearnPage />);
    });
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull();
  });

  it("声で話すモードの未送信の文を保存し、終えると入力欄の文に戻す", async () => {
    currentSearch = "session=s1";
    hookOverrides = { ...inSession, sessionId: "s1" };
    conversationState.status = "listening";
    conversationState.unsentText = "声の文";
    const view = await renderPage();
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBe("声の文");

    conversationState.status = "off";
    await act(async () => {
      view.rerender(<LearnPage />);
    });
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull();
  });

  it("セッションが始まると、開始前の欄の書きかけを消す", async () => {
    const view = await renderPage();
    sessionStorage.setItem("curigor:draft:start:learning", "間に話した文");
    sessionStorage.setItem("curigor:draft:start:explore", "別の文");
    hookOverrides = { ...inSession, sessionId: "s1" };
    await act(async () => {
      view.rerender(<LearnPage />);
    });
    expect(sessionStorage.getItem("curigor:draft:start:learning")).toBeNull();
    expect(sessionStorage.getItem("curigor:draft:start:explore")).toBeNull();
  });
});
