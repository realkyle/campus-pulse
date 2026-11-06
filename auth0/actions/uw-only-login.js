/**
 * Auth0 post-login Action: only UW accounts may sign in.
 *
 * Deployed in the Auth0 dashboard (Actions → Library → "UW only login", trigger
 * Login / Post Login). This file is the reviewed copy; keep the two in sync.
 *
 * It also copies the verified email into the access token, so the backend can
 * enforce UW-only access on every API request (defense in depth).
 */
const UW_DOMAINS = ["uw.edu", "washington.edu"];
const EMAIL_CLAIM = "https://campus-pulse/email";

exports.onExecutePostLogin = async (event, api) => {
  const email = (event.user.email || "").trim().toLowerCase();
  const isUw = UW_DOMAINS.some((domain) => email.endsWith(`@${domain}`));

  if (!isUw || !event.user.email_verified) {
    api.access.deny("Only UW accounts (@uw.edu or @washington.edu) can sign in.");
    return;
  }

  api.accessToken.setCustomClaim(EMAIL_CLAIM, email);
};
