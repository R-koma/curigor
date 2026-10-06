import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SignInPreview } from "@/app/sign-in-preview/preview";

describe("SignInPreview", () => {
  it("renders every sample without throwing", () => {
    const { container } = render(<SignInPreview />);
    expect(
      screen.getByRole("heading", { name: "ログイン画面の見本" }),
    ).toBeInTheDocument();
    expect(container.querySelector("iframe")).not.toBeNull();
  });
});
