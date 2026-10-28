import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

import type { Operator } from "@/lib/legal";

const legal = vi.hoisted(() => ({ operator: null as Operator | null }));

vi.mock("@/lib/legal", () => ({
  get OPERATOR() {
    return legal.operator;
  },
  PRIVACY_POLICY_EFFECTIVE_DATE: "2026年10月16日",
  PRIVACY_POLICY_REVISED_DATE: "2026年10月27日",
}));

vi.mock("@/lib/auth-client", () => ({
  authClient: {
    useSession: () => ({ data: null, isPending: false }),
  },
}));

import PrivacyPage from "@/app/privacy/page";
import LandingFooter from "@/components/landing/landing-footer";

function section(name: string): HTMLElement {
  const heading = screen.getByRole("heading", { level: 2, name });
  return heading.closest("section") as HTMLElement;
}

function notFoundDigest(): string | undefined {
  try {
    PrivacyPage();
  } catch (error) {
    return (error as { digest?: string }).digest;
  }
  return undefined;
}

beforeEach(() => {
  legal.operator = { name: "運営 太郎", email: "contact@example.com" };
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("privacy page", () => {
  it("shows the operator and contact", () => {
    render(<PrivacyPage />);
    const operator = section("1. 運営者");
    expect(within(operator).getByText("運営 太郎")).toBeInTheDocument();
    expect(
      within(operator).getByText("contact@example.com"),
    ).toBeInTheDocument();
  });

  it("states the retention periods decided in ADR-016", () => {
    render(<PrivacyPage />);
    const retention = section("6. 保存期間");
    expect(
      within(retention).getByText(
        "アカウントがある間は保存し、アカウントの削除で消します",
      ),
    ).toBeInTheDocument();
    expect(
      within(retention).getByText(/ログインの有効期限が切れるまで/),
    ).toBeInTheDocument();
    expect(
      within(retention).getByText("Google のアクセストークンなど"),
    ).toBeInTheDocument();
    expect(
      within(retention).getByText(/Langfuse の保存期間/),
    ).toBeInTheDocument();
  });

  it("lists Cloudflare among the recipients abroad for the human check", () => {
    render(<PrivacyPage />);
    const recipients = section("4. 外国にある第三者への提供");
    const row = within(recipients).getByText("Cloudflare").closest("tr");
    expect(row).toHaveTextContent("米国");
    expect(row).toHaveTextContent("Turnstile");
  });

  it("shows when the policy was last revised", () => {
    render(<PrivacyPage />);
    expect(screen.getByText(/改定日:\s*2026年10月27日/)).toBeInTheDocument();
  });

  it("describes how to delete the account", () => {
    render(<PrivacyPage />);
    const deletion = section("7. アカウントの削除");
    expect(
      within(deletion).getByText(/「アカウントを削除」/),
    ).toBeInTheDocument();
    expect(
      within(deletion).getByText(/ログインから 1 日以内/),
    ).toBeInTheDocument();
    expect(
      within(deletion).getByText(/問い合わせ（contact@example.com/),
    ).toBeInTheDocument();
  });

  it("responds with not found in production until the operator is set", () => {
    legal.operator = null;
    vi.stubEnv("NODE_ENV", "production");
    expect(notFoundDigest()).toMatch(/NEXT_HTTP_ERROR_FALLBACK;404/);
  });

  it("renders with placeholders outside production until the operator is set", () => {
    legal.operator = null;
    render(<PrivacyPage />);
    expect(within(section("1. 運営者")).getAllByText("（未定）")).toHaveLength(
      2,
    );
  });
});

describe("landing footer", () => {
  it("links to the privacy policy once the operator is set", () => {
    const { container } = render(<LandingFooter />);
    expect(container.querySelector('a[href="/privacy"]')).not.toBeNull();
  });

  it("hides the link until the operator is set", () => {
    legal.operator = null;
    const { container } = render(<LandingFooter />);
    expect(container.querySelector('a[href="/privacy"]')).toBeNull();
  });
});
