import { useEffect, useState, useSyncExternalStore } from "react";

// lib/auth0.ts redirects to "/?login_error=uw_only|failed" after a refused login.
// Read once per page load (never on the server), and cleared when dismissed.
let pendingLoginError: string | null =
  typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("login_error");
const noSubscription = () => () => {};

const MESSAGES: Record<string, string> = {
  uw_only: "Only UW accounts (@uw.edu or @washington.edu) can sign in. Sign in again and choose your UW Google account.",
  failed: "Sign-in failed. Please try again.",
};

/** The message for a refused login, if this page load came from one, and a way to dismiss it. */
export function useLoginError(): { message: string | null; dismiss: () => void } {
  const reason = useSyncExternalStore(noSubscription, () => pendingLoginError, () => null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // So a refresh doesn't show the message again. (No state change here.)
    if (pendingLoginError) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  return {
    message: reason && !dismissed ? (MESSAGES[reason] ?? MESSAGES.failed) : null,
    dismiss: () => {
      pendingLoginError = null;
      setDismissed(true);
    },
  };
}
