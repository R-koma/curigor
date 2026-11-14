import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReviewPage from "@/app/(main)/review/[noteId]/page";

let currentSearch = "";
const sendMessage = vi.fn(() => true);
const hookState: { isSessionEnded: boolean; sessionId: string | null } = {
  isSessionEnded: false,
  sessionId: "s1",
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
  isReconnecting: false,
  isLoading: false,
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
  startRefused: false,
  startReview: vi.fn(),
  resumeSession: vi.fn(),
  sendMessage,
  endSession: vi.fn(),
  cancelLastMessage: vi.fn(),
  clearEditingMessage: vi.fn(),
  notePeekAvailable: false,
  markNoteViewed: vi.fn(),
};
vi.mock("@/hooks/use-chat-websocket", () => ({
  useChatWebSocket: () => ({
    ...stableHook,
    isSessionEnded: hookState.isSessionEnded,
    sessionId: hookState.sessionId,
  }),
}));
const stableConversation = {
  status: "off",
  unsentText: "",
  stop: vi.fn(),
  pause: vi.fn(),
  resume: vi.fn(),
  error: null,
  speechError: null,
};
vi.mock("@/hooks/use-voice-conversation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/use-voice-conversation")>()),
  useVoiceConversation: () => stableConversation,
}));
vi.mock("@/hooks/use-error-toast", () => ({ useErrorToast: () => {} }));
vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({ setNavbarCenter: vi.fn(), setPageHelpIds: vi.fn() }),
}));
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
vi.mock("@/lib/active-session", () => ({
  fetchActiveSession: async () => null,
}));
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
  loadResumableMessages: async () => ({
    sessionType: "review",
    status: "in_progress",
    noteId: "n1",
    topic: null,
    messages: [
      { role: "user", content: "二分探索" },
      { role: "assistant", content: "説明してみて" },
    ],
  }),
}));

const params = Promise.resolve({ noteId: "n1" });

async function renderPage() {
  let view!: ReturnType<typeof render>;
  await act(async () => {
    view = render(<ReviewPage params={params} />);
  });
  return view;
}

describe("ReviewPage の書きかけ", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    currentSearch = "session=s1";
    hookState.isSessionEnded = false;
    hookState.sessionId = "s1";
    stableConversation.status = "off";
    stableConversation.unsentText = "";
    Element.prototype.scrollIntoView ??= () => {};
  });

  it("?session= で開くと保存した書きかけが入力欄に入る", async () => {
    sessionStorage.setItem("curigor:draft:session:s1", "復習の途中");
    await renderPage();
    expect(screen.getByLabelText("入力欄")).toHaveValue("復習の途中");
  });

  it("入力すると保存し、送信すると消える", async () => {
    await renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("入力欄"), "abc");
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBe("abc");
    await user.click(screen.getByRole("button", { name: "送信" }));
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull();
  });

  it("セッションが終わると保存が消える", async () => {
    sessionStorage.setItem("curigor:draft:session:s1", "書きかけ");
    const view = await renderPage();
    expect(screen.getByLabelText("入力欄")).toHaveValue("書きかけ");
    hookState.isSessionEnded = true;
    await act(async () => {
      view.rerender(<ReviewPage params={params} />);
    });
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull();
  });

  it("声で話すモードの未送信の文を保存し、終えると入力欄の文に戻す", async () => {
    stableConversation.status = "listening";
    stableConversation.unsentText = "声の文";
    const view = await renderPage();
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBe("声の文");

    stableConversation.status = "off";
    await act(async () => {
      view.rerender(<ReviewPage params={params} />);
    });
    expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull();
  });

  it("セッションが始まった後 ?session= が付く前に打った文は、セッションの保存に書く", async () => {
    const view = await renderPage();
    currentSearch = "";
    hookState.sessionId = "s2";
    await act(async () => {
      view.rerender(<ReviewPage params={params} />);
    });
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("入力欄"), "abc");
    expect(sessionStorage.getItem("curigor:draft:session:s2")).toBe("abc");
  });
});
