import { useCallback, useEffect, useMemo, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { api, type Assessment, type Dossier, type ImageDetail, type Overview, type Report, type TrackFull } from "../api";
import EventDetail from "../components/EventDetail";
import EventList from "../components/EventList";
import OpsMap, { type MapFocus } from "../components/OpsMap";
import { screenContext, type DssAction } from "../components/ChatPanel";
import { LEVELS, RISK_COLOR, RISK_TR, STATUS_COLOR, km, posAt, rank, toHHMM, toMin } from "../risk";

const NO_FOCUS: MapFocus = { report: null, zonePoints: [], subjects: [] };

interface Detail { img: ImageDetail; dossier: Dossier; assessment: Assessment | null; reports: Report[]; tracks: TrackFull[] }

export default function Ops({ id, initialReport }: { id: string | null; initialReport?: string | null }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [d, setD] = useState<Detail | null>(null);
  const [time, setTime] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [vehicle, setVehicle] = useState<string | null>(null);
  const [focus, setFocus] = useState<MapFocus>(NO_FOCUS);
  const [fitTo, setFitTo] = useState<[number, number][] | null>(null);
  const [job, setJob] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState<DssAction | null>(null);
  const [highlight, setHighlight] = useState<{ title: string; tracks: TrackFull[] } | null>(null);

  // Chatbot aksiyonları
  useEffect(() => {
    const on = (e: Event) => {
      const a = (e as CustomEvent<DssAction>).detail;
      if (a.action === "show_reports") { window.location.hash = `#/reports/${a.status ?? ""}`; return; }
      if (a.action === "highlight_tracks" && a.track_ids?.length) {
        Promise.all(a.track_ids.map((t) => api.track(t))).then((tracks) => {
          setHighlight({ title: a.title || `${tracks.length} araç`, tracks });
          setFitTo(tracks.flatMap((t) => t.points.map((q) => [q.lat, q.lon] as [number, number])));
        });
        return;
      }
      if (a.image_id) {
        setPending(a);
        if (a.image_id !== id) window.location.hash = `#/image/${a.image_id}`;
      }
    };
    window.addEventListener("dss-action", on);
    return () => window.removeEventListener("dss-action", on);
  }, [id]);

  const loadOverview = useCallback(() => api.overview().then(setOverview).catch((e) => setErr(String(e))), []);
  useEffect(() => { loadOverview(); }, [loadOverview]);

  // Seçim yoksa en riskli olayı aç (ekran boş kalmasın)
  useEffect(() => {
    if (!id && overview) {
      const top = [...overview.images].sort((a, b) => rank(a.max_risk) - rank(b.max_risk) || a.capture_time.localeCompare(b.capture_time))[0];
      if (top) window.location.hash = `#/image/${top.id}`;
    }
  }, [id, overview]);

  const loadDetail = useCallback(async (imageId: string) => {
    const [img, dossier, assessment, reports, tracks] = await Promise.all([
      api.image(imageId), api.dossier(imageId), api.assessment(imageId), api.reportsForImage(imageId), api.tracksForImage(imageId),
    ]);
    return { img, dossier, assessment, reports: reports.items, tracks: tracks.items };
  }, []);

  useEffect(() => {
    if (!id) return;
    setPlaying(false); setFocus(NO_FOCUS); setJob(null);
    loadDetail(id).then((det) => {
      setD(det);
      setTime(toMin(det.img.capture_time));
      const lvl = (vid: string, base: string) => det.assessment?.vehicles.find((v) => v.vehicle_id === vid)?.risk_level ?? base;
      const top = [...det.dossier.vehicles].sort((a, b) => rank(lvl(a.vehicle_id, a.baseline_risk.level) as never) - rank(lvl(b.vehicle_id, b.baseline_risk.level) as never) || b.baseline_risk.score - a.baseline_risk.score)[0];
      setVehicle(top?.vehicle_id ?? null);
      const pts = det.tracks.flatMap((t) => t.points.map((p) => [p.lat, p.lon] as [number, number]));
      setFitTo(pts.length ? pts : [[det.img.center.lat, det.img.center.lon]]);
    }).catch((e) => setErr(String(e)));
  }, [id, loadDetail]);

  // Adresle gelen rapor odağı (#/image/<id>?report=R092) — demo bağlantıları için
  useEffect(() => {
    if (!initialReport || !d || !overview) return;
    const r = d.reports.find((x) => x.id === initialReport);
    if (r) focusReport(r);
  }, [initialReport, d?.img.id, overview]); // eslint-disable-line react-hooks/exhaustive-deps

  // Bekleyen chatbot aksiyonunu, ilgili olay yüklendiğinde uygula
  useEffect(() => {
    if (!pending || !d || d.img.id !== pending.image_id) return;
    const a = pending;
    setPending(null);
    if (a.action === "open_event" && a.vehicle_id) selectVehicle(a.vehicle_id);
    if (a.action === "play_track" && a.track_id) {
      const v = d.dossier.vehicles.find((x) => x.track_id === a.track_id);
      if (v) selectVehicle(v.vehicle_id);
      setTime(toMin(d.img.capture_time) - 120);
      setTimeout(() => setPlaying(true), 400);
    }
    if (a.action === "focus_report" && a.report_id) {
      const r = d.reports.find((x) => x.id === a.report_id);
      if (r) focusReport(r);
    }
  }, [pending, d]); // eslint-disable-line react-hooks/exhaustive-deps

  // Chatbot bağlamı: kullanıcı neye bakıyor
  useEffect(() => {
    Object.assign(screenContext, {
      page: "operasyon", image_id: id, time: time != null ? toHHMM(time) : null,
      zone: d?.img.zone, selected_vehicle: vehicle, selected_track: d?.dossier.vehicles.find((v) => v.vehicle_id === vehicle)?.track_id ?? null,
      focused_report: focus.report?.id ?? null,
    });
  }, [id, time, vehicle, d, focus]);

  const end = d ? toMin(d.img.capture_time) : 0;
  const start = end - 120;

  // Oynatma: 5 dk adım, çekim anında durur
  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => setTime((x) => {
      if (x == null || x + 5 > end) { setPlaying(false); return end; }
      return x + 5;
    }), 600);
    return () => window.clearInterval(t);
  }, [playing, end]);

  const selTrackId = d?.dossier.vehicles.find((v) => v.vehicle_id === vehicle)?.track_id ?? null;
  const selTrack = d?.tracks.find((t) => t.track_id === selTrackId) ?? null;

  const selectVehicle = (vid: string) => {
    setVehicle(vid);
    const tr = d?.tracks.find((t) => t.track_id === d.dossier.vehicles.find((v) => v.vehicle_id === vid)?.track_id);
    if (tr) setFitTo(tr.points.map((p) => [p.lat, p.lon]));
  };
  const selectTrackOnMap = (trackId: string) => {
    const v = d?.dossier.vehicles.find((x) => x.track_id === trackId);
    if (v) setVehicle(v.vehicle_id);
  };

  async function focusReport(r: Report) {
    if (!d || !overview) return;
    setPlaying(false);
    const t = Math.min(Math.max(toMin(r.time), start), end);
    setTime(t);
    const all = [...d.dossier.reports, ...d.dossier.context_reports].find((x) => x.report_id === r.id);
    const subjects = [...new Set((all?.checks ?? []).flatMap((c) => (c.subjects ?? []).map((s) => s.track_id).filter(Boolean) as string[]))];
    if (r.category === "zone" && r.links.zone) {
      const z = await api.zoneTracks(r.time, r.links.zone);
      setFocus({ report: r, zonePoints: z.points, subjects });
      const zc = overview.zones.find((x) => x.name === r.links.zone)!;
      setFitTo([[overview.base.lat, overview.base.lon], [zc.lat, zc.lon], ...z.points.map((p) => [p.lat, p.lon] as [number, number])]);
    } else {
      setFocus({ report: r, zonePoints: [], subjects });
      const pts: [number, number][] = r.coord ? [[r.coord.lat, r.coord.lon]] : [];
      d.tracks.filter((x) => subjects.includes(x.track_id)).forEach((x) => { const p = posAt(x.points, toMin(r.time)); if (p) pts.push(p); });
      if (pts.length) setFitTo(pts.length === 1 ? [pts[0], [pts[0][0] + 0.002, pts[0][1] + 0.002]] : pts);
    }
  }

  async function analyze(force: boolean) {
    if (!id) return;
    try { const j = await api.assess(id, force); setJob(j.events_url); } catch (e) { setErr(String(e)); }
  }
  const jobDone = () => { setJob(null); if (id) loadDetail(id).then(setD); loadOverview(); };

  // Seçili aracın zaman çubuğundaki durumu
  const status = useMemo(() => {
    if (!selTrack || time == null) return null;
    const pts = selTrack.points;
    const i = pts.findIndex((p) => toMin(p.time) >= time);
    const p = pts[Math.max(0, i === -1 ? pts.length - 1 : i)];
    return `${selTrack.track_id} · ${km(p.dist_to_base_m)}`;
  }, [selTrack, time]);

  if (err) return <div className="page">Hata: {err} — Flask API (port 5000) çalışıyor mu?</div>;
  if (!overview) return <div className="page muted">Yükleniyor…</div>;
  const selectedSummary = overview.images.find((i) => i.id === id) ?? null;

  return (
    <div className="grid h-[calc(100vh-49px)]" style={{ gridTemplateColumns: "300px 1fr 500px" }}>
      <aside className="border-r border-slate-800 bg-[var(--panel)] min-h-0">
        <div className="px-3 py-2 border-b border-slate-800 flex gap-1.5">
          {LEVELS.map((l) => (
            <div key={l} className="flex-1 rounded border px-1.5 py-1 text-center" style={{ borderColor: RISK_COLOR[l] + "80" }}>
              <div className="font-bold" style={{ color: RISK_COLOR[l] }}>{overview.risk_summary[l]}</div>
              <div className="text-[9px] text-slate-400">{RISK_TR[l]}</div>
            </div>
          ))}
        </div>
        <div className="h-[calc(100%-58px)]">
          <EventList images={overview.images} selected={id} onSelect={(x) => (window.location.hash = `#/image/${x}`)} />
        </div>
      </aside>

      <main className="relative min-h-0">
        <OpsMap overview={overview} selected={selectedSummary} tracks={d?.tracks ?? []} reports={d?.reports ?? []}
          time={time} selectedTrack={selTrackId} focus={focus} fitTo={fitTo}
          onSelectImage={(x) => (window.location.hash = `#/image/${x}`)} onSelectTrack={selectTrackOnMap} onSelectReport={focusReport}
          highlight={highlight?.tracks ?? []} />

        {highlight && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[900] bg-sky-950/90 border border-sky-600 rounded-lg px-3 py-1.5 text-xs flex items-center gap-3">
            <span>🤖 Asistan: <b>{highlight.title}</b> ({highlight.tracks.map((t) => t.track_id).join(", ")})</span>
            <button className="!py-0 !px-1.5 text-[10px]" onClick={() => setHighlight(null)}>kapat</button>
          </div>
        )}

        {/* lejant */}
        <div className="absolute top-3 left-3 z-[900] flex gap-3 bg-slate-950/70 rounded-md px-2.5 py-1 text-[10px] text-slate-300">
          <span><span className="inline-block w-2.5 h-2.5 rounded-full bg-sky-500 mr-1 align-middle" />üs</span>
          <span><span className="inline-block w-2.5 h-2.5 rounded-full bg-orange-500 mr-1 align-middle" />araç</span>
          <span><span className="inline-block w-2 h-2 rotate-45 bg-red-500 mr-1 align-middle" />rapor</span>
          <span><span className="inline-block w-2 h-2 rounded-full bg-slate-500 mr-1 align-middle" />diğer olay</span>
        </div>

        {focus.report && (
          <div className="absolute top-3 right-3 z-[900] max-w-sm bg-slate-950/90 border rounded-lg px-3 py-2 text-xs" style={{ borderColor: STATUS_COLOR[focus.report.status] }}>
            <div className="flex items-center gap-2 mb-1">
              <b>{focus.report.id}</b><span className="text-slate-400">{focus.report.time}</span>
              <span className="flex-1" /><button className="!py-0 !px-1.5 text-[10px]" onClick={() => setFocus(NO_FOCUS)}>kapat</button>
            </div>
            <div>“{focus.report.text}”</div>
          </div>
        )}

        {/* zaman çubuğu: yalnızca seçili olayın 2 saati */}
        {d && time != null && (
          <div className="absolute left-3 right-3 bottom-3 z-[900] bg-slate-950/90 border border-slate-700 rounded-lg px-3 py-2">
            <div className="flex items-center gap-3">
              <button onClick={() => { if (time >= end) setTime(start); setPlaying(!playing); }}>{playing ? <Pause size={16} /> : <Play size={16} />}</button>
              <button onClick={() => { setPlaying(false); setTime(start); }} title="başa sar"><RotateCcw size={14} /></button>
              <span className="font-mono text-lg font-bold w-14">{toHHMM(time)}</span>
              <div className="relative flex-1">
                <input className="w-full" type="range" min={start} max={end} step={5} value={time} onChange={(e) => setTime(Number(e.target.value))} />
                {/* rapor anları */}
                {d.reports.filter((r) => toMin(r.time) >= start && toMin(r.time) <= end).map((r) => (
                  <div key={r.id} title={`${r.id} ${r.time}`} onClick={() => focusReport(r)}
                    className="absolute -top-2.5 w-2.5 h-2.5 rotate-45 cursor-pointer border border-slate-900"
                    style={{ left: `calc(${((toMin(r.time) - start) / 120) * 100}% - 5px)`, background: STATUS_COLOR[r.status] }} />
                ))}
              </div>
              <span className="text-xs text-slate-300 w-36 text-right font-mono">{status ?? ""}{time >= end ? " 📷" : ""}</span>
            </div>
          </div>
        )}
      </main>

      <aside className="border-l border-slate-800 bg-[var(--panel)] min-h-0">
        {d ? <EventDetail img={d.img} dossier={d.dossier} assessment={d.assessment} reports={d.reports}
          selectedVehicle={vehicle} onSelectVehicle={selectVehicle} focusReportId={focus.report?.id ?? null} onFocusReport={focusReport}
          onAnalyze={analyze} jobUrl={job} onJobDone={jobDone} />
          : <div className="page muted">Yükleniyor…</div>}
      </aside>
    </div>
  );
}
