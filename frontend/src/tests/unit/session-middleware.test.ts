import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { middleware } from "@/middleware";

function request(path: string, cookie?: string) {
  const headers = new Headers();
  if (cookie) {
    headers.set("cookie", cookie);
  }
  return middleware(new NextRequest(new URL(path, "https://robs-solar.vercel.app"), { headers }));
}

describe("session middleware", () => {
  it("redirects protected routes to /login when the session cookie is missing", () => {
    const response = request("/");
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://robs-solar.vercel.app/login");
  });

  it("allows /login without a session cookie", () => {
    const response = request("/login");
    expect(response.status).toBe(200);
  });

  it("allows finance pages when the session cookie is present", () => {
    const response = request("/finance/transactions", "robs_solar_session=abc");
    expect(response.status).toBe(200);
  });
});
