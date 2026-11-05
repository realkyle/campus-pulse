"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import SiteNav from "@/components/SiteNav";
import type { AlertPin } from "@/components/CampusMap";
import { API_URL } from "@/lib/config";
import { colors, severity as sev } from "@/lib/tokens";

const CampusMap = dynamic(() => import("@/components/CampusMap"), { ssr: false });

const BUILDINGS = ["UW1", "UW2", "LIB", "ARC", "DISC", "HH", "NCH", "CC"];
const SEVERITIES = ["high", "medium", "low"] as const;
type Severity = typeof SEVERITIES[number];

const SEVERITY_COLORS: Record<Severity, { bg: string; border: string; text: string }> = {
  high:   sev.high,
  medium: sev.medium,
  low:    sev.low,
};

const DEMO_KEY = "campus_pulse_demos";
// sessionStorage, not localStorage: the admin token is forgotten when the tab closes.
const ADMIN_TOKEN_KEY = "campus_pulse_admin_token";

const DEMO_ERRORS: Record<number, string> = {
  401: "Wrong admin token.",
  404: "Demo alerts are turned off on this server.",
  422: "Invalid building or severity.",
  429: "5 demo alerts are already active. Clear one or wait for it to expire.",
};

type DemoEntry = { id: string; building: string; severity: Severity; expiresAt: number };

function DemoControls() {
  const [building, setBuilding] = useState("UW1");
  const [severity, setSeverity] = useState<Severity>("high");
  const [demos, setDemos] = useState<DemoEntry[]>([]);
  const [adminToken, setAdminToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function saveDemos(entries: DemoEntry[]) {
    localStorage.setItem(DEMO_KEY, JSON.stringify(entries));
    setDemos(entries);
  }

  function getRemaining(expiresAt: number) {
    return Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
  }

  function handleTokenChange(value: string) {
    setAdminToken(value);
    sessionStorage.setItem(ADMIN_TOKEN_KEY, value);
  }

  async function adminFetch(path: string, method: "POST" | "DELETE"): Promise<Response | null> {
    setError(null);
    try {
      const res = await fetch(`${API_URL}${path}`, { method, headers: { "X-Admin-Token": adminToken } });
      if (!res.ok) setError(DEMO_ERRORS[res.status] ?? `Request failed (HTTP ${res.status}).`);
      return res;
    } catch {
      setError("Could not reach the backend.");
      return null;
    }
  }

  // Restore from storage on mount and tick every second
  useEffect(() => {
    setAdminToken(sessionStorage.getItem(ADMIN_TOKEN_KEY) ?? "");
    const stored = localStorage.getItem(DEMO_KEY);
    if (stored) {
      const parsed: DemoEntry[] = JSON.parse(stored).filter((d: DemoEntry) => getRemaining(d.expiresAt) > 0);
      setDemos(parsed);
      if (parsed.length !== JSON.parse(stored).length) localStorage.setItem(DEMO_KEY, JSON.stringify(parsed));
    }
    timerRef.current = setInterval(() => {
      setDemos((prev) => {
        const active = prev.filter((d) => getRemaining(d.expiresAt) > 0);
        if (active.length !== prev.length) localStorage.setItem(DEMO_KEY, JSON.stringify(active));
        return active;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  async function handleTrigger() {
    const params = new URLSearchParams({ building, severity });
    const res = await adminFetch(`/api/demo?${params}`, "POST");
    if (!res?.ok) return;
    const data = await res.json();
    const entry: DemoEntry = { id: data.pin_id, building: data.building, severity, expiresAt: Date.now() + data.expires_in * 1000 };
    saveDemos([...demos, entry]);
  }

  async function handleClearOne(id: string) {
    const res = await adminFetch(`/api/demo/${encodeURIComponent(id)}`, "DELETE");
    // 404 means it already expired on the server, so drop it locally too.
    if (res?.ok || res?.status === 404) saveDemos(demos.filter((d) => d.id !== id));
  }

  async function handleClearAll() {
    const res = await adminFetch("/api/demo/clear", "POST");
    if (res?.ok) saveDemos([]);
  }

  return (
    <section style={{ padding: "32px 48px", borderBottom: "1px solid #1e293b" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#f1f5f9" }}>Demo Controls</h2>
        <span style={{ fontSize: 10, fontWeight: 700, color: "#f59e0b", background: "#451a03", borderRadius: 4, padding: "2px 8px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Presentation
        </span>
      </div>

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-end" }}>

        {/* Admin token: the backend rejects demo requests without it */}
        <div>
          <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Admin token</div>
          <input
            type="password"
            value={adminToken}
            onChange={(e) => handleTokenChange(e.target.value)}
            placeholder="Required"
            autoComplete="off"
            style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6, color: "#f1f5f9", fontSize: 13, padding: "8px 12px", width: 160 }}
          />
        </div>

        {/* Building selector */}
        <div>
          <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Building</div>
          <select
            value={building}
            onChange={(e) => setBuilding(e.target.value)}
            style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6, color: "#f1f5f9", fontSize: 13, padding: "8px 12px", cursor: "pointer" }}
          >
            {BUILDINGS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>

        {/* Severity toggle */}
        <div>
          <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Severity</div>
          <div style={{ display: "flex", gap: 4 }}>
            {SEVERITIES.map((s) => {
              const c = SEVERITY_COLORS[s];
              const active = severity === s;
              return (
                <button
                  key={s}
                  onClick={() => setSeverity(s)}
                  style={{ background: active ? c.bg : "#1e293b", border: `1px solid ${active ? c.border : "#334155"}`, borderRadius: 6, color: active ? c.text : "#64748b", fontSize: 12, fontWeight: 600, padding: "7px 14px", cursor: "pointer", textTransform: "capitalize" }}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </div>

        {/* Trigger button */}
        <button
          onClick={handleTrigger}
          disabled={!adminToken}
          style={{ opacity: adminToken ? 1 : 0.5, background: SEVERITY_COLORS[severity].bg, border: `1px solid ${SEVERITY_COLORS[severity].border}`, borderRadius: 6, color: SEVERITY_COLORS[severity].text, fontSize: 13, fontWeight: 700, padding: "8px 20px", cursor: adminToken ? "pointer" : "not-allowed" }}
        >
          Add Alert
        </button>

        {demos.length > 1 && (
          <button
            onClick={handleClearAll}
            style={{ background: "transparent", border: "1px solid #334155", borderRadius: 6, color: "#94a3b8", fontSize: 12, padding: "8px 14px", cursor: "pointer" }}
          >
            Clear All
          </button>
        )}
      </div>

      {/* Active demo list */}
      {demos.length > 0 && (
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 6 }}>
          {demos.map((d) => {
            const c = SEVERITY_COLORS[d.severity];
            const remaining = getRemaining(d.expiresAt);
            return (
              <div key={d.id} style={{ display: "flex", alignItems: "center", gap: 10, background: "#0f172a", border: `1px solid ${c.border}44`, borderRadius: 6, padding: "8px 12px" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: c.border, flexShrink: 0 }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: c.text, textTransform: "capitalize", minWidth: 60 }}>{d.severity}</span>
                <span style={{ fontSize: 12, color: "#f1f5f9", minWidth: 40 }}>{d.building}</span>
                <span style={{ fontSize: 11, color: "#64748b", flex: 1 }}>auto-clears in {remaining}s</span>
                <button
                  onClick={() => handleClearOne(d.id)}
                  style={{ background: "transparent", border: "1px solid #334155", borderRadius: 4, color: "#64748b", fontSize: 11, padding: "2px 8px", cursor: "pointer" }}
                >
                  Clear
                </button>
              </div>
            );
          })}
        </div>
      )}

      {error && (
        <p role="alert" style={{ fontSize: 12, color: "#fca5a5", marginTop: 12 }}>{error}</p>
      )}

      <p style={{ fontSize: 12, color: "#475569", marginTop: 12 }}>
        Admin only. Each alert appears on the map for 60 seconds, up to 5 at a time. Stack multiple alerts on different buildings simultaneously.
      </p>
    </section>
  );
}

export default function HomePage() {
  const [alerts, setAlerts] = useState<AlertPin[]>([]);

  useEffect(() => {
    fetch(`${API_URL}/api/alerts`)
      .then((r) => r.json())
      .then((d) => setAlerts(d.alerts ?? []))
      .catch(() => {});
  }, []);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#0f172a" }}>
      <SiteNav />

      <main style={{ flex: 1, overflowY: "auto" }}>
        {/* Hero */}
        <section
          style={{
            padding: "48px 48px 32px",
            borderBottom: "1px solid #1e293b",
          }}
        >
          <div
            style={{
              display: "inline-block",
              fontSize: 11,
              fontWeight: 600,
              color: "#3b82f6",
              background: "#1e3a5f",
              borderRadius: 20,
              padding: "4px 12px",
              marginBottom: 16,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            CSS 382 — Design Your Own Project
          </div>
          <h1
            style={{
              fontSize: 36,
              fontWeight: 800,
              color: "#f1f5f9",
              marginBottom: 16,
              lineHeight: 1.2,
            }}
          >
            UW Bothell Campus Pulse
          </h1>
          <p
            style={{
              fontSize: 16,
              color: "#94a3b8",
              maxWidth: 600,
              lineHeight: 1.7,
              marginBottom: 32,
            }}
          >
            Students at UW Bothell frequently miss critical campus information — club
            events, guest lectures, and emergency alerts — because email is an
            unreliable channel many students ignore. Campus Pulse is a real-time
            browser-based map of UW Bothell that automatically surfaces alerts and
            personalized event recommendations from official university sources.
          </p>

          {/* Stat chips */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {[
              { label: "AI-powered alerts", sub: "GPT-4o-mini NLP" },
              { label: "Personalized feed", sub: "Collaborative filtering" },
              { label: "FERPA compliant", sub: "Hashed user ID storage" },
              { label: "No account required", sub: "Core map is public" },
            ].map(({ label, sub }) => (
              <div
                key={label}
                style={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  padding: "12px 16px",
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600, color: "#f1f5f9" }}>
                  {label}
                </div>
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                  {sub}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Live map embed */}
        <section style={{ padding: "32px 48px", borderBottom: "1px solid #1e293b" }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#f1f5f9", marginBottom: 16 }}>
            Live Demo
          </h2>
          <div
            style={{
              borderRadius: 10,
              overflow: "hidden",
              border: "1px solid #334155",
              height: 480,
            }}
          >
            <CampusMap alerts={alerts} />
          </div>
          <p style={{ fontSize: 12, color: "#475569", marginTop: 8 }}>
            Live map — pins update every 5 minutes from the UW Alerts RSS feed.
          </p>
        </section>

        <DemoControls />

        {/* Tech stack */}
        <section style={{ padding: "32px 48px 48px" }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#f1f5f9", marginBottom: 20 }}>
            Tech Stack
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 12,
            }}
          >
            {[
              { layer: "Frontend",  tech: "Next.js 14 + TypeScript" },
              { layer: "Map",       tech: "OpenStreetMap + Leaflet" },
              { layer: "Backend",   tech: "FastAPI + Python 3.11" },
              { layer: "AI Alerts", tech: "GPT-4o-mini (OpenAI)" },
              { layer: "Recommender", tech: "Surprise (SVD)" },
              { layer: "Database",  tech: "PostgreSQL / Supabase" },
              { layer: "Auth",       tech: "Auth0 (UW login)" },
              { layer: "Deployment", tech: "Vercel + Render" },
            ].map(({ layer, tech }) => (
              <div
                key={layer}
                style={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  padding: "14px 16px",
                }}
              >
                <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                  {layer}
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0" }}>
                  {tech}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
