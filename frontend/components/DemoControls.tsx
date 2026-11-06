"use client";

import { useState } from "react";
import { fetchAsUser } from "@/lib/api";
import { severity as sev } from "@/lib/tokens";
import { useLocalStorageValue } from "@/lib/useLocalStorageValue";
import { useNow } from "@/lib/useNow";

const BUILDINGS = ["UW1", "UW2", "LIB", "ARC", "DISC", "HH", "NCH", "CC"];
const SEVERITIES = ["high", "medium", "low"] as const;
type Severity = typeof SEVERITIES[number];

const SEVERITY_COLORS: Record<Severity, { bg: string; border: string; text: string }> = {
  high:   sev.high,
  medium: sev.medium,
  low:    sev.low,
};

const DEMO_KEY = "campus_pulse_demos";

const DEMO_ERRORS: Record<number, string> = {
  401: "Your session expired. Please sign in again.",
  403: "Admins only.",
  404: "That demo alert already expired.",
  422: "Invalid building or severity.",
  429: "5 demo alerts are already active. Clear one or wait for it to expire.",
};

type DemoEntry = { id: string; building: string; severity: Severity; expiresAt: number };

function parseDemos(stored: string | null): DemoEntry[] {
  try {
    return stored ? (JSON.parse(stored) as DemoEntry[]) : [];
  } catch {
    return []; // unreadable leftovers from an older version
  }
}

/** Admin-only fake alerts for presentations (api/demo.md); shown only when /api/me says is_admin. */
export default function DemoControls() {
  const [building, setBuilding] = useState("UW1");
  const [severity, setSeverity] = useState<Severity>("high");
  const [error, setError] = useState<string | null>(null);
  // Demo pins survive a reload: they live in localStorage, read without an effect.
  const [storedDemos, setStoredDemos] = useLocalStorageValue(DEMO_KEY);
  const now = useNow(1000); // ticks the countdowns once a second
  const demos = parseDemos(storedDemos).filter((d) => d.expiresAt > now);

  function saveDemos(entries: DemoEntry[]) {
    setStoredDemos(JSON.stringify(entries));
  }

  function getRemaining(expiresAt: number) {
    return Math.max(0, Math.ceil((expiresAt - now) / 1000));
  }

  async function adminFetch(path: string, method: "POST" | "DELETE"): Promise<Response | null> {
    setError(null);
    try {
      // The backend checks the demo:write permission inside the signed access token.
      const res = await fetchAsUser(path, { method });
      if (!res.ok) setError(DEMO_ERRORS[res.status] ?? `Request failed (HTTP ${res.status}).`);
      return res;
    } catch {
      setError("Your session expired. Please sign in again.");
      return null;
    }
  }

  async function handleTrigger() {
    const params = new URLSearchParams({ building, severity });
    const res = await adminFetch(`/api/demo?${params}`, "POST");
    if (!res?.ok) return;
    const data = await res.json();
    // `now` (from useNow, at most 1 s old) instead of Date.now(): accurate enough for a
    // 60 s countdown, and keeps the component free of impure calls.
    const entry: DemoEntry = { id: data.pin_id, building: data.building, severity, expiresAt: now + data.expires_in * 1000 };
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
          style={{ background: SEVERITY_COLORS[severity].bg, border: `1px solid ${SEVERITY_COLORS[severity].border}`, borderRadius: 6, color: SEVERITY_COLORS[severity].text, fontSize: 13, fontWeight: 700, padding: "8px 20px", cursor: "pointer" }}
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
