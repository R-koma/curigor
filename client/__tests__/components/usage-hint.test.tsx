import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UsageHint } from "@/components/hints/usage-hint";
import {
  UsageHintsProvider,
  useActiveHint,
  useUsageHints,
} from "@/context/usage-hints-context";
import { HINT_TEXT, type HintId } from "@/lib/hints";

const mocks = vi.hoisted(() => ({ fetchAPI: vi.fn() }));

vi.mock("@/lib/api", () => ({ fetchAPI: mocks.fetchAPI }));

function respondWith(dismissed: string[]) {
  mocks.fetchAPI.mockImplementation(
    async (path: string, options?: RequestInit) =>
      !options?.method && path === "/api/hints/dismissals"
        ? { dismissed }
        : undefined,
  );
}

function ActiveHint({ candidates }: { candidates: (HintId | false)[] }) {
  const active = useActiveHint(candidates);
  return <p data-testid="active">{active ?? "none"}</p>;
}

function ResetButton() {
  const { reset } = useUsageHints();
  return (
    <button type="button" onClick={() => void reset()}>
      reset
    </button>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("UsageHint", () => {
  it("shows a hint the user has not dismissed", async () => {
    respondWith([]);
    render(
      <UsageHintsProvider>
        <UsageHint id="chat_input" />
      </UsageHintsProvider>,
    );
    const hint = await screen.findByRole("complementary", {
      name: "使い方のヒント",
    });
    expect(hint).toHaveTextContent(HINT_TEXT.chat_input);
  });

  it("does not show a dismissed hint", async () => {
    respondWith(["chat_input"]);
    render(
      <UsageHintsProvider>
        <UsageHint id="chat_input" />
        <ActiveHint candidates={["chat_input"]} />
      </UsageHintsProvider>,
    );
    await waitFor(() => expect(mocks.fetchAPI).toHaveBeenCalled());
    expect(screen.getByTestId("active")).toHaveTextContent("none");
    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("shows nothing when the dismissals could not be loaded", async () => {
    mocks.fetchAPI.mockRejectedValue(new Error("API error: 500"));
    render(
      <UsageHintsProvider>
        <UsageHint id="chat_input" />
      </UsageHintsProvider>,
    );
    await waitFor(() => expect(mocks.fetchAPI).toHaveBeenCalled());
    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("shows nothing outside the provider", () => {
    render(<UsageHint id="chat_input" />);
    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("records the hint and hides it when closed", async () => {
    respondWith([]);
    render(
      <UsageHintsProvider>
        <UsageHint id="dialogue" />
      </UsageHintsProvider>,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "ヒントを閉じる" }),
    );
    expect(screen.queryByRole("complementary")).toBeNull();
    expect(mocks.fetchAPI).toHaveBeenCalledWith(
      "/api/hints/dismissals/dialogue",
      { method: "PUT" },
    );
  });

  it("closes with Escape while focused", async () => {
    respondWith([]);
    render(
      <UsageHintsProvider>
        <UsageHint id="dialogue" />
      </UsageHintsProvider>,
    );
    (await screen.findByRole("button", { name: "ヒントを閉じる" })).focus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("picks the first candidate that is still shown", async () => {
    respondWith(["intake_card"]);
    render(
      <UsageHintsProvider>
        <ActiveHint
          candidates={["intake_card", false, "chat_input", "dialogue"]}
        />
      </UsageHintsProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("active")).toHaveTextContent("chat_input"),
    );
  });

  it("shows dismissed hints again after a reset", async () => {
    respondWith(["chat_input"]);
    render(
      <UsageHintsProvider>
        <UsageHint id="chat_input" />
        <ResetButton />
      </UsageHintsProvider>,
    );
    await waitFor(() => expect(mocks.fetchAPI).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: "reset" }));
    expect(
      await screen.findByRole("complementary", { name: "使い方のヒント" }),
    ).toBeInTheDocument();
    expect(mocks.fetchAPI).toHaveBeenCalledWith("/api/hints/dismissals", {
      method: "DELETE",
    });
  });
});
