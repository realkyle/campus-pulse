import { NextResponse } from "next/server";
import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { isUwEmail } from "./uwEmail";

/**
 * Server-side Auth0 client. Reads AUTH0_DOMAIN, AUTH0_CLIENT_ID,
 * AUTH0_CLIENT_SECRET, AUTH0_SECRET and APP_BASE_URL from the environment.
 *
 * UW-only access is enforced by an Auth0 post-login Action (auth0/actions/)
 * and, from the next PR, by the backend on every request. The check here is a
 * safety net: the SDK saves the session even when this hook objects, so a
 * non-UW login is sent straight to /auth/logout, which clears it.
 */
export const auth0 = new Auth0Client({
  authorizationParameters: {
    // Always show the login screen. Without this, Auth0 silently reuses the
    // last session: after a refused (non-UW) login, every "Sign in" click was
    // refused again instantly and bounced back home, with no way to switch accounts.
    prompt: "login",
    // Request access tokens for the Campus Pulse API, so the backend can verify
    // them (without an audience, Auth0 issues a token only it can read).
    audience: process.env.AUTH0_AUDIENCE,
  },
  async onCallback(error, context, session) {
    const base = context.appBaseUrl ?? process.env.APP_BASE_URL ?? "http://localhost:3000";
    if (error) {
      // The UW-only Action refuses a login with OAuth error "access_denied".
      const cause = (error as { cause?: { code?: string; message?: string } }).cause;
      const reason = cause?.code === "access_denied" ? "uw_only" : "failed";
      // Code plus Auth0's description, e.g. "invalid_request: <why>", for debugging.
      console.error("Login failed:", cause?.code ?? error.message, cause?.message ? `: ${cause.message}` : "");
      return NextResponse.redirect(new URL(`/?login_error=${reason}`, base));
    }
    if (session && !isUwEmail(session.user.email)) {
      // Sent to logout to clear the session; the Action normally blocks this earlier.
      return NextResponse.redirect(new URL("/auth/logout", base));
    }
    return NextResponse.redirect(new URL(context.returnTo ?? "/", base));
  },
});
