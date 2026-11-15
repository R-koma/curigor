import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toaster } from "@/components/ui/sonner";
import { SavedSessionList } from "@/components/sessions/saved-session-list";
import type { SavedSession } from "@/lib/saved-sessions";

const fetchAPI = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ fetchAPI }));
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const NOW = new Date("2026-11-15T12:00:00Z");
const SESSION: SavedSession = {
  session_id: "s1",
  session_type: "learning",
  topic: "TCP",
  note_id: null,
  last_activity_at: NOW.toISOString(),
  expires_at: new Date(NOW.getTime() + 20 * 86_400_000).toISOString(),
  last_assistant_excerpt: null,
  progress: null,
};

describe("undo toast with the real Toaster", () => {
  beforeEach(() => {
    fetchAPI.mockReset();
    fetchAPI.mockResolvedValue(undefined);
  });

  it("survives an outside pointerdown and sends no DELETE after unmount", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <>
        <Toaster />
        <button type="button">outside</button>
        <SavedSessionList sessions={[SESSION]} now={NOW} />
      </>,
    );
    await user.click(screen.getByRole("button", { name: "「TCP」を削除" }));
    expect(await screen.findByText("元に戻す")).toBeInTheDocument();
    await act(async () => {
      document.body.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 400));
    });
    expect(screen.getByText("元に戻す")).toBeInTheDocument();
    unmount();
    await act(async () => {});
    expect(fetchAPI).not.toHaveBeenCalled();
  });
});
