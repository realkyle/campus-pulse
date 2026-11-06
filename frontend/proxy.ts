import { NextResponse } from "next/server";
import { auth0 } from "./lib/auth0";

// Next.js 16 "proxy" (formerly middleware): mounts the /auth/* routes and
// keeps the session cookie rolling on every request.
export async function proxy(request: Request) {
  try {
    return await auth0.middleware(request);
  } catch (error) {
    // A login problem (e.g. missing AUTH0_* env vars) must not take down the
    // public map: serve normal pages as usual and fail only the /auth routes.
    console.error("Auth0 proxy failed:", error);
    if (new URL(request.url).pathname.startsWith("/auth/")) {
      return new NextResponse("Login is temporarily unavailable.", { status: 503 });
    }
    return NextResponse.next();
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)"],
};
