import type { Level } from "./api";

export const LEVELS: Level[] = ["critical", "high", "medium", "low"];

export const RISK_COLOR: Record<Level, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
};

export const RISK_TR: Record<Level, string> = {
  critical: "KRİTİK",
  high: "YÜKSEK",
  medium: "ORTA",
  low: "DÜŞÜK",
};

export const STATUS_TR: Record<string, string> = {
  verified: "Doğrulandı",
  partial: "Kısmen",
  contradicted: "Çelişkili",
  unverifiable: "Doğrulanamaz",
};

export const STATUS_COLOR: Record<string, string> = {
  verified: "#22c55e",
  partial: "#eab308",
  contradicted: "#ef4444",
  unverifiable: "#64748b",
};

export const VERDICT_TR: Record<string, string> = {
  reliable: "Güvenilir",
  partly_reliable: "Kısmen güvenilir",
  unreliable: "Güvenilmez",
  unverifiable: "Doğrulanamaz",
};

export const LABEL_TR: Record<string, string> = { car: "otomobil", van: "panelvan", truck: "kamyon", bus: "otobüs" };

export const MOTION_TR: Record<string, string> = {
  approaching: "yaklaşıyor", receding: "uzaklaşıyor", lateral: "yanal", stationary: "duruyor",
};

export const CLAIM_TR: Record<string, string> = {
  count: "sayım", stationary: "durağanlık", motion: "hareket", identity: "kimlik/dost",
  density: "yoğunluk", zone_status: "bölge durumu", noise: "genel", unknown: "bilinmeyen",
};

export const rank = (l: Level | null | undefined) => (l ? LEVELS.indexOf(l) : 9);

export const km = (m: number | null | undefined) => (m == null ? "-" : m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`);

export const toMin = (t: string) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
export const toHHMM = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

// Track noktaları arasında doğrusal enterpolasyon (dakika cinsinden t)
export function posAt(points: { time: string; lat: number; lon: number }[], t: number): [number, number] | null {
  if (!points.length) return null;
  const ts = points.map((p) => toMin(p.time));
  if (t < ts[0] || t > ts[ts.length - 1]) return null;
  for (let i = 0; i < ts.length - 1; i++) {
    if (t >= ts[i] && t <= ts[i + 1]) {
      const w = ts[i + 1] === ts[i] ? 0 : (t - ts[i]) / (ts[i + 1] - ts[i]);
      return [points[i].lat + w * (points[i + 1].lat - points[i].lat), points[i].lon + w * (points[i + 1].lon - points[i].lon)];
    }
  }
  return [points[points.length - 1].lat, points[points.length - 1].lon];
}

// Üs etrafında bölge sektörü (bölge merkezinin yönü ±22.5°, 1–6 km halka)
// Bölge dilimleri: bölge merkezleri üssün etrafında halka gibi dizili; "en yakın merkez" ataması bu yüzden
// üsse göre açı dilimlerine denk gelir. Dilim sınırı = komşu iki merkezin açıortayı (açı: kuzeyden saat yönünde).
type LatLon = { lat: number; lon: number };
const K_LAT = 111320;
const kLon = (base: LatLon) => 111320 * Math.cos((base.lat * Math.PI) / 180);
const polar = (base: LatLon, r: number, a: number): [number, number] =>
  [base.lat + (r * Math.cos(a)) / K_LAT, base.lon + (r * Math.sin(a)) / kLon(base)];

export function sectorAngles(base: LatLon, zones: (LatLon & { name: string })[]): Record<string, [number, number]> {
  const brg = zones.map((z) => ({ name: z.name, a: Math.atan2((z.lon - base.lon) * kLon(base), (z.lat - base.lat) * K_LAT) }))
    .sort((x, y) => x.a - y.a);
  const n = brg.length, tau = 2 * Math.PI, out: Record<string, [number, number]> = {};
  brg.forEach((z, i) => {
    const before = (z.a - brg[(i - 1 + n) % n].a + tau) % tau || tau;
    const after = (brg[(i + 1) % n].a - z.a + tau) % tau || tau;
    out[z.name] = [z.a - before / 2, z.a + after / 2];
  });
  return out;
}

export function sectorPolygon(base: LatLon, [a0, a1]: [number, number], inner: number, outer: number): [number, number][] {
  const steps = Math.max(8, Math.ceil(((a1 - a0) * 180) / Math.PI / 3));
  const out: [number, number][] = [];
  for (let i = 0; i <= steps; i++) out.push(polar(base, outer, a0 + ((a1 - a0) * i) / steps));
  for (let i = steps; i >= 0; i--) out.push(polar(base, inner, a0 + ((a1 - a0) * i) / steps));
  return out;
}

export const sectorSpoke = (base: LatLon, a: number, inner: number, outer: number): [number, number][] =>
  [polar(base, inner, a), polar(base, outer, a)];

export function zoneWedge(base: { lat: number; lon: number }, zone: { lat: number; lon: number }): [number, number][] {
  const kLat = 111320, kLon = 111320 * Math.cos((base.lat * Math.PI) / 180);
  const bearing = Math.atan2((zone.lon - base.lon) * kLon, (zone.lat - base.lat) * kLat);
  const pt = (r: number, a: number): [number, number] => [base.lat + (r * Math.cos(a)) / kLat, base.lon + (r * Math.sin(a)) / kLon];
  const out: [number, number][] = [];
  const half = (22.5 * Math.PI) / 180;
  for (let i = 0; i <= 12; i++) out.push(pt(6000, bearing - half + (2 * half * i) / 12));
  for (let i = 12; i >= 0; i--) out.push(pt(1000, bearing - half + (2 * half * i) / 12));
  return out;
}
