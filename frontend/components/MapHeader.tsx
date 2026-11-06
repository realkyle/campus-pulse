"use client";

import { useState } from "react";
import AlertList from "@/components/AlertList";
import type { AlertPin } from "@/components/CampusMap";
import { colors } from "@/lib/tokens";
import { useIsMobile } from "@/lib/useMediaQuery";

interface Props {
  alerts: AlertPin[];
  loading: boolean;
  /** Name shown when signed in; null when signed out. */
  displayName: string | null;
  authLoading: boolean;
  onLogout: () => void;
}

/** Title, alert-count button (opens AlertList), and sign in / sign out. */
export default function MapHeader({ alerts, loading, displayName, authLoading, onLogout }: Props) {
  const isMobile = useIsMobile();
  const [showAlertList, setShowAlertList] = useState(false);

  return (
    <header
      style={{
        background: colors.bgPanel,
        borderBottom: `1px solid ${colors.border}`,
        padding: "12px 20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 20 }}>📍</span>
        <div>
          <h1 style={{ fontSize: 16, fontWeight: 700, color: colors.textPrimary }}>
            Campus Pulse
          </h1>
          <p style={{ fontSize: 11, color: colors.textMuted }}>
            Real-time alerts & campus activity
          </p>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {/* Website link — hidden on mobile */}
        {!isMobile && (
          <a
            href="/home"
            style={{
              fontSize: 11,
              color: colors.textDimmer,
              textDecoration: "none",
              padding: "4px 8px",
              border: `1px solid ${colors.bgPanel}`,
              borderRadius: 4,
            }}
          >
            Project Site
          </a>
        )}

        {/* Alert count badge — clickable */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => setShowAlertList((v) => !v)}
            style={{
              background: alerts.length > 0 ? colors.highBg : colors.blueDark,
              color: alerts.length > 0 ? colors.highText : colors.blueLight,
              borderRadius: 20,
              padding: "4px 12px",
              fontSize: 12,
              fontWeight: 600,
              border: "none",
              cursor: alerts.length > 0 ? "pointer" : "default",
            }}
          >
            {loading ? "Loading…" : `${alerts.length} alert${alerts.length !== 1 ? "s" : ""}`}
          </button>

          {showAlertList && alerts.length > 0 && <AlertList alerts={alerts} />}
        </div>

        {/* Auth controls */}
        {displayName ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {!isMobile && (
              <span style={{ fontSize: 12, color: colors.textMuted }}>
                Signed in as <strong style={{ color: colors.textPrimary }}>{displayName}</strong>
              </span>
            )}
            <button
              onClick={onLogout}
              style={{
                fontSize: 11,
                color: colors.textMuted,
                background: "transparent",
                border: `1px solid ${colors.border}`,
                borderRadius: 4,
                padding: "3px 8px",
                cursor: "pointer",
              }}
            >
              Sign out
            </button>
          </div>
        ) : (
          <a
            href="/auth/login"
            style={{
              fontSize: 12,
              color: colors.blueLight,
              background: "transparent",
              border: `1px solid ${colors.blueDark}`,
              borderRadius: 6,
              padding: "5px 12px",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            {authLoading ? "Loading auth…" : "Sign in with Auth0"}
          </a>
        )}
      </div>
    </header>
  );
}
