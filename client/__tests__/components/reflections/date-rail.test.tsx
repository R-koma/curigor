import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DateRail } from "@/components/reflections/date-rail";
import type { WeekDayStatus } from "@/lib/reflection";

const DAYS: WeekDayStatus[] = [
  { day: "2026-10-26", has_learning: false, unread: false },
  { day: "2026-10-27", has_learning: true, unread: false },
  { day: "2026-10-28", has_learning: true, unread: true },
  { day: "2026-10-29", has_learning: false, unread: false },
  { day: "2026-10-30", has_learning: false, unread: false },
  { day: "2026-10-31", has_learning: true, unread: true },
  { day: "2026-11-01", has_learning: false, unread: false },
];

function renderRail(overrides: Partial<Parameters<typeof DateRail>[0]> = {}) {
  const props = {
    days: DAYS,
    selected: { kind: "day" as const, day: "2026-10-28" },
    today: "2026-10-30",
    onSelectDay: vi.fn(),
    onSelectWeek: vi.fn(),
    onPrevWeek: vi.fn(),
    onNextWeek: vi.fn(),
    ...overrides,
  };
  render(<DateRail {...props} />);
  return props;
}

describe("DateRail", () => {
  it("marks only the unread days", () => {
    renderRail();
    const unread = screen
      .getAllByRole("button")
      .filter((b) => b.getAttribute("aria-label")?.includes("未読"));
    expect(unread.map((b) => b.getAttribute("aria-label"))).toEqual([
      expect.stringContaining("28"),
      expect.stringContaining("31"),
    ]);
    expect(
      screen.getByRole("button", { name: /27/ }).getAttribute("aria-label"),
    ).not.toContain("未読");
  });

  it("disables days after today", () => {
    renderRail();
    expect(screen.getByRole("button", { name: /31/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /11月1日/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /30/ })).toBeEnabled();
  });

  it("marks the selected day and reports a selection", async () => {
    const props = renderRail();
    expect(screen.getByRole("button", { name: /28/ })).toHaveAttribute(
      "aria-current",
      "date",
    );
    await userEvent.click(screen.getByRole("button", { name: /27/ }));
    expect(props.onSelectDay).toHaveBeenCalledWith("2026-10-27");
  });

  it("offers the week summary", () => {
    renderRail();
    expect(
      screen.getByRole("button", { name: "今週のまとめ" }),
    ).toBeInTheDocument();
  });

  it("moves between weeks but not past the current one", async () => {
    const props = renderRail();
    await userEvent.click(screen.getByRole("button", { name: "前の週" }));
    expect(props.onPrevWeek).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "次の週" })).toBeDisabled();
  });

  it("allows the next week from a past week", () => {
    renderRail({ today: "2026-11-05" });
    expect(screen.getByRole("button", { name: "次の週" })).toBeEnabled();
  });
});
