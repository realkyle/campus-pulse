"use client";

import { colors } from "@/lib/tokens";
import { useLoginError } from "@/lib/useLoginError";

/** Explains a refused sign-in (e.g. a non-UW account); dismissible. */
export default function LoginErrorBanner() {
  const { message, dismiss } = useLoginError();
  if (!message) return null;
  return (
    <div role="alert" style={{ background: colors.highBg, color: colors.highText, padding: "8px 16px", fontSize: 13, display: "flex", justifyContent: "space-between", gap: 12 }}>
      <span>{message}</span>
      <button onClick={dismiss} aria-label="Dismiss" style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", fontSize: 14 }}>✕</button>
    </div>
  );
}
