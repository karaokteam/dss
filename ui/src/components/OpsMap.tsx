import { Fragment, useEffect } from "react";
import { Circle, CircleMarker, MapContainer, Marker, Polygon, Polyline, Rectangle, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import type { ImageSummary, Overview, Report, TrackFull, ZonePoint } from "../api";
import { LABEL_TR, RISK_COLOR, RISK_TR, STATUS_COLOR, STATUS_TR, posAt, toMin, zoneWedge } from "../risk";

const baseIcon = L.divIcon({
  className: "",
  html: `<div style="width:26px;height:26px;border-radius:50%;background:#0ea5e9;border:3px solid #e0f2fe;box-shadow:0 0 12px #38bdf8;display:flex;align-items:center;justify-content:center;font-size:13px">★</div>`,
  iconSize: [26, 26], iconAnchor: [13, 13],
});
const reportIcon = (color: string, active: boolean) => L.divIcon({
  className: "",
  html: `<div style="width:${active ? 16 : 12}px;height:${active ? 16 : 12}px;transform:rotate(45deg);background:${color};border:2px solid #0b1017;box-shadow:0 0 ${active ? 10 : 0}px ${color}"></div>`,
  iconSize: [16, 16], iconAnchor: [8, 8],
});

function Fit({ bounds }: { bounds: [number, number][] | null }) {
  const map = useMap();
  useEffect(() => {
    // Animasyonsuz: uçuş animasyonu sırasında vektör katmanları (sektör, halkalar, izler) kayabiliyordu
    if (bounds && bounds.length) map.fitBounds(L.latLngBounds(bounds).pad(0.25), { animate: false, maxZoom: 16 });
  }, [JSON.stringify(bounds)]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export interface MapFocus {
  report: Report | null;          // odaklanan rapor (çizgiler + bölge sektörü)
  zonePoints: ZonePoint[];        // bölge raporu: rapor saatinde bölgedeki araçlar
  subjects: string[];             // raporun anlattığı track'ler
}

interface Props {
  overview: Overview;
  selected: ImageSummary | null;
  tracks: TrackFull[];
  reports: Report[];
  time: number | null;
  selectedTrack: string | null;
  focus: MapFocus;
  fitTo: [number, number][] | null;
  onSelectImage: (id: string) => void;
  onSelectTrack: (id: string) => void;
  onSelectReport: (r: Report) => void;
  highlight: TrackFull[];
}

export default function OpsMap(p: Props) {
  const b = p.overview.base;
  const focusReport = p.focus.report;
  const zone = focusReport?.links.zone ? p.overview.zones.find((z) => z.name === focusReport.links.zone) : null;

  return (
    <MapContainer center={[b.lat, b.lon]} zoom={13} zoomControl={false}>
      <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        attribution="Esri" maxNativeZoom={16} maxZoom={18} className="base-tiles" />
      <Fit bounds={p.fitTo} />

      {/* Üs + halkalar */}
      {[2000, 3500, 5000].map((r) => (
        <Circle key={r} center={[b.lat, b.lon]} radius={r} interactive={false}
          pathOptions={{ color: "#7dd3fc", weight: 1.8, opacity: 0.75, fill: false, dashArray: "6 6" }} />
      ))}
      <Marker position={[b.lat, b.lon]} icon={baseIcon}><Tooltip>{b.name}</Tooltip></Marker>
      {p.overview.zones.map((z) => (
        <Marker key={z.name} position={[z.lat, z.lon]} interactive={false}
          icon={L.divIcon({ className: "", html: `<div class="zone-label">${z.name}</div>`, iconSize: [140, 14], iconAnchor: [70, 7] })} />
      ))}

      {/* Bölge raporu odağı: sektör + rapor anındaki araçlar */}
      {zone && focusReport?.category === "zone" && (
        <Polygon positions={zoneWedge(b, zone)} interactive={false}
          pathOptions={{ color: "#c4b5fd", weight: 2, fillColor: "#a78bfa", fillOpacity: 0.18 }} />
      )}
      {p.focus.zonePoints.map((z) => (
        <CircleMarker key={"z" + z.track_id} center={[z.lat, z.lon]} radius={z.label === "truck" || z.label === "bus" ? 6 : 4}
          pathOptions={{ color: "#a78bfa", fillColor: z.label === "truck" || z.label === "bus" ? "#f97316" : "#a78bfa", fillOpacity: 0.9, weight: 1.5 }}>
          <Tooltip>{z.track_id} · {z.label ? LABEL_TR[z.label] ?? z.label : "etiketsiz"} (rapor anında bölgede)</Tooltip>
        </CircleMarker>
      ))}

      {/* Diğer olaylar: küçük soluk noktalar */}
      {p.overview.images.filter((i) => i.id !== p.selected?.id).map((img) => (
        <CircleMarker key={img.id} center={[img.center.lat, img.center.lon]} radius={5}
          pathOptions={{ color: RISK_COLOR[img.max_risk], fillColor: RISK_COLOR[img.max_risk], fillOpacity: 0.35, opacity: 0.6, weight: 1 }}
          eventHandlers={{ click: () => p.onSelectImage(img.id) }}>
          <Tooltip>{img.capture_time} · {img.zone} · {RISK_TR[img.max_risk]}</Tooltip>
        </CircleMarker>
      ))}

      {/* Seçili olay: görüntü alanı */}
      {p.selected && (
        <Rectangle bounds={p.selected.bounds} interactive={false}
          pathOptions={{ color: RISK_COLOR[p.selected.max_risk], weight: 2, fillOpacity: 0.15 }} />
      )}

      {/* Seçili olayın araçları: soluk tam iz + zamana kadar kuyruk + konum */}
      {p.tracks.map((t) => {
        const color = t.risk_level ? RISK_COLOR[t.risk_level] : "#94a3b8";
        const sel = p.selectedTrack === t.track_id;
        const full = t.points.map((q) => [q.lat, q.lon] as [number, number]);
        const tail = p.time == null ? full : t.points.filter((q) => toMin(q.time) <= p.time!).map((q) => [q.lat, q.lon] as [number, number]);
        const now = p.time == null ? full[full.length - 1] : posAt(t.points, p.time);
        if (now && tail.length) tail.push(now);
        return (
          <Fragment key={t.track_id}>
            <Polyline positions={full} interactive={false} pathOptions={{ color, weight: 1, opacity: sel ? 0.45 : 0.18, dashArray: "2 4" }} />
            <Polyline positions={tail} interactive={false} pathOptions={{ color, weight: sel ? 4 : 2, opacity: sel ? 1 : 0.7 }} />
            {now && (
              <CircleMarker center={now} radius={sel ? 9 : 6} eventHandlers={{ click: () => p.onSelectTrack(t.track_id) }}
                pathOptions={{ color: sel ? "#f8fafc" : "#0b1017", fillColor: color, fillOpacity: 1, weight: sel ? 3 : 1.5 }}>
                <Tooltip permanent={sel} direction="top" offset={[0, -8]}>
                  <b>{t.track_id}</b>{sel ? "" : ` · ${t.label ? LABEL_TR[t.label] ?? t.label : "?"} · ${t.risk_level ? RISK_TR[t.risk_level] : "-"}`}
                </Tooltip>
              </CircleMarker>
            )}
          </Fragment>
        );
      })}

      {/* Asistanın vurguladığı araçlar (farklı olaylardan) */}
      {p.highlight.map((t) => {
        const color = t.risk_level ? RISK_COLOR[t.risk_level] : "#38bdf8";
        const pts = t.points.map((q) => [q.lat, q.lon] as [number, number]);
        return (
          <Fragment key={"h" + t.track_id}>
            <Polyline positions={pts} interactive={false} pathOptions={{ color: "#38bdf8", weight: 6, opacity: 0.25 }} />
            <Polyline positions={pts} interactive={false} pathOptions={{ color, weight: 2.5, opacity: 1 }} />
            <CircleMarker center={pts[pts.length - 1]} radius={7} eventHandlers={{ click: () => p.onSelectImage(t.image_id) }}
              pathOptions={{ color: "#f8fafc", fillColor: color, fillOpacity: 1, weight: 2 }}>
              <Tooltip permanent direction="top" offset={[0, -8]}>
                <b>{t.track_id}</b>
              </Tooltip>
            </CircleMarker>
          </Fragment>
        );
      })}

      {/* Raporlar: konum + (odaktaysa) anlattığı araca çizgi */}
      {p.reports.filter((r) => r.coord).map((r) => {
        const active = focusReport?.id === r.id;
        const color = STATUS_COLOR[r.status] ?? "#64748b";
        const lines = active ? p.tracks.filter((t) => p.focus.subjects.includes(t.track_id)).map((t) => posAt(t.points, toMin(r.time))).filter(Boolean) as [number, number][] : [];
        return (
          <Fragment key={r.id}>
            <Marker position={[r.coord!.lat, r.coord!.lon]} icon={reportIcon(color, active)} eventHandlers={{ click: () => p.onSelectReport(r) }}>
              <Tooltip direction="right"><b>{r.id}</b> {r.time} · {STATUS_TR[r.status]}</Tooltip>
            </Marker>
            {lines.map((pos, i) => (
              <Polyline key={i} positions={[[r.coord!.lat, r.coord!.lon], pos]} interactive={false}
                pathOptions={{ color, weight: 2, dashArray: "6 4" }} />
            ))}
          </Fragment>
        );
      })}
    </MapContainer>
  );
}
