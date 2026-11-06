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
  async onCallback(error, context, session) {
    const base = context.appBaseUrl ?? process.env.APP_BASE_URL ?? "http://localhost:3000";
    if (error) {
      return NextResponse.redirect(new URL("/?login_error=failed", base));
    }
    if (session && !isUwEmail(session.user.email)) {
      return NextResponse.redirect(new URL("/auth/logout", base));
    }
    return NextResponse.redirect(new URL(context.returnTo ?? "/", base));
  },
});
