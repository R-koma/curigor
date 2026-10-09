import { describe, it, expect, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { SwipeToDelete } from "@/components/notes/swipe-to-delete";
import { COARSE_POINTER, setMediaQuery } from "../stubs/match-media";

function setup(onDelete = vi.fn(), onOpen = vi.fn()) {
  render(
    <SwipeToDelete label="「二分探索」を削除" onDelete={onDelete}>
      <a href="#note" onClick={onOpen}>
        二分探索
      </a>
    </SwipeToDelete>,
  );
  return { onDelete, onOpen };
}

function panel() {
  return screen.getByTestId("swipe-panel");
}

function swipe(dx: number, dy = 0) {
  const target = screen.getByText("二分探索");
  fireEvent.touchStart(target, { touches: [{ clientX: 200, clientY: 100 }] });
  fireEvent.touchMove(target, {
    touches: [{ clientX: 200 + dx / 2, clientY: 100 + dy / 2 }],
  });
  fireEvent.touchMove(target, {
    touches: [{ clientX: 200 + dx, clientY: 100 + dy }],
  });
  fireEvent.touchEnd(target, { changedTouches: [{ clientX: 200 + dx }] });
}

function coarse() {
  act(() => setMediaQuery(COARSE_POINTER, true));
}

describe("SwipeToDelete", () => {
  it("renders only its content with a fine pointer", () => {
    setup();
    expect(
      screen.queryByRole("button", { name: "「二分探索」を削除" }),
    ).toBeNull();
  });

  it("reveals the delete button after a left swipe and deletes on tap", () => {
    coarse();
    const { onDelete } = setup();
    swipe(-120);
    expect(panel().style.transform).toBe("translateX(-88px)");
    fireEvent.click(screen.getByRole("button", { name: "「二分探索」を削除" }));
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(panel().style.transform).toBe("translateX(0px)");
  });

  it("snaps back after a short swipe", () => {
    coarse();
    setup();
    swipe(-30);
    expect(panel().style.transform).toBe("translateX(0px)");
  });

  it("ignores a vertical drag so the page can scroll", () => {
    coarse();
    setup();
    swipe(-20, 120);
    expect(panel().style.transform).toBe("translateX(0px)");
  });

  it("closes instead of opening the note when the open card is tapped", () => {
    coarse();
    const { onOpen } = setup();
    swipe(-120);
    fireEvent.click(screen.getByText("二分探索"));
    expect(onOpen).not.toHaveBeenCalled();
    expect(panel().style.transform).toBe("translateX(0px)");
  });

  it("opens the note on a plain tap", () => {
    coarse();
    const { onOpen } = setup();
    fireEvent.click(screen.getByText("二分探索"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
