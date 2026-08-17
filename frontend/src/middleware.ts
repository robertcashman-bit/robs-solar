import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Must match backend `app.auth.sessions.SESSION_COOKIE`. */
const SESSION_COOKIE = "robs_solar_session";

function isPublicPath(pathname: string): boolean {
  if (pathname === "/login" || pathname.startsWith("/login/")) {
    return true;
  }
  if (pathname.startsWith("/backend")) {
    // Multi-service deploys route /backend to FastAPI; leave alone if it hits Next.
    return true;
  }
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/icons") ||
    pathname === "/favicon.ico" ||
    pathname === "/manifest.json" ||
    pathname === "/sw.js" ||
    pathname === "/robots.txt"
  ) {
    return true;
  }
  // Static installers / shortcuts
  if (
    pathname.endsWith(".js") ||
    pathname.endsWith(".css") ||
    pathname.endsWith(".png") ||
    pathname.endsWith(".ico") ||
    pathname.endsWith(".sh") ||
    pathname.endsWith(".ps1") ||
    pathname.endsWith(".py") ||
    pathname.endsWith(".url") ||
    pathname.endsWith(".webmanifest")
  ) {
    return true;
  }
  return false;
}

/**
 * Missing session cookie → hard redirect to /login before any client
 * “Loading session…” shell can render. Expired cookies still reach the
 * client gate, which clears loading and redirects after /auth/me 401.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }
  const session = request.cookies.get(SESSION_COOKIE)?.value;
  if (!session) {
    const login = request.nextUrl.clone();
    login.pathname = "/login";
    login.search = "";
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
