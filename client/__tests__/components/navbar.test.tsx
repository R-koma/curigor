import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Navbar } from "@/components/layout/navbar";

vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({ navbarCenter: <span>中央のスロット</span> }),
}));

describe("Navbar", () => {
  it("renders only the center slot, without the account or theme controls", () => {
    render(<Navbar />);
    expect(screen.getByText("中央のスロット")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
