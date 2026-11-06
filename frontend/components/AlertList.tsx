"use client";

import type { AlertPin } from "@/components/CampusMap";
import { colors, severity as sev } from "@/lib/tokens";

/** The alert-count button's dropdown: every current alert, pinned or not. */
export default function AlertList({ alerts }: { alerts: AlertPin[] }) {
  return (
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
  );
}
