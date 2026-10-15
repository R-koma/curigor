// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxy } from "@/proxy";

const REPORT_ONLY = "content-security-policy-report-only";
const ENFORCE = "content-security-policy";

function call() {
  return proxy(new NextRequest("http://localhost:3000/dashboard"));
}

describe("proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("reports violations without blocking by default", () => {
    const response = call();
    expect(response.headers.get(REPORT_ONLY)).toContain("'strict-dynamic'");
    expect(response.headers.get(ENFORCE)).toBeNull();
  });

  it("enforces the policy when CSP_ENFORCE is true", () => {
    vi.stubEnv("CSP_ENFORCE", "true");
    const response = call();
    expect(response.headers.get(ENFORCE)).toContain("'strict-dynamic'");
    expect(response.headers.get(REPORT_ONLY)).toBeNull();
  });

  it.each(["1", "TRUE", "yes", ""])(
    "keeps reporting only when CSP_ENFORCE is %j",
    (value) => {
      vi.stubEnv("CSP_ENFORCE", value);
      const response = call();
      expect(response.headers.get(REPORT_ONLY)).not.toBeNull();
      expect(response.headers.get(ENFORCE)).toBeNull();
    },
  );

  it("passes the page the same nonce and policy as the response header", () => {
    const response = call();
    const nonce = response.headers.get("x-middleware-request-x-nonce");
    const policy = response.headers.get(REPORT_ONLY);
    expect(nonce).toBeTruthy();
    expect(policy).toContain(`'nonce-${nonce}'`);
    expect(response.headers.get(`x-middleware-request-${REPORT_ONLY}`)).toBe(
      policy,
    );
  });

  it("issues a new nonce for every request", () => {
    const first = call().headers.get("x-middleware-request-x-nonce");
    const second = call().headers.get("x-middleware-request-x-nonce");
    expect(first).not.toBe(second);
  });

  it("allows eval only in development", () => {
    expect(call().headers.get(REPORT_ONLY)).not.toContain("'unsafe-eval'");
    vi.stubEnv("NODE_ENV", "development");
    expect(call().headers.get(REPORT_ONLY)).toContain("'unsafe-eval'");
  });
});
