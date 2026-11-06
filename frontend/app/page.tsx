"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useUser } from "@auth0/nextjs-auth0";
import AlertBanner from "@/components/AlertBanner";
import RecommendationsPanel from "@/components/RecommendationsPanel";
import type { AlertPin, BusStop } from "@/components/CampusMap";
import { API_URL } from "@/lib/config";
import { useLocalStorageValue } from "@/lib/useLocalStorageValue";
import { usePolledJson } from "@/lib/usePolledJson";
import { useWindowWidth } from "@/lib/useWindowWidth";
import { colors, severity as sev } from "@/lib/tokens";

// Leaflet uses browser APIs — must be loaded client-side only.
const CampusMap = dynamic(() => import("@/components/CampusMap"), { ssr: false });
const POLL_MS = 30_000;

interface AlertsResponse {
  alerts: AlertPin[];
  last_updated: string;
  ai_available: boolean;
  feed_available: boolean;
}

// lib/auth0.ts redirects to "/?login_error=uw_only|failed" after a refused login.
// Read once per page load (never on the server), and cleared when dismissed.
let pendingLoginError: string | null =
  typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("login_error");
const noSubscription = () => () => {};

const LOGIN_ERROR_TEXT: Record<string, string> = {
  uw_only: "Only UW accounts (@uw.edu or @washington.edu) can sign in. Sign in again and choose your UW Google account.",
  failed: "Sign-in failed. Please try again.",
};

export default function HomePage() {
  const isMobile = useWindowWidth() < 768;
  const { user, isLoading: authLoading } = useUser();
  const alertsPoll = usePolledJson<AlertsResponse>(`${API_URL}/api/alerts`, POLL_MS);
  const busPoll = usePolledJson<{ stops: BusStop[] }>(`${API_URL}/api/buses`, 60_000);
  const data = alertsPoll.data;
  const loading = !alertsPoll.loaded;
  const busStops = busPoll.data?.stops ?? [];
  const [major, setStoredMajor] = useLocalStorageValue("major");
  const [showAlertList, setShowAlertList] = useState(false);

  const loginReason = useSyncExternalStore(noSubscription, () => pendingLoginError, () => null);
  const [loginErrorDismissed, setLoginErrorDismissed] = useState(false);
  const loginError = loginReason && !loginErrorDismissed ? (LOGIN_ERROR_TEXT[loginReason] ?? LOGIN_ERROR_TEXT.failed) : null;

  useEffect(() => {
    // So a refresh doesn't show the message again. (No state change here.)
    if (pendingLoginError) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  function dismissLoginError() {
    pendingLoginError = null;
    setLoginErrorDismissed(true);
  }

  // The backend identifies the user from the access token (lib/api.ts); the
  // browser no longer computes or stores a user ID.
  const displayName = user ? (user.name ?? user.email ?? "Signed in user") : null;

  function handleMajorChange(m: string) {
    setStoredMajor(m);
  }

  function handleLogout() {
    localStorage.removeItem("major");
    // Left over from the old client-side user ID; remove it from existing browsers.
    localStorage.removeItem("hashed_netid");
    localStorage.removeItem("hashed_netid_source");
    // A full page load on purpose: /auth/logout is the Auth0 route, not a Next.js page.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/auth/logout";
  }


  const alerts = data?.alerts ?? [];


  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      {/* Header */}
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

            {showAlertList && alerts.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  right: 0,
                  width: 320,
                  background: colors.bgPanel,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 8,
                  boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
                  zIndex: 2000,
                  overflow: "hidden",
                }}
              >
                <div style={{ padding: "10px 14px", borderBottom: `1px solid ${colors.border}`, fontSize: 11, fontWeight: 700, color: colors.textFaint, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Active Alerts
                </div>
                {alerts.map((alert) => {
                  const sevColor = (sev[alert.severity as keyof typeof sev] ?? sev.medium).pin;
                  return (
                    <div key={alert.id} style={{ padding: "12px 14px", borderBottom: `1px solid ${colors.bgBase}`, display: "flex", gap: 10, alignItems: "flex-start" }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: sevColor, flexShrink: 0, marginTop: 4 }} />
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: colors.textPrimary, marginBottom: 2 }}>
                          {alert.incident_type} — {alert.scope === "university" ? "All UW campuses" : alert.building_name}
                        </div>
                        <div style={{ fontSize: 11, color: colors.textMuted, lineHeight: 1.5 }}>
                          {alert.raw_text.length > 100 ? alert.raw_text.slice(0, 100) + "…" : alert.raw_text}
                        </div>
                        <div style={{ fontSize: 10, color: colors.textDimmer, marginTop: 4 }}>
                          {new Date(alert.published).toLocaleString()}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
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
                onClick={handleLogout}
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

      {loginError && (
        <div role="alert" style={{ background: colors.highBg, color: colors.highText, padding: "8px 16px", fontSize: 13, display: "flex", justifyContent: "space-between", gap: 12 }}>
          <span>{loginError}</span>
          <button onClick={dismissLoginError} aria-label="Dismiss" style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
      )}

      {/* Status banners */}
      {data && (
        <AlertBanner
          aiAvailable={data.ai_available}
          feedAvailable={data.feed_available}
          lastUpdated={data.last_updated}
        />
      )}

      {/* Map + optional recommendations panel */}
      <main style={{ flex: 1, display: "flex", flexDirection: isMobile ? "column" : "row", overflow: "hidden" }}>
        <div style={{ flex: 1, position: "relative", height: isMobile ? "60vh" : "auto" }}>
          {loading && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(15,23,42,0.7)",
                zIndex: 1000,
                fontSize: 14,
                color: colors.textMuted,
              }}
            >
              Loading campus map…
            </div>
          )}
          <CampusMap alerts={alerts} busStops={busStops} />
          {!loading && alerts.length === 0 && (
            <div style={{
              position: "absolute",
              top: 12,
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 1000,
              background: colors.lowBg,
              border: `1px solid ${colors.lowBorder}`,
              color: colors.lowText,
              borderRadius: 20,
              padding: "6px 18px",
              fontSize: 12,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 6,
              pointerEvents: "none",
            }}>
              ✓ No active alerts — campus is clear
            </div>
          )}
        </div>

        {user && (
          <RecommendationsPanel
            key={major ?? ""} // a new major resets the panel's state (fresh list, page 1)
            major={major}
            onMajorChange={handleMajorChange}
          />
        )}
      </main>

      {/* Legend */}
      <footer
        style={{
          background: colors.bgPanel,
          borderTop: `1px solid ${colors.border}`,
          padding: "8px 16px",
          display: "flex",
          gap: 20,
          alignItems: "center",
          flexShrink: 0,
        }}
      >
        {(["high", "medium", "low"] as const).map((level) => (
          <div key={level} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <svg width="10" height="14" viewBox="0 0 28 38" style={{ flexShrink: 0 }}>
              <path d="M14 0C6.27 0 0 6.27 0 14c0 10.5 14 24 14 24s14-13.5 14-24C28 6.27 21.73 0 14 0z" fill={sev[level].pin} stroke="white" strokeWidth="3"/>
            </svg>
            <span style={{ fontSize: 11, color: colors.textMuted }}>
              {level.charAt(0).toUpperCase() + level.slice(1)} severity
            </span>
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ background: colors.busBg, border: `1.5px solid ${colors.busPin}`, borderRadius: 3, padding: "1px 4px", fontSize: 8, fontWeight: 800, color: colors.busPin, letterSpacing: "0.05em" }}>BUS</span>
          <span style={{ fontSize: 11, color: colors.textMuted }}>Bus stop</span>
        </div>
        <span style={{ marginLeft: "auto", fontSize: 11, color: colors.textDimmer }}>
          Click a pin for details
        </span>
      </footer>
    </div>
  );
}
