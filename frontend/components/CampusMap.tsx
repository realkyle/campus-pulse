"use client";

import { MapContainer, TileLayer, Marker, Popup, Tooltip } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { colors, severity as sev } from "@/lib/tokens";

export interface AlertPin {
  id: string;
  raw_text: string;
  building_name: string;
  incident_type: string;
  severity: "low" | "medium" | "high";
  recommended_action: string;
  /** "campus" alerts are pinned; "university" alerts have no coordinates and appear only in the alert list. */
  scope: "campus" | "university";
  coordinates: [number, number] | null;
  published: string;
  headline?: string;
  safety_brief?: string;
}

export interface BusArrival {
  route: string;
  headsign: string;
  minutes: number;
  predicted: boolean;
}

export interface BusStop {
  id: string;
  name: string;
  lat: number;
  lon: number;
  arrivals: BusArrival[];
}

// Campus center and bounding box
const CENTER: [number, number] = [47.7594, -122.1903];
const BOUNDS: [[number, number], [number, number]] = [
  [47.753, -122.198],
  [47.766, -122.182],
];

function alertIcon(color: string, isHigh = false): L.DivIcon {
  const pulse = isHigh ? `
    <circle cx="14" cy="14" r="13" fill="${color}" opacity="0.5">
      <animate attributeName="r" from="13" to="38" dur="1.8s" repeatCount="indefinite"/>
      <animate attributeName="opacity" from="0.5" to="0" dur="1.8s" repeatCount="indefinite"/>
    </circle>` : "";
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38" overflow="visible">
      ${pulse}
      <path d="M14 0C6.27 0 0 6.27 0 14c0 10.5 14 24 14 24s14-13.5 14-24C28 6.27 21.73 0 14 0z"
        fill="${color}" stroke="white" stroke-width="2.5"/>
      <circle cx="14" cy="14" r="5.5" fill="white" fill-opacity="0.35"/>
    </svg>`;
  return L.divIcon({
    html: `<div style="filter:drop-shadow(0 3px 6px rgba(0,0,0,0.45))">${svg}</div>`,
    className: "",
    iconSize: [28, 38],
    iconAnchor: [14, 38],
    popupAnchor: [0, -40],
  });
}

function busIcon(): L.DivIcon {
  const html = `
    <div style="
      width: 38px; height: 24px;
      background: ${colors.busBg};
      border: 2.5px solid ${colors.busPin};
      border-radius: 6px;
      color: ${colors.busPin};
      font-size: 10px;
      font-weight: 800;
      font-family: sans-serif;
      letter-spacing: 0.05em;
      box-shadow: 0 3px 8px rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      box-sizing: border-box;
    ">BUS</div>`;
  return L.divIcon({
    html,
    className: "",
    iconSize: [38, 24],
    iconAnchor: [19, 12],
    popupAnchor: [0, -16],
  });
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function CampusMap({ alerts, busStops = [] }: { alerts: AlertPin[]; busStops?: BusStop[] }) {
  return (
    <MapContainer
      center={CENTER}
      zoom={16}
      maxBounds={BOUNDS}
      maxBoundsViscosity={0.8}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />

      {/* Alert pins: only campus alerts have coordinates; university-wide ones are list-only */}
      {alerts.filter((pin): pin is AlertPin & { coordinates: [number, number] } => pin.coordinates !== null).map((pin) => {
        const s = sev[pin.severity] ?? sev.medium;
        return (
          <Marker
            key={pin.id}
            position={pin.coordinates}
            icon={alertIcon(s.pin, pin.severity === "high")}
          >
            <Tooltip direction="top" offset={[0, -42]} opacity={1}>
              <div style={{ fontSize: 12, lineHeight: 1.4 }}>
                <strong>{pin.incident_type}</strong>
                <span style={{ marginLeft: 6, padding: "1px 5px", borderRadius: 3, background: s.pin, color: "#fff", fontSize: 10, fontWeight: 700 }}>
                  {pin.severity.toUpperCase()}
                </span>
                <div style={{ color: colors.textDimmer, marginTop: 2 }}>{pin.building_name}</div>
              </div>
            </Tooltip>
            <Popup>
              <div style={{ padding: "10px 12px", minWidth: 240 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                  <strong style={{ fontSize: 14, color: colors.bgBase }}>
                    {pin.incident_type}
                  </strong>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#fff", background: s.pin, borderRadius: 4, padding: "2px 6px", marginLeft: 8, whiteSpace: "nowrap" }}>
                    {pin.severity.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: colors.textDimmer, marginBottom: 8 }}>
                  {pin.building_name} · {formatTime(pin.published)}
                </div>

                {pin.headline && (
                  <div style={{ fontSize: 13, fontWeight: 700, color: s.pin, marginBottom: 6, lineHeight: 1.3 }}>
                    {pin.headline}
                  </div>
                )}

                <div style={{
                  fontSize: 12,
                  color: colors.bgBase,
                  background: pin.safety_brief ? `${s.pin}18` : "#f8fafc",
                  border: pin.safety_brief ? `1px solid ${s.pin}44` : "none",
                  borderRadius: 4,
                  padding: "6px 8px",
                  marginBottom: 6,
                  lineHeight: 1.5,
                }}>
                  {pin.safety_brief ?? pin.recommended_action}
                </div>

                <details style={{ fontSize: 11, color: colors.textFaint }}>
                  <summary style={{ cursor: "pointer" }}>Raw alert</summary>
                  <p style={{ marginTop: 4 }}>{pin.raw_text}</p>
                </details>
              </div>
            </Popup>
          </Marker>
        );
      })}

      {/* Bus stop pins */}
      {busStops.map((stop) => (
        <Marker
          key={stop.id}
          position={[stop.lat, stop.lon]}
          icon={busIcon()}
        >
          <Tooltip direction="top" offset={[0, -16]} opacity={1}>
            <div style={{ fontSize: 12, lineHeight: 1.5 }}>
              <strong>{stop.name}</strong>
              {stop.arrivals.slice(0, 2).map((a, i) => (
                <div key={i} style={{ color: colors.textDimmer, marginTop: 2 }}>
                  <span style={{ fontWeight: 700, color: colors.busPin }}>Route {a.route}</span>
                  {" — "}
                  {a.minutes === 0 ? "arriving now" : `${a.minutes} min`}
                </div>
              ))}
              {stop.arrivals.length === 0 && (
                <div style={{ color: colors.textDimmer, marginTop: 2 }}>No arrivals soon</div>
              )}
            </div>
          </Tooltip>
          <Popup>
            <div style={{ padding: "10px 12px", minWidth: 240 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
                <span style={{ fontSize: 14 }}>🚌</span>
                <strong style={{ fontSize: 13, color: colors.bgBase }}>{stop.name}</strong>
              </div>

              {stop.arrivals.length === 0 ? (
                <p style={{ fontSize: 12, color: colors.textFaint, margin: 0 }}>No arrivals in the next hour.</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e2e8f0" }}>
                      <th style={{ textAlign: "left", padding: "2px 4px", color: colors.textFaint, fontWeight: 600 }}>Route</th>
                      <th style={{ textAlign: "left", padding: "2px 4px", color: colors.textFaint, fontWeight: 600 }}>Destination</th>
                      <th style={{ textAlign: "right", padding: "2px 4px", color: colors.textFaint, fontWeight: 600 }}>Arrives</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stop.arrivals.slice(0, 6).map((a, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "4px 4px", fontWeight: 700, color: colors.busPin }}>{a.route}</td>
                        <td style={{ padding: "4px 4px", color: colors.bgBase, maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.headsign}</td>
                        <td style={{ padding: "4px 4px", textAlign: "right", color: a.minutes <= 2 ? "#ef4444" : colors.bgBase, fontWeight: a.minutes <= 2 ? 700 : 400 }}>
                          {a.minutes === 0 ? "Now" : `${a.minutes} min`}
                          {!a.predicted && <span style={{ fontSize: 9, color: colors.textFaint, marginLeft: 3 }}>sched</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
