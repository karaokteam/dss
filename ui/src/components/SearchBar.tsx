import { useEffect, useMemo, useRef, useState } from "react";
import { FileText, Image as ImageIcon, Loader2, Search, Truck } from "lucide-react";
import { api, type GlobalTrack, type ImageSummary, type Report } from "../api";
import { LABEL_TR, RISK_COLOR, RISK_TR, STATUS_COLOR, STATUS_TR } from "../risk";

// Üst bar araması: track (T0122 / 122), rapor (R042 / 42 / metin), olay (img_000860 / bölge adı).
// Seçim adrese yazılır (#/image/<id>?track=… | ?report=…); Ops ekranı aracı seçer ya da raporu haritada odaklar.

interface Hit { kind: "track" | "report" | "image"; id: string; title: string; sub: string; color: string; score: number; href: string }

const fold = (s: string) => s.toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");
let cache: { tracks: GlobalTrack[]; reports: Report[]; images: ImageSummary[] } | null = null;

function search(q: string, data: NonNullable<typeof cache>): Hit[] {
  const f = fold(q.trim());
  if (!f) return [];
  const num = f.match(/^([tr])?0*(\d+)$/);            // "t122", "122", "r42", "42"
  const hits: Hit[] = [];
  const idScore = (id: string, letter: "t" | "r" | null) => {
    const fid = fold(id);
    if (num && (!num[1] || num[1] === letter) && Number(fid.replace(/\D/g, "")) === Number(num[2])) return 0;
    if (fid === f) return 0;
    if (fid.startsWith(f)) return 1;
    return fid.includes(f) ? 2 : -1;
  };
  for (const t of data.tracks) {
    const s = idScore(t.track_id, "t");
    if (s < 0) continue;
    const flags = [t.circling ? `↻ üssün etrafında döndü (${t.circling_window})` : "", t.consistent_approach ? "tutarlı yaklaşma" : ""].filter(Boolean).join(" · ");
    hits.push({ kind: "track", id: t.track_id, score: s, color: t.risk_level ? RISK_COLOR[t.risk_level] : "#94a3b8",
      title: `${t.track_id} · ${t.label ? LABEL_TR[t.label] ?? t.label : "etiketsiz"}${t.risk_level ? " · " + RISK_TR[t.risk_level] : ""}`,
      sub: `${t.image_id} · kayıt sonu ${t.points[t.points.length - 1]?.time ?? "-"}${flags ? " · " + flags : ""}`,
      href: `#/image/${t.image_id}?track=${t.track_id}` });
  }
  for (const r of data.reports) {
    let s = idScore(r.id, "r");
    let snippet = r.text;
    if (s < 0 && f.length >= 3) {
      const i = fold(r.text).indexOf(f);
      if (i >= 0) { s = 3; snippet = (i > 30 ? "…" : "") + r.text.slice(Math.max(0, i - 30), i + 70) + (i + 70 < r.text.length ? "…" : ""); }
    }
    if (s < 0) continue;
    hits.push({ kind: "report", id: r.id, score: s, color: STATUS_COLOR[r.status] ?? "#64748b",
      title: `${r.id} · ${r.time} · ${r.source === "official" ? "resmi" : "üçüncü taraf"} · ${STATUS_TR[r.status] ?? r.status}`,
      sub: snippet, href: r.links.images.length ? `#/image/${r.links.images[0]}?report=${r.id}` : "#/reports" });
  }
  for (const im of data.images) {
    let s = fold(im.id).includes(f) ? (fold(im.id) === f ? 0 : 2) : -1;
    if (s < 0 && f.length >= 3 && fold(im.zone).includes(f)) s = 3;
    if (s < 0) continue;
    hits.push({ kind: "image", id: im.id, score: s, color: RISK_COLOR[im.max_risk],
      title: `${im.id} · ${im.capture_time} · ${RISK_TR[im.max_risk]}`, sub: im.zone, href: `#/image/${im.id}` });
  }
  const pick = (k: Hit["kind"], n: number) => hits.filter((h) => h.kind === k).sort((a, b) => a.score - b.score || a.id.localeCompare(b.id)).slice(0, n);
  return [...pick("track", 6), ...pick("report", 6), ...pick("image", 4)].sort((a, b) => a.score - b.score);
}

const ICON = { track: Truck, report: FileText, image: ImageIcon };
const KIND_TR = { track: "araç izi", report: "rapor", image: "olay" };

export default function SearchBar() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(cache);
  const [loading, setLoading] = useState(false);
  const [idx, setIdx] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  const load = () => {
    if (cache || loading) return;
    setLoading(true);
    Promise.all([api.allTracks(), api.reports(), api.overview()])
      .then(([t, r, o]) => { cache = { tracks: t.items, reports: r.items, images: o.images }; setData(cache); })
      .finally(() => setLoading(false));
  };
  const hits = useMemo(() => (data ? search(q, data) : []), [q, data]);
  useEffect(() => setIdx(0), [q]);

  // "/" ile aramaya odaklan (yazı alanında değilken)
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const el = document.activeElement as HTMLElement | null;
      if (e.key === "/" && !(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA"))) { e.preventDefault(); input.current?.focus(); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  const choose = (h: Hit) => {
    window.location.hash = h.href;
    setQ(h.id); setOpen(false); input.current?.blur();
  };

  return (
    <div className="relative w-[340px]">
      <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
      <input ref={input} value={q} placeholder="Ara: T0122, R042, rapor metni…  ( / )"
        onChange={(e) => { load(); setQ(e.target.value); setOpen(true); }}
        onFocus={() => { load(); setOpen(true); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, hits.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
          else if (e.key === "Enter" && hits[idx]) { e.preventDefault(); choose(hits[idx]); }
          else if (e.key === "Escape") { setOpen(false); input.current?.blur(); }
        }}
        className="w-full bg-slate-900 border border-slate-700 rounded-md pl-8 pr-2 py-1.5 text-xs outline-none focus:border-sky-500" />
      {open && q.trim() && (
        <div className="absolute left-0 right-0 top-full mt-1 z-[3000] max-h-[420px] overflow-y-auto rounded-md border border-slate-700 bg-slate-950/95 shadow-2xl shadow-black">
          {loading && <div className="px-3 py-2 text-xs text-slate-400"><Loader2 size={12} className="inline animate-spin mr-1" />yükleniyor…</div>}
          {!loading && data && hits.length === 0 && <div className="px-3 py-2 text-xs text-slate-400">Sonuç yok</div>}
          {hits.map((h, i) => {
            const Icon = ICON[h.kind];
            return (
              <div key={h.kind + h.id} onMouseDown={(e) => { e.preventDefault(); choose(h); }} onMouseEnter={() => setIdx(i)}
                className={`flex gap-2 px-3 py-1.5 cursor-pointer border-b border-slate-800/70 ${i === idx ? "bg-slate-800" : ""}`}>
                <Icon size={14} className="mt-0.5 shrink-0" style={{ color: h.color }} />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold truncate">{h.title}</div>
                  <div className="text-[11px] text-slate-400 truncate">{h.sub}</div>
                </div>
                <span className="text-[9px] uppercase text-slate-500 mt-0.5">{KIND_TR[h.kind]}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
