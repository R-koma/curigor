import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/auth-client", () => ({
  authClient: {
    emailOtp: { sendVerificationOtp: vi.fn() },
    signIn: { emailOtp: vi.fn(), social: vi.fn() },
  },
}));

import { SignInForm } from "@/components/auth/sign-in-form";

describe("auth forms guard against native GET submissions", () => {
  it("sign-in form uses method=post", () => {
    const { container } = render(<SignInForm showDevCodeHint={false} />);
    const form = container.querySelector("#sign-in-form");
    expect(form).not.toBeNull();
    expect(form?.getAttribute("method")).toBe("post");
  });
});
