import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { REFLECTION_LIMIT_MESSAGE } from "@/components/reflections/reflection-audio";
import { ReflectionQuizDialog } from "@/components/reflections/reflection-quiz-dialog";
import { ApiError, fetchAPI } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, fetchAPI: vi.fn() };
});

const mockFetch = vi.mocked(fetchAPI);

const questions = [1, 2, 3].map((n) => ({
  question: `問題${n}`,
  choices: [`${n}-A`, `${n}-B`, `${n}-C`, `${n}-D`],
  answer_index: 1,
  explanation: `解説${n}`,
}));

function renderDialog() {
  return render(
    <ReflectionQuizDialog
      period="day"
      start="2026-11-01"
      open
      onOpenChange={() => {}}
    />,
  );
}

describe("ReflectionQuizDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("requests the quiz when opened", async () => {
    mockFetch.mockResolvedValue({ questions });
    renderDialog();
    expect(await screen.findByText("問題1")).toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/reflections/day/2026-11-01/quiz",
      { method: "POST" },
    );
  });

  it("shows 正解 and the explanation for a correct pick", async () => {
    mockFetch.mockResolvedValue({ questions });
    renderDialog();
    await userEvent.click(await screen.findByRole("button", { name: /1-B/ }));
    expect(screen.getByText("正解")).toBeInTheDocument();
    expect(screen.getByText("解説1")).toBeInTheDocument();
  });

  it("marks the correct choice after a wrong pick", async () => {
    mockFetch.mockResolvedValue({ questions });
    renderDialog();
    await userEvent.click(await screen.findByRole("button", { name: /1-A/ }));
    expect(screen.getByText("不正解")).toBeInTheDocument();
    expect(screen.getByText("正解")).toBeInTheDocument();
    expect(screen.getByText("解説1")).toBeInTheDocument();
  });

  it("shows the score after the last question and sends nothing", async () => {
    mockFetch.mockResolvedValue({ questions });
    renderDialog();
    const picks = [/1-B/, /2-B/, /3-A/];
    for (let i = 0; i < 3; i++) {
      await userEvent.click(
        await screen.findByRole("button", { name: picks[i] }),
      );
      await userEvent.click(
        screen.getByRole("button", {
          name: i < 2 ? "次の問題" : "結果を見る",
        }),
      );
    }
    expect(screen.getByText("3問中2問正解")).toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("shows the limit message on 429", async () => {
    mockFetch.mockRejectedValue(new ApiError(429, null, null));
    renderDialog();
    expect(
      await screen.findByText(REFLECTION_LIMIT_MESSAGE),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "もう一度試す" })).toBeNull();
  });

  it("offers a retry on other failures", async () => {
    mockFetch.mockRejectedValueOnce(new ApiError(502, null, null));
    mockFetch.mockResolvedValueOnce({ questions });
    renderDialog();
    await userEvent.click(
      await screen.findByRole("button", { name: "もう一度試す" }),
    );
    expect(await screen.findByText("問題1")).toBeInTheDocument();
  });
});
