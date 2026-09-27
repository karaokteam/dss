// Flask API istemcisi ve tipleri (sözleşme: STRUCTURE.md §5)

export type Level = "critical" | "high" | "medium" | "low";

export interface LatLonObj { lat: number; lon: number }
export interface Zone { name: string; lat: number; lon: number }

export interface ImageSummary {
  id: string; capture_time: string; zone: string; center: LatLonObj; bounds: [[number, number], [number, number]]; dist_to_base_m: number;
  vehicle_count: number; max_risk: Level; baseline_max_risk: Level; assessed: boolean; fallback: boolean;
  anomaly_count: number; summary: string | null; urls: { raw: string; annotated: string };
}

export interface Overview {
  base: Zone; zones: Zone[]; time_range: { from: string; to: string };
  counts: { images: number; detections: number; tracks: number; reports: number; assessed: number };
  risk_summary: Record<Level, number>; images: ImageSummary[];
}

export interface Alert {
  vehicle_id: string; label: string | null; track_id: string | null; risk_level: Level; baseline_level: Level;
  score: number; rationale: string; source: "agent" | "baseline"; image_id: string; capture_time: string;
  zone: string | null; lat: number | null; lon: number | null; dist_to_base_m: number | null;
  eta_min: number | null; consistent_approach: boolean; circling: boolean; headline: string;
}

export interface TrackPointLive {
  track_id: string; lat: number; lon: number; label: string | null; image_id: string | null;
  ends_at: string; consistent_approach: boolean; risk_level: Level | null;
}

export interface Detection {
  id: string; label: string | null; confidence: number | null; bbox_xywh: number[] | null; lat: number; lon: number;
  track_id: string | null; flags: string[]; baseline_risk: Level; baseline_score: number; is_missed_track: boolean;
}

export interface ImageDetail extends ImageSummary {
  width_px: number; height_px: number;
  corners: { top_left: number[]; top_right: number[]; bottom_left: number[]; bottom_right: number[] };
  footprint_m: number[]; detections: Detection[];
}

// Dossier (kanıt dosyası) — yalnızca UI'ın kullandığı alanlar
export interface Factor { name: string; weight: number; detail: string }
export interface Subject { kind: string; detection_id: string | null; track_id: string | null; label: string | null; dist_m: number }
export interface ClaimCheck {
  report_id: string; time: string; source: string; claim_type: string; status: string; reason: string; subjects?: Subject[];
}
export interface Kinematics {
  state: string; motion: string; dist_to_base_m: number; dist_to_base_start_m: number;
  radial_change_window_m: number | null; speed_mps: number; eta_min: number | null; stationary_min: number;
  moves: number; approach_moves: number; recede_moves: number; consistent_approach: boolean;
  circling: boolean; circling_radius_m: number | null; circling_window: string | null; circling_sweep_deg: number | null;
  min_dist_to_base_m: number;
  tortuosity: number | null; segments: { kind: string; start: string; end: string; distance_m: number; radial_change_m: number }[];
}
export interface VehicleEvidence {
  vehicle_id: string; label: string | null; confidence: number | null; track_id: string | null;
  dist_to_base_m: number; zone: string; kinematics: Kinematics | null; claims: ClaimCheck[]; flags: string[];
  baseline_risk: { score: number; level: Level; factors: Factor[] };
  candidates: { label: string; confidence: number }[];
}
export interface ReportSummary { report_id: string; time: string; source: string; text: string; checks: ClaimCheck[] }
export interface Dossier {
  image_id: string; capture_time: string; zone: string; dist_to_base_m: number; vehicles: VehicleEvidence[];
  reports: ReportSummary[]; context_reports: ReportSummary[];
  anomalies: { type: string; detail: string; evidence: string[] }[];
  global_context: { time: string; consistent_approachers: number; by_zone: Record<string, { count: number; heavy: number; closest_m: number; tracks: string[] }> };
}

export interface AssessedVehicle {
  vehicle_id: string; label: string | null; track_id: string | null; risk_level: Level; baseline_level: Level;
  baseline_score: number; override_reason: string | null; rationale: string; evidence: string[]; source: string;
}
export interface Assessment {
  image_id: string; overall_risk: Level; summary: string; vehicles: AssessedVehicle[];
  attention_items: { title: string; risk_level: Level; rationale: string; evidence: string[] }[];
  report_notes: { report_id: string; verdict: string; note: string }[];
  trace: { fallback: boolean; fallback_reason?: string; tool_calls: { tool: string; args: string; summary: string }[];
           iterations: number; duration_s?: number; model: string; prompt_version: string };
  current: boolean;
}

export interface Report {
  id: string; time: string; source: string; text: string; category: string; coord: LatLonObj | null;
  claim: { claim_types: string[]; vehicle_type: string | null; count: number | null; motion: string | null; friendly: boolean };
  links: { images: string[]; tracks: string[]; zone: string | null };
  status: string; checks: { claim_type: string; status: string; reason: string }[];
}

export interface TrackFull {
  track_id: string; image_id: string; detection_id: string | null; label: string | null; risk_level: Level | null;
  points: { time: string; lat: number; lon: number; dist_to_base_m: number }[];
  kinematics: Kinematics | null;
}

export interface GlobalTrack {
  track_id: string; image_id: string; label: string | null; risk_level: Level | null; consistent_approach: boolean;
  circling: boolean; circling_window: string | null;
  points: { time: string; lat: number; lon: number }[];
}

export interface ZonePoint { track_id: string; lat: number; lon: number; zone: string; label: string | null; image_id: string | null; risk_level: Level | null }

export interface Job { job_id: string; status: string; events_url: string; progress: { done: number; total: number } }

export interface AlertRuleHit {
  track_id: string; label: string | null; image_id: string; trigger_time: string; trigger_dist_m: number;
  min_dist_m: number; min_time: string; zone: string; inside_min: number; photo_time: string; photo_dist_m: number;
  lead_min: number; circling: string | null; consistent_approach: boolean;
}

export interface AlertRuleResult {
  text: string | null; notes: string[]; parsed_by: string; rule_text: string; total: number; any_vehicle_total: number; unlabeled: number;
  by_label: Record<string, number>; median_lead_min: number | null; hits: AlertRuleHit[];
  rule: { vehicle: string; max_dist_m: number | null; zone: string | null; time_from: string | null; time_to: string | null; circling_only: boolean };
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body?.error?.message || `${r.status} ${url}`);
  }
  return r.json();
}

async function post<T>(url: string, body: unknown = {}): Promise<T> {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.error?.message || `${r.status} ${url}`);
  return r.json();
}

export const api = {
  overview: () => get<Overview>("/api/overview"),
  alerts: (minRisk: Level = "high") => get<{ items: Alert[] }>(`/api/alerts?min_risk=${minRisk}`),
  tracksAt: (time: string) => get<{ time: string; points: TrackPointLive[] }>(`/api/tracks?time=${time}`),
  track: (id: string) => get<TrackFull>(`/api/tracks/${id}`),
  image: (id: string) => get<ImageDetail>(`/api/images/${id}`),
  dossier: (id: string) => get<Dossier>(`/api/images/${id}/dossier`),
  assessment: (id: string) => get<Assessment>(`/api/images/${id}/assessment`).catch(() => null),
  assess: (id: string, force = false) => post<Job>(`/api/images/${id}/assess`, { force }),
  reports: () => get<{ items: Report[] }>("/api/reports"),
  allTracks: () => get<{ items: GlobalTrack[] }>("/api/tracks?all=1"),
  reportsForImage: (id: string) => get<{ items: Report[] }>(`/api/reports?image_id=${id}`),
  tracksForImage: (id: string) => get<{ items: TrackFull[] }>(`/api/tracks?image_id=${id}`),
  zoneTracks: (time: string, zone: string) => get<{ points: ZonePoint[] }>(`/api/tracks?time=${time}&zone=${encodeURIComponent(zone)}`),
  budget: () => get<{ spend_usd: number; max_budget_usd: number }>("/api/llm/budget").catch(() => null),
  testAlertRule: (text: string) => post<AlertRuleResult>("/api/alert-rules/test", { text }),
};
