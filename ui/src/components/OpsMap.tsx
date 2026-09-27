import { Fragment, createElement, useEffect, useMemo } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Bus, Car, CircleHelp, Truck, Van, type LucideIcon } from "lucide-react";
import { Circle, CircleMarker, MapContainer, Marker, Polygon, Polyline, Rectangle, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import type { GlobalTrack, ImageSummary, Overview, Report, TrackFull, ZonePoint } from "../api";
import { LABEL_TR, RISK_COLOR, RISK_TR, STATUS_COLOR, STATUS_TR, posAt, sectorAngles, sectorPolygon, sectorSpoke, toMin, zoneWedge } from "../risk";

const SECTOR_INNER_M = 300;     // üs işaretinin etrafı boş kalsın
const SECTOR_OUTER_M = 8000;    // track'lerin en uzak başlangıcı ~7,9 km

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

// Araç ikonu: tipine göre SVG (lucide), risk renginde halka
const ICONS: Record<string, LucideIcon> = { car: Car, van: Van, truck: Truck, bus: Bus };
const svgCache = new Map<string, string>();
function iconSvg(label: string | null, px: number): string {
  const key = `${label}|${px}`;
  if (!svgCache.has(key)) {
    const Icon = (label && ICONS[label]) || CircleHelp;
    svgCache.set(key, renderToStaticMarkup(createElement(Icon, { size: px, color: "#e2e8f0", strokeWidth: 2.2 })));
  }
  return svgCache.get(key)!;
}
const iconCache = new Map<string, L.DivIcon>();
export function vehicleIcon(label: string | null, color: string, size = 22, selected = false): L.DivIcon {
  const key = `${label}|${color}|${size}|${selected}`;
  let icon = iconCache.get(key);
  if (!icon) {
    icon = L.divIcon({
      className: "",
      html: `<div class="veh${selected ? " sel" : ""}" style="width:${size}px;height:${size}px;border-color:${color};box-shadow:0 0 ${selected ? 12 : 4}px ${color}">${iconSvg(label, Math.round(size * 0.6))}</div>`,
      iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    });
    iconCache.set(key, icon);
  }
  return icon;
}

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
  global?: { tracks: GlobalTrack[]; time: number } | null;   // "Tüm gün" modu
  onSelectGlobal?: (t: GlobalTrack) => void;
  activeZone?: { name: string; color: string } | null;       // vurgulanan bölge dilimi
  onSelectZone?: (name: string) => void;                     // dilime / bölge adına tıklama
}

export default function OpsMap(p: Props) {
  const b = p.overview.base;
  const focusReport = p.focus.report;
  const zone = focusReport?.links.zone ? p.overview.zones.find((z) => z.name === focusReport.links.zone) : null;
  const sectors = useMemo(() => sectorAngles(b, p.overview.zones), [b, p.overview.zones]);
  const active = p.activeZone && sectors[p.activeZone.name] ? p.activeZone : null;

  return (
    <MapContainer center={[b.lat, b.lon]} zoom={13} zoomControl={false}>
      <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        attribution="Esri" maxNativeZoom={16} maxZoom={18} className="base-tiles" />
      <Fit bounds={p.fitTo} />

      {/* Bölge dilimleri: tıklanabilir alanlar (görünmez) + soluk sınır çizgileri + seçili dilim */}
      {Object.entries(sectors).map(([name, ang]) => (
        <Polygon key={"sec" + name} positions={sectorPolygon(b, ang, SECTOR_INNER_M, SECTOR_OUTER_M)}
          eventHandlers={{ click: () => p.onSelectZone?.(name) }}
          pathOptions={{ stroke: false, fillColor: "#000", fillOpacity: 0.01, className: "zone-sector" }} />
      ))}
      {Object.entries(sectors).map(([name, [a0]]) => (
        <Polyline key={"spoke" + name} positions={sectorSpoke(b, a0, SECTOR_INNER_M, SECTOR_OUTER_M)} interactive={false}
          pathOptions={{ color: "#64748b", weight: 1, opacity: 0.35, dashArray: "4 8" }} />
      ))}
      {active && (
        <Polygon key={"active" + active.name + active.color} positions={sectorPolygon(b, sectors[active.name], SECTOR_INNER_M, SECTOR_OUTER_M)}
          interactive={false}
          pathOptions={{ color: active.color, weight: 2, opacity: 0.9, fillColor: active.color, fillOpacity: 0.12, className: "zone-sector-active" }} />
      )}

      {/* Üs + halkalar */}
      {[2000, 3500, 5000].map((r) => (
        <Circle key={r} center={[b.lat, b.lon]} radius={r} interactive={false}
          pathOptions={{ color: "#64748b", weight: 1, opacity: 0.35, fill: false, dashArray: "4 8" }} />
      ))}
      <Marker position={[b.lat, b.lon]} icon={baseIcon}><Tooltip>{b.name}</Tooltip></Marker>
      {p.overview.zones.map((z) => {
        const on = active?.name === z.name;
        return (
          <Marker key={z.name + (on ? active!.color : "")} position={[z.lat, z.lon]} eventHandlers={{ click: () => p.onSelectZone?.(z.name) }}
            icon={L.divIcon({
              className: "", iconSize: [140, 14], iconAnchor: [70, 7],
              html: `<div class="zone-label${on ? " active" : ""}"${on ? ` style="color:${active!.color}"` : ""}>${z.name}</div>`,
            })} />
        );
      })}

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
      {!p.global && p.overview.images.filter((i) => i.id !== p.selected?.id).map((img) => (
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
              <Marker position={now} icon={vehicleIcon(t.label, color, sel ? 32 : 24, sel)} zIndexOffset={sel ? 1000 : 0}
                eventHandlers={{ click: () => p.onSelectTrack(t.track_id) }}>
                <Tooltip permanent={sel} direction="top" offset={[0, -14]}>
                  <b>{t.track_id}</b>{sel ? "" : ` · ${t.label ? LABEL_TR[t.label] ?? t.label : "?"} · ${t.risk_level ? RISK_TR[t.risk_level] : "-"}`}
                </Tooltip>
              </Marker>
            )}
          </Fragment>
        );
      })}

      {/* Tüm gün modu: o anda kaydı olan bütün araçlar + son 30 dk kuyruk; o anda çekilen görüntüler yanıp söner */}
      {p.global && p.overview.images.filter((i) => Math.abs(toMin(i.capture_time) - p.global!.time) <= 5).map((img) => (
        <Rectangle key={"cam" + img.id} bounds={img.bounds} className="cam-pulse" eventHandlers={{ click: () => p.onSelectImage(img.id) }}
          pathOptions={{ color: "#f8fafc", weight: 3, fillColor: RISK_COLOR[img.max_risk], fillOpacity: 0.5 }}>
          <Tooltip permanent direction="bottom">{img.capture_time}</Tooltip>
        </Rectangle>
      ))}
      {p.global && p.global.tracks.map((t) => {
        const now = posAt(t.points, p.global!.time);
        if (!now) return null;
        const color = t.risk_level ? RISK_COLOR[t.risk_level] : "#94a3b8";
        const tail = t.points.filter((q) => { const m = toMin(q.time); return m <= p.global!.time && m >= p.global!.time - 30; })
          .map((q) => [q.lat, q.lon] as [number, number]);
        tail.push(now);
        const big = t.consistent_approach || t.circling || t.risk_level === "critical" || t.risk_level === "high";
        return (
          <Fragment key={"g" + t.track_id}>
            {tail.length > 1 && <Polyline positions={tail} interactive={false} pathOptions={{ color, weight: big ? 2.5 : 1.2, opacity: big ? 0.9 : 0.5 }} />}
            <Marker position={now} icon={vehicleIcon(t.label, color, big ? 24 : 16)} zIndexOffset={big ? 500 : 0}
              eventHandlers={{ click: () => p.onSelectGlobal?.(t) }}>
              <Tooltip direction="top" offset={[0, -10]}>
                <b>{t.track_id}</b> · {t.label ? LABEL_TR[t.label] ?? t.label : "?"} · {t.risk_level ? RISK_TR[t.risk_level] : "-"}
                {t.consistent_approach && " · tutarlı yaklaşma"}{t.circling && ` · üssün etrafında döndü (${t.circling_window})`}<br />kayıt sonu {t.points[t.points.length - 1].time}
              </Tooltip>
            </Marker>
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
            <Marker position={pts[pts.length - 1]} icon={vehicleIcon(t.label, color, 28, true)} eventHandlers={{ click: () => p.onSelectImage(t.image_id) }}>
              <Tooltip permanent direction="top" offset={[0, -14]}><b>{t.track_id}</b></Tooltip>
            </Marker>
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
