import { useCallback, useEffect, useMemo, useState } from "react";
import { Bus, Car, Pause, Play, RotateCcw, Truck, Van } from "lucide-react";
import { api, type Assessment, type Dossier, type GlobalTrack, type ImageDetail, type Overview, type Report, type TrackFull } from "../api";
import EventDetail from "../components/EventDetail";
import EventList from "../components/EventList";
import OpsMap, { type MapFocus } from "../components/OpsMap";
import RulePanel from "../components/RulePanel";
import { screenContext, type DssAction } from "../components/ChatPanel";
import { LABEL_TR, LEVELS, RISK_COLOR, RISK_TR, STATUS_COLOR, km, posAt, rank, toHHMM, toMin } from "../risk";

const NO_FOCUS: MapFocus = { report: null, zonePoints: [], subjects: [] };

interface Detail { img: ImageDetail; dossier: Dossier; assessment: Assessment | null; reports: Report[]; tracks: TrackFull[] }

export default function Ops({ id, initialReport, initialMode = "event" }: { id: string | null; initialReport?: string | null; initialMode?: "event" | "global" }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [d, setD] = useState<Detail | null>(null);
  const [time, setTime] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [mode, setMode] = useState<"event" | "global">(initialMode);
  const [allTracks, setAllTracks] = useState<GlobalTrack[] | null>(null);
  const [gTime, setGTime] = useState<number | null>(null);
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
      // Alarm kuralı: tüm gün görünümünde alarm anına git
      if (a.action === "goto_time" && a.time) { setPlaying(false); setFocus(NO_FOCUS); setMode("global"); setGTime(toMin(a.time)); return; }
      if (a.action === "select_track") setMode("event");
      if (a.action === "highlight_tracks" && a.track_ids?.length) {
        if (a.time) { setPlaying(false); setMode("global"); setGTime(toMin(a.time)); }   // alarm kuralı sonucu
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
    if (a.action === "select_track" && a.track_id) {
      const v = d.dossier.vehicles.find((x) => x.track_id === a.track_id);
      if (v) selectVehicle(v.vehicle_id);
    }
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

  // Tüm gün aralığı
  const gStart = overview ? toMin(overview.time_range.from) : 0;
  const gEnd = overview ? toMin(overview.time_range.to) : 0;
  useEffect(() => {
    if (mode !== "global" || !overview) return;   // aralık, genel görünüm yüklenince bilinir
    if (!allTracks) api.allTracks().then((r) => setAllTracks(r.items));
    if (gTime == null || gTime < gStart || gTime > gEnd) setGTime(gStart);
  }, [mode, overview]); // eslint-disable-line react-hooks/exhaustive-deps

  // Oynatma: 5 dk adım; olay modunda çekim anında, tüm gün modunda gün sonunda durur
  useEffect(() => {
    if (!playing) return;
    const set = mode === "global" ? setGTime : setTime;
    const last = mode === "global" ? gEnd : end;
    const t = window.setInterval(() => set((x) => {
      if (x == null || x + 5 > last) { setPlaying(false); return last; }
      return x + 5;
    }), mode === "global" ? 450 : 600);
    return () => window.clearInterval(t);
  }, [playing, end, mode, gEnd]);

  const switchMode = (m: "event" | "global") => {
    setPlaying(false); setMode(m); setFocus(NO_FOCUS); setHighlight(null);
    if (m === "global" && overview) setFitTo(overview.images.map((i) => [i.center.lat, i.center.lon] as [number, number]));
    if (m === "event" && d) setFitTo(d.tracks.flatMap((t) => t.points.map((p) => [p.lat, p.lon] as [number, number])));
  };
  const selectGlobal = (t: GlobalTrack) => {
    setMode("event"); setPlaying(false);
    setPending({ action: "select_track", image_id: t.image_id, track_id: t.track_id });
    if (t.image_id !== id) window.location.hash = `#/image/${t.image_id}`;
  };

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

  // "Ne görüyorum?" bandı
  const band = useMemo(() => {
    if (mode === "global") {
      if (!allTracks || gTime == null || !overview) return "Tüm gün yükleniyor…";
      const active = allTracks.map((t) => ({ t, p: posAt(t.points, gTime) })).filter((x) => x.p);
      const near = active.filter((x) => Math.hypot((x.p![0] - overview.base.lat) * 111320, (x.p![1] - overview.base.lon) * 85300) < 2000).length;
      const cons = active.filter((x) => x.t.consistent_approach).length;
      const circ = active.filter((x) => x.t.circling).map((x) => x.t.track_id);
      const cams = overview.images.filter((i) => Math.abs(toMin(i.capture_time) - gTime) <= 5).length;
      return `${toHHMM(gTime)} · ${active.length} araç kayıtta · ${near}'i üsse 2 km içinde · ${cons}'i tutarlı yaklaşan araç` + (circ.length ? ` · üssün etrafında dönen: ${circ.join(", ")}` : "") + (cams ? ` · ${cams} görüntü çekiliyor` : "") + " · araca tıkla → olayı aç";
    }
    if (!d) return "";
    if (focus.report) {
      return focus.report.category === "zone"
        ? `${focus.report.id} (${focus.report.time}): mor alan = raporun bölgesi, mor noktalar = rapor anında o bölgedeki araçlar`
        : `${focus.report.id} (${focus.report.time}): harita rapor anında; kesikli çizgi = raporun anlattığı araç`;
    }
    const lvl = (vid: string, base: string) => d.assessment?.vehicles.find((v) => v.vehicle_id === vid)?.risk_level ?? base;
    const top = [...d.dossier.vehicles].sort((a, b) => rank(lvl(a.vehicle_id, a.baseline_risk.level) as never) - rank(lvl(b.vehicle_id, b.baseline_risk.level) as never))[0];
    if (!top) return `${d.img.capture_time} · ${d.img.zone}`;
    const k = top.kinematics;
    const how = k ? (k.circling ? `${k.circling_window} arasında üssün etrafında ~${Math.round(k.circling_radius_m ?? 0)} m'de döndü` : k.consistent_approach ? "2 saatte her hareketinde üsse yaklaştı" : k.motion === "approaching" ? "son 1 saatte üsse yaklaştı" : k.motion === "stationary" ? `${k.stationary_min} dk'dır duruyor` : k.motion === "receding" ? "üsten uzaklaşıyor" : "yanal hareket") : "park halinde";
    return `${d.img.capture_time} · ${d.img.zone} · En dikkat çeken: ${top.track_id ?? "tespitsiz araç"} ${top.label ? LABEL_TR[top.label] ?? top.label : ""}, üsse ${km(top.dist_to_base_m)}, ${how} · ▶ ile 2 saatini izle`;
  }, [mode, allTracks, gTime, overview, d, focus]);

  if (err) return <div className="page">Hata: {err} — Flask API (port 5000) çalışıyor mu?</div>;
  if (!overview) return <div className="page muted">Yükleniyor…</div>;
  const selectedSummary = overview.images.find((i) => i.id === id) ?? null;

  return (
    <div className="grid h-[calc(100vh-49px)]" style={{ gridTemplateColumns: "300px 1fr 500px" }}>
      <aside className="border-r border-slate-800 bg-[var(--panel)] min-h-0 flex flex-col">
        <div className="px-3 py-2 border-b border-slate-800 flex gap-1.5">
          {LEVELS.map((l) => (
            <div key={l} className="flex-1 rounded border px-1.5 py-1 text-center" style={{ borderColor: RISK_COLOR[l] + "80" }}>
              <div className="font-bold" style={{ color: RISK_COLOR[l] }}>{overview.risk_summary[l]}</div>
              <div className="text-[9px] text-slate-400">{RISK_TR[l]}</div>
            </div>
          ))}
        </div>
        <RulePanel />
        <div className="flex-1 min-h-0">
          <EventList images={overview.images} selected={id} onSelect={(x) => (window.location.hash = `#/image/${x}`)} />
        </div>
      </aside>

      <main className="relative min-h-0">
        <OpsMap overview={overview} selected={mode === "event" ? selectedSummary : null}
          tracks={mode === "event" ? d?.tracks ?? [] : []} reports={mode === "event" ? d?.reports ?? [] : []}
          time={time} selectedTrack={selTrackId} focus={focus} fitTo={fitTo}
          onSelectImage={(x) => (window.location.hash = `#/image/${x}`)} onSelectTrack={selectTrackOnMap} onSelectReport={focusReport}
          highlight={highlight?.tracks ?? []}
          global={mode === "global" && allTracks && gTime != null ? { tracks: allTracks, time: gTime } : null}
          onSelectGlobal={selectGlobal} />

        {/* Ne görüyorum? */}
        {band && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[890] max-w-[70%] bg-slate-950/85 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 text-center">
            {band}
          </div>
        )}

        {highlight && (
          <div className="absolute top-12 left-1/2 -translate-x-1/2 z-[900] bg-sky-950/90 border border-sky-600 rounded-lg px-3 py-1.5 text-xs flex items-center gap-3">
            <span>🤖 Asistan: <b>{highlight.title}</b> ({highlight.tracks.map((t) => t.track_id).join(", ")})</span>
            <button className="!py-0 !px-1.5 text-[10px]" onClick={() => setHighlight(null)}>kapat</button>
          </div>
        )}

        {/* lejant */}
        <div className="absolute bottom-20 left-3 z-[900] flex flex-col gap-1 bg-slate-950/80 rounded-md px-2.5 py-1.5 text-[10px] text-slate-300">
          <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full bg-sky-500" />üs</span>
          <span className="flex items-center gap-1"><Car size={12} /><Van size={12} /><Truck size={12} /><Bus size={12} /> araç · halka rengi = risk</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rotate-45 bg-red-500 mx-0.5" />rapor · renk = doğruluk</span>
          {mode === "event" && <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-slate-500 mx-0.5" />diğer olay</span>}
        </div>

        {focus.report && (
          <div className="absolute top-14 right-3 z-[900] max-w-sm bg-slate-950/90 border rounded-lg px-3 py-2 text-xs" style={{ borderColor: STATUS_COLOR[focus.report.status] }}>
            <div className="flex items-center gap-2 mb-1">
              <b>{focus.report.id}</b><span className="text-slate-400">{focus.report.time}</span>
              <span className="flex-1" /><button className="!py-0 !px-1.5 text-[10px]" onClick={() => setFocus(NO_FOCUS)}>kapat</button>
            </div>
            <div>“{focus.report.text}”</div>
          </div>
        )}

        {/* zaman çubuğu: olay (2 saat) ya da tüm gün */}
        {(mode === "global" ? gTime != null : d && time != null) && (() => {
          const g = mode === "global";
          const t = g ? gTime! : time!;
          const lo = g ? gStart : start, hi = g ? gEnd : end;
          const set = g ? setGTime : setTime;
          return (
            <div className="absolute left-3 right-3 bottom-3 z-[900] bg-slate-950/90 border border-slate-700 rounded-lg px-3 py-2">
              <div className="flex items-center gap-3">
                <div className="flex rounded-md overflow-hidden border border-slate-700 text-[11px]">
                  <button className={`!rounded-none !border-0 !py-1 ${!g ? "!bg-sky-800" : ""}`} onClick={() => switchMode("event")}>Olay</button>
                  <button className={`!rounded-none !border-0 !py-1 ${g ? "!bg-sky-800" : ""}`} onClick={() => switchMode("global")}>Tüm gün</button>
                </div>
                <button onClick={() => { if (t >= hi) set(lo); setPlaying(!playing); }}>{playing ? <Pause size={16} /> : <Play size={16} />}</button>
                <button onClick={() => { setPlaying(false); set(lo); }} title="başa sar"><RotateCcw size={14} /></button>
                <span className="font-mono text-lg font-bold w-14">{toHHMM(t)}</span>
                <div className="relative flex-1">
                  <input className="w-full" type="range" min={lo} max={hi} step={5} value={t} onChange={(e) => set(Number(e.target.value))} />
                  {!g && d && d.reports.filter((r) => toMin(r.time) >= lo && toMin(r.time) <= hi).map((r) => (
                    <div key={r.id} title={`${r.id} ${r.time}`} onClick={() => focusReport(r)}
                      className="absolute -top-2.5 w-2.5 h-2.5 rotate-45 cursor-pointer border border-slate-900"
                      style={{ left: `calc(${((toMin(r.time) - lo) / (hi - lo)) * 100}% - 5px)`, background: STATUS_COLOR[r.status] }} />
                  ))}
                  {g && overview.images.map((im) => (
                    <div key={im.id} title={`${im.capture_time} ${im.zone}`} onClick={() => (window.location.hash = `#/image/${im.id}`)}
                      className="absolute -top-2.5 w-1.5 h-2.5 cursor-pointer rounded-sm"
                      style={{ left: `calc(${((toMin(im.capture_time) - lo) / (hi - lo)) * 100}% - 3px)`, background: RISK_COLOR[im.max_risk] }} />
                  ))}
                </div>
                <span className="text-xs text-slate-300 w-36 text-right font-mono">{g ? "" : `${status ?? ""}${t >= hi ? " ●" : ""}`}</span>
              </div>
            </div>
          );
        })()}
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
