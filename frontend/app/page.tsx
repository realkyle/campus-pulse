"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import AlertBanner from "@/components/AlertBanner";
import RecommendationsPanel from "@/components/RecommendationsPanel";
import type { AlertPin, BusStop } from "@/components/CampusMap";
import { API_URL } from "@/lib/config";
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

async function sha256(value: string) {
  const encoded = new TextEncoder().encode(value);
  const hashBuffer = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export default function HomePage() {
  const isMobile = useWindowWidth() < 768;
  const { user, error: authError, isLoading: authLoading } = useUser();
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busStops, setBusStops] = useState<BusStop[]>([]);
  const [netid, setNetid] = useState<string | null>(null);
  const [hashedNetid, setHashedNetid] = useState<string | null>(null);
  const [major, setMajor] = useState<string | null>(null);
  const [showAlertList, setShowAlertList] = useState(false);

  useEffect(() => {
    const storedMajor = localStorage.getItem("major");
    if (storedMajor) setMajor(storedMajor);
  }, []);

  useEffect(() => {
    if (!user) {
      setNetid(null);
      setHashedNetid(null);
      return;
    }

    const displayName = user.name ?? user.email ?? user.nickname ?? user.sub ?? "Signed in user";
    setNetid(displayName);

    const sourceId = user.sub ?? displayName;
    const storedSource = localStorage.getItem("hashed_netid_source");
    const storedHash = localStorage.getItem("hashed_netid");

    if (storedSource === sourceId && storedHash) {
      setHashedNetid(storedHash);
      return;
    }

    async function createHash() {
      const hashed = await sha256(sourceId);
      localStorage.setItem("hashed_netid", hashed);
      localStorage.setItem("hashed_netid_source", sourceId);
      setHashedNetid(hashed);
    }

    createHash();
  }, [user]);

  function handleMajorChange(m: string) {
    localStorage.setItem("major", m);
    setMajor(m);
  }

  function handleLogout() {
    localStorage.removeItem("major");
    localStorage.removeItem("hashed_netid");
    localStorage.removeItem("hashed_netid_source");
    window.location.href = "/api/auth/logout";
  }

  async function fetchAlerts() {
    try {
      const res = await fetch(`${API_URL}/api/alerts`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: AlertsResponse = await res.json();
      setData(json);
    } catch {
      // Keep stale data if available; just stop showing loading spinner.
    } finally {
      setLoading(false);
    }
  }

  async function fetchBuses() {
    try {
      const res = await fetch(`${API_URL}/api/buses`);
      if (!res.ok) return;
      const json = await res.json();
      setBusStops(json.stops ?? []);
    } catch {
      // Non-critical — map still works without bus data
    }
  }

  useEffect(() => {
    fetchAlerts();
    fetchBuses();
    const alertInterval = setInterval(fetchAlerts, POLL_MS);
    const busInterval = setInterval(fetchBuses, 60_000);
    return () => {
      clearInterval(alertInterval);
      clearInterval(busInterval);
    };
  }, []);


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
              UW Bothell Campus Pulse
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
          {netid ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {!isMobile && (
                <span style={{ fontSize: 12, color: colors.textMuted }}>
                  Signed in as <strong style={{ color: colors.textPrimary }}>{netid}</strong>
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
              href="/api/auth/login"
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

        {hashedNetid && (
          <RecommendationsPanel
            hashedNetid={hashedNetid}
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
