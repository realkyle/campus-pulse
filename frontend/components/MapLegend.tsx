import { colors, severity as sev } from "@/lib/tokens";

/** Pin colors and the bus marker, under the map. */
export default function MapLegend() {
  return (
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
  );
}
