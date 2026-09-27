import React, { useMemo, useState } from "react";
import { ClipboardList, Eye, Microscope, Play, Truck } from "lucide-react";
import type { Assessment, Dossier, ImageDetail, Level, Report } from "../api";
import AgentTrace from "./AgentTrace";
import {
  CLAIM_TR, LABEL_TR, MOTION_TR, RISK_COLOR, RISK_TR, STATUS_COLOR, STATUS_TR, VERDICT_TR, km, rank,
} from "../risk";

export function RiskBadge({ level, prefix = "Risk" }: { level: Level; prefix?: string }) {
  return <span className="badge" style={{ background: RISK_COLOR[level] }}>{prefix ? `${prefix}: ` : ""}{RISK_TR[level]}</span>;
}
export function TruthBadge({ s }: { s: string }) {
  return <span className="badge" style={{ background: STATUS_COLOR[s] ?? "#64748b" }}>{STATUS_TR[s] ?? s}</span>;
}

interface Props {
  img: ImageDetail; dossier: Dossier; assessment: Assessment | null; reports: Report[];
  selectedVehicle: string | null; onSelectVehicle: (vehicleId: string) => void;
  focusReportId: string | null; onFocusReport: (r: Report) => void;
  onAnalyze: (force: boolean) => void; jobUrl: string | null; onJobDone: () => void;
}

type Tab = "assess" | "vehicle" | "reports";

export default function EventDetail(p: Props) {
  const [tab, setTab] = useState<Tab>("assess");
  const [variant, setVariant] = useState<"raw" | "annotated">("raw");
  const { img, dossier, assessment } = p;

  const levelOf = useMemo(() => {
    const m: Record<string, Level> = {};
    dossier.vehicles.forEach((v) => (m[v.vehicle_id] = v.baseline_risk.level));
    assessment?.vehicles.forEach((v) => (m[v.vehicle_id] = v.risk_level));
    return m;
  }, [dossier, assessment]);

  const overall = assessment?.overall_risk ?? img.baseline_max_risk;
  const v = dossier.vehicles.find((x) => x.vehicle_id === p.selectedVehicle);
  const av = assessment?.vehicles.find((x) => x.vehicle_id === p.selectedVehicle);
  const coordReports = p.reports.filter((r) => r.category === "coordinate");
  const zoneReports = p.reports.filter((r) => r.category === "zone");
  const pick = (id: string) => { p.onSelectVehicle(id); setTab("vehicle"); };

  return (
    <div className="flex flex-col h-full">
      {/* başlık */}
      <div className="px-4 pt-3 pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold">{img.capture_time}</span>
          <span className="font-bold">{img.zone}</span>
          <RiskBadge level={overall} />
          <span className="flex-1" />
          <span className="text-xs text-slate-500">{km(img.dist_to_base_m)}</span>
          <button className="!p-1.5" title={assessment ? "Yeniden analiz" : "Analiz et"} onClick={() => p.onAnalyze(!!assessment)} disabled={!!p.jobUrl}>
            <Play size={13} />
          </button>
        </div>
      </div>

      <div className="overflow-y-auto flex-1">
        {/* fotoğraf + risk kutuları */}
        <div className="imgwrap">
          <img src={img.urls[variant]} alt={img.id} />
          {variant === "raw" && (
            <svg className="overlay" viewBox={`0 0 ${img.width_px} ${img.height_px}`} preserveAspectRatio="none">
              {img.detections.filter((d) => d.bbox_xywh).map((d) => {
                const [x, y, w, h] = d.bbox_xywh!;
                const lvl = levelOf[d.id] ?? d.baseline_risk;
                const sel = p.selectedVehicle === d.id;
                return (
                  <g key={d.id} onClick={() => pick(d.id)}>
                    <rect x={x - 4} y={y - 4} width={w + 8} height={h + 8} fill={sel ? "rgba(56,189,248,.15)" : "transparent"}
                      stroke={sel ? "#f8fafc" : RISK_COLOR[lvl]} strokeWidth={sel ? 5 : rank(lvl) <= 1 ? 3.5 : 2}
                      strokeDasharray={d.is_missed_track ? "8 5" : undefined} opacity={d.flags.includes("low_confidence") ? 0.45 : 1} />
                    {(rank(lvl) <= 1 || sel) && d.track_id && (
                      <text x={x} y={y - 9} fill={RISK_COLOR[lvl]} fontSize={Math.max(15, img.width_px / 65)} fontWeight={800}
                        style={{ paintOrder: "stroke", stroke: "#000", strokeWidth: 4 }}>{d.track_id}</text>
                    )}
                  </g>
                );
              })}
            </svg>
          )}
          <button className="absolute right-2 bottom-2 text-xs !py-0.5 !bg-black/60" onClick={() => setVariant(variant === "raw" ? "annotated" : "raw")}>
            <Eye size={12} className="inline mr-1" />{variant === "raw" ? "YOLO çizimi" : "risk kutuları"}
          </button>
        </div>

        {/* sekmeler */}
        <div className="flex border-b border-slate-800 sticky top-0 bg-[var(--panel)] z-10">
          {([["assess", "Değerlendirme", Microscope], ["vehicle", "Araç", Truck], ["reports", `Raporlar (${p.reports.length})`, ClipboardList]] as const).map(([k, label, Icon]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`flex-1 !rounded-none !border-0 !border-b-2 text-sm ${tab === k ? "!border-sky-400 text-white" : "!border-transparent text-slate-400"}`}>
              <Icon size={14} className="inline mr-1" />{label}
            </button>
          ))}
        </div>

        <div className="p-4">
          {/* ---------------- Değerlendirme */}
          {tab === "assess" && (
            <>
              {p.jobUrl && <div className="mb-3"><AgentTrace eventsUrl={p.jobUrl} onFinished={p.onJobDone} /></div>}
              {assessment ? <div className="text-sm leading-relaxed mb-3">{assessment.summary}</div>
                : <div className="text-xs text-slate-500 mb-3">Agent çalışmadı · kural tabanlı risk</div>}

              {dossier.vehicles.filter((x) => rank(levelOf[x.vehicle_id]) <= 2).map((x) => (
                <div key={x.vehicle_id} onClick={() => pick(x.vehicle_id)}
                  className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-slate-800 text-sm">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: RISK_COLOR[levelOf[x.vehicle_id]] }} />
                  <b className="w-14">{x.track_id ?? "?"}</b>
                  <span className="text-slate-400 flex-1">{x.label ? LABEL_TR[x.label] ?? x.label : "tespitsiz"}</span>
                  {x.kinematics?.circling && <span title={`üssün etrafında döndü ${x.kinematics.circling_window}`} className="text-red-400 text-xs">↻</span>}
                  {x.kinematics?.consistent_approach && <span title="tutarlı yaklaşma" className="text-red-400 text-xs">⇣⇣</span>}
                  <span className="text-xs text-slate-500 font-mono">{km(x.dist_to_base_m)}</span>
                </div>
              ))}

              {assessment && assessment.attention_items.length > 0 && (
                <Fold title={`Dikkat noktaları (${assessment.attention_items.length})`} open>
                  {assessment.attention_items.map((a, i) => (
                    <details key={i} className="mb-1.5">
                      <summary className="text-sm cursor-pointer"><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: RISK_COLOR[a.risk_level] }} />{a.title}</summary>
                      <div className="text-xs text-slate-400 mt-1 ml-4">{a.rationale}</div>
                    </details>
                  ))}
                </Fold>
              )}
              {dossier.anomalies.length > 0 && (
                <Fold title={`Anomaliler (${dossier.anomalies.length})`}>
                  {dossier.anomalies.map((a, i) => <div key={i} className="text-xs text-slate-400 mb-1.5">{a.detail}</div>)}
                </Fold>
              )}
              {assessment && assessment.trace.tool_calls.length > 0 && (
                <Fold title={`Agent soruşturmaları (${assessment.trace.tool_calls.length})`}>
                  {assessment.trace.tool_calls.map((t, i) => (
                    <div key={i} className="text-[11px] mb-1.5 text-slate-400"><span className="pill !text-sky-300">{t.tool}</span>{t.summary}</div>
                  ))}
                </Fold>
              )}
            </>
          )}

          {/* ---------------- Araç */}
          {tab === "vehicle" && (!v ? <div className="text-sm text-slate-400">Fotoğrafta ya da haritada bir araca tıkla.</div> : (
            <>
              <div className="flex items-center gap-2 mb-2">
                <RiskBadge level={levelOf[v.vehicle_id]} />
                <b>{v.track_id ?? v.vehicle_id}</b>
                <span className="text-sm text-slate-300">{v.label ? LABEL_TR[v.label] ?? v.label : "tespit yok"}</span>
                {v.confidence != null && <span className="text-xs text-slate-500">güven {v.confidence.toFixed(2)}</span>}
              </div>

              {v.kinematics ? (
                <>
                  <div className="grid grid-cols-2 gap-2 mb-3 text-sm">
                    <Stat k="Üsse (2 sa)" v={`${km(v.kinematics.dist_to_base_start_m)} → ${km(v.kinematics.dist_to_base_m)}`} />
                    <Stat k="Son 60 dk" v={`${MOTION_TR[v.kinematics.motion] ?? v.kinematics.motion}`} />
                    <Stat k="Hareket ↓/↑" v={`${v.kinematics.approach_moves} / ${v.kinematics.recede_moves}`} />
                    <Stat k="Tutarlı yaklaşma" v={v.kinematics.consistent_approach ? "EVET" : "hayır"} red={v.kinematics.consistent_approach} />
                    {v.kinematics.circling && <Stat k="Üssün etrafında döndü" v={`${v.kinematics.circling_window} · ~${Math.round(v.kinematics.circling_radius_m ?? 0)} m`} red />}
                    {!v.kinematics.circling && v.kinematics.min_dist_to_base_m < v.kinematics.dist_to_base_m - 200 && <Stat k="Üsse en yakın" v={km(v.kinematics.min_dist_to_base_m)} red={v.kinematics.min_dist_to_base_m < 1000} />}
                    <Stat k="Duruyor" v={`${v.kinematics.stationary_min} dk`} />
                    <Stat k="ETA" v={v.kinematics.eta_min != null ? `${Math.round(v.kinematics.eta_min)} dk` : "-"} />
                  </div>
                  <div className="flex gap-1 flex-wrap mb-3">
                    {v.kinematics.segments.map((s, i) => (
                      <span key={i} className="pill" style={{ color: s.kind === "move" ? (s.radial_change_m < 0 ? "#f97316" : "#22c55e") : undefined }}>
                        {s.start} {s.kind === "move" ? `${s.radial_change_m < 0 ? "↓" : "↑"}${km(Math.abs(s.radial_change_m))}` : "■"}
                      </span>
                    ))}
                  </div>
                </>
              ) : <div className="text-sm text-slate-400 mb-3">Hareket kaydı yok (park halinde / track'siz).</div>}

              {av && (
                <div className="card !border-sky-800">
                  {av.risk_level !== av.baseline_level && <div className="text-[11px] text-sky-300 mb-1">kural {RISK_TR[av.baseline_level]} → agent {RISK_TR[av.risk_level]}</div>}
                  {av.override_reason && <div className="text-xs mb-1 text-slate-300">{av.override_reason}</div>}
                  <div className="text-xs">{av.rationale}</div>
                </div>
              )}

              <Fold title={`Risk faktörleri · skor ${v.baseline_risk.score}`}>
                {v.baseline_risk.factors.map((f) => (
                  <div key={f.name} className="text-xs mb-0.5"><b style={{ color: f.weight > 0 ? "#f97316" : "#22c55e" }}>{f.weight > 0 ? "+" : ""}{f.weight}</b> {f.detail}</div>
                ))}
              </Fold>
              {v.claims.length > 0 && (
                <Fold title={`Raporlar (${new Set(v.claims.map((c) => c.report_id)).size})`} open>
                  {v.claims.map((c, i) => {
                    const r = p.reports.find((x) => x.id === c.report_id);
                    return (
                      <div key={i} title={c.reason} className="flex items-center gap-2 text-xs py-1 cursor-pointer hover:bg-slate-800 rounded px-1"
                        onClick={() => { if (r) { p.onFocusReport(r); setTab("reports"); } }}>
                        <TruthBadge s={c.status} /><b>{c.report_id}</b><span className="text-slate-400">{CLAIM_TR[c.claim_type] ?? c.claim_type}</span>
                      </div>
                    );
                  })}
                </Fold>
              )}
            </>
          ))}

          {/* ---------------- Raporlar */}
          {tab === "reports" && (
            <>
              {coordReports.length === 0 && zoneReports.length === 0 && <div className="text-xs text-slate-500">rapor yok</div>}
              {coordReports.map((r) => <ReportCard key={r.id} r={r} active={p.focusReportId === r.id} onClick={() => p.onFocusReport(r)}
                note={assessment?.report_notes.find((n) => n.report_id === r.id)} />)}
              {zoneReports.length > 0 && <div className="section-title">Bölge</div>}
              {zoneReports.map((r) => <ReportCard key={r.id} r={r} active={p.focusReportId === r.id} onClick={() => p.onFocusReport(r)}
                note={assessment?.report_notes.find((n) => n.report_id === r.id)} />)}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ k, v, red }: { k: string; v: string; red?: boolean }) {
  return <div className="bg-slate-900/60 rounded px-2 py-1"><div className="text-[10px] text-slate-500 uppercase">{k}</div><div className={red ? "text-red-400 font-bold" : ""}>{v}</div></div>;
}

function ReportCard({ r, active, onClick, note }: { r: Report; active: boolean; onClick: () => void; note?: { verdict: string; note: string } }) {
  return (
    <div className={`card clickable ${active ? "selected" : ""}`} onClick={onClick}>
      <div className="flex items-center gap-2 text-xs mb-1">
        <TruthBadge s={r.status} /><b>{r.id}</b><span className="text-slate-400">{r.time}</span>
      </div>
      <div className={`text-xs ${active ? "" : "truncate"}`}>{r.text}</div>
      {active && r.checks.map((c, i) => <div key={i} className="text-[11px] text-slate-400"><b>{CLAIM_TR[c.claim_type] ?? c.claim_type}:</b> {c.reason}</div>)}
      {active && note && <div className="text-[11px] text-sky-300 mt-1">Agent: {VERDICT_TR[note.verdict] ?? note.verdict} — {note.note}</div>}
    </div>
  );
}

function Fold({ title, open, children }: { title: string; open?: boolean; children: React.ReactNode }) {
  return (
    <details open={open} className="mt-3 border-t border-slate-800 pt-2">
      <summary className="section-title !m-0 cursor-pointer select-none">{title}</summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}
