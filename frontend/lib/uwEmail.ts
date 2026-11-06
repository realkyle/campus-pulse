const UW_EMAIL_DOMAINS = ["uw.edu", "washington.edu"];

/** True for addresses ending in @uw.edu or @washington.edu (case-insensitive). */
export function isUwEmail(email: string | null | undefined): boolean {
  const normalized = (email ?? "").trim().toLowerCase();
  return UW_EMAIL_DOMAINS.some((domain) => normalized.endsWith(`@${domain}`));
}
