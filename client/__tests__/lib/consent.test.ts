import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import {
  CONSENT_PATH,
  fetchConsentStatus,
  goToConsent,
  submitConsent,
} from "@/lib/consent";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchConsentStatus", () => {
  it("returns the status with the token for the cookie", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ token: "jwt" }))
      .mockResolvedValueOnce(
        jsonResponse({ terms_version: 1, consented: false }),
      );
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchConsentStatus("session=abc")).toEqual({
      terms_version: 1,
      consented: false,
    });
    expect(fetchMock.mock.calls[0][1].headers).toEqual({
      Cookie: "session=abc",
    });
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/api\/consents\/me$/);
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer jwt");
  });

  it("returns null when the API cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ token: "jwt" }))
        .mockRejectedValueOnce(new TypeError("fetch failed")),
    );

    expect(await fetchConsentStatus("")).toBeNull();
  });
});

describe("submitConsent", () => {
  it("posts the version the user read", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ token: "jwt" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await submitConsent(3);

    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toMatch(/\/api\/consents$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ terms_version: 3 });
  });

  it("throws the error code when the terms were updated", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ token: "jwt" }))
        .mockResolvedValueOnce(
          jsonResponse(
            {
              code: "terms_version_outdated",
              detail: "Terms have been updated",
            },
            409,
          ),
        ),
    );

    await expect(submitConsent(1)).rejects.toMatchObject(
      new ApiError(409, "terms_version_outdated", "Terms have been updated"),
    );
  });
});

describe("goToConsent", () => {
  it("navigates to the consent screen", () => {
    const assign = vi.fn();

    goToConsent(assign);

    expect(assign).toHaveBeenCalledWith(CONSENT_PATH);
  });
});
