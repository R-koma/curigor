import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const RAW_PALETTE =
  /\b(?:bg|text|border)-(?:blue|emerald|amber|orange|indigo|slate)-\d{2,3}/;

describe("Button", () => {
  it("renders the brand variant with brand tokens", () => {
    render(<Button variant="brand">続ける</Button>);
    const button = screen.getByRole("button", { name: "続ける" });
    expect(button).toHaveClass("bg-brand", "text-brand-foreground");
    expect(button.className).not.toMatch(RAW_PALETTE);
  });

  it("keeps the default variant on primary", () => {
    render(<Button>既定</Button>);
    expect(screen.getByRole("button", { name: "既定" })).toHaveClass(
      "bg-primary",
    );
  });
});

describe("Badge", () => {
  it.each([
    ["info", "bg-brand-soft", "text-brand-text"],
    ["success", "bg-success-soft", "text-success-text"],
    ["warning", "bg-warning-soft", "text-warning-text"],
  ] as const)("%s uses status tokens", (variant, soft, text) => {
    render(<Badge variant={variant}>ラベル</Badge>);
    const badge = screen.getByText("ラベル");
    expect(badge).toHaveClass(soft, text);
    expect(badge.className).not.toMatch(RAW_PALETTE);
    expect(badge.className).not.toContain("dark:bg-");
  });

  it("applies the hover tint only when rendered as a link", () => {
    render(<Badge variant="info">ラベル</Badge>);
    const classes = screen.getByText("ラベル").className;
    expect(classes).toContain("[a]:hover:bg-brand/20");
    expect(classes).not.toMatch(/(^|\s)hover:/);
  });
});
