import { useState } from "react";
import { BellRing, ChevronDown, ChevronRight, Loader2, Play } from "lucide-react";
import { api, type AlertRuleHit, type AlertRuleResult } from "../api";
import { LABEL_TR, km } from "../risk";

// Komutan alarm kuralı: doğal dilde yazılan kural tüm gün üzerinde geriye dönük sınanır (/api/alert-rules/test).
// Sonuçlar Ops ekranına 'dss-action' olaylarıyla iletilir (haritada vurgula, tüm gün görünümünde o saate git).

const EXAMPLES = [
  "Bir kamyon üsse 1 km'den fazla yaklaşırsa uyar",
  "Üssün etrafında dönen araç olursa uyar",
  "Herhangi bir araç üsse 1 km'den fazla yaklaşırsa uyar",
  "Öğleden sonra Kuzeybatı Yolu'nda ağır vasıta görülürse alarm ver",
];

const fire = (detail: object) => window.dispatchEvent(new CustomEvent("dss-action", { detail }));

export default function RulePanel() {
  const [open, setOpen] = useState(true);
  const [text, setText] = useState(EXAMPLES[0]);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<AlertRuleResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const showAll = (r: AlertRuleResult) => {
    if (!r.hits.length) return;
    fire({ action: "goto_time", time: r.hits[0].trigger_time });
    fire({ action: "highlight_tracks", track_ids: r.hits.slice(0, 12).map((h) => h.track_id),
           title: `Alarm kuralı: ${r.rule_text} → ${r.total} araç` });
  };
  const showHit = (h: AlertRuleHit) => {
    fire({ action: "goto_time", time: h.trigger_time });
    fire({ action: "highlight_tracks", track_ids: [h.track_id],
           title: `${h.track_id} · alarm ${h.trigger_time} · en yakın ${km(h.min_dist_m)} (${h.min_time})` });
  };

  async function run(t = text) {
    if (!t.trim() || busy) return;
    setText(t); setBusy(true); setErr(null);
    try {
      const r = await api.testAlertRule(t);
      setRes(r);
      if (r.total <= 12) showAll(r);
    } catch (e) {
      setErr(String(e));
    } finally { setBusy(false); }
  }

  return (
    <div className="border-b border-slate-800">
      <button className="w-full !rounded-none !border-0 !bg-transparent flex items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <BellRing size={14} className="text-amber-400" />
        <span className="section-title !m-0 flex-1">Alarm kuralı · tüm gün testi</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); run(); }}>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run(); } }}
              placeholder="Örn: Bir kamyon üsse 1 km'den fazla yaklaşırsa uyar"
              className="flex-1 resize-none bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-xs outline-none focus:border-amber-500" />
            <button type="submit" disabled={busy} title="Tüm günde test et" className="!px-2 !bg-amber-700 !border-amber-500">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            </button>
          </form>
          <div className="flex flex-wrap gap-1">
            {EXAMPLES.map((x) => (
              <button key={x} className="!text-[10px] !leading-tight !py-0.5 !px-1.5 text-left" onClick={() => run(x)}>{x}</button>
            ))}
          </div>

          {err && <div className="text-xs text-red-400">{err}</div>}

          {res && (
            <div className="space-y-1.5">
              <div className="text-[11px] text-slate-400">
                <span className={`mr-1 rounded px-1 text-[9px] font-bold ${res.parsed_by === "llm" ? "bg-sky-800 text-sky-100" : "bg-slate-700 text-slate-200"}`}
                  title={res.parsed_by === "llm" ? "kuralı LLM çevirdi; sayıları kod hesapladı" : "kuralı kural ayrıştırıcı çevirdi"}>
                  {res.parsed_by === "llm" ? "LLM" : "KURAL"}
                </span>
                Anlaşılan kural: <b className="text-slate-200">{res.rule_text}</b>
                {res.notes.length > 0 && <span> ({res.notes.join("; ")})</span>}
              </div>
              <div className="rounded-md border border-amber-600/60 bg-amber-950/30 px-2 py-1.5 text-xs">
                <div>
                  <b className="text-amber-300 text-base">{res.total}</b> araç tetikler
                  {res.rule.vehicle !== "any" && <span className="text-slate-400"> · tip filtresi olmadan {res.any_vehicle_total}</span>}
                </div>
                {res.median_lead_min != null && (
                  <div className="text-slate-300">İlk fotoğraftan medyan <b>{res.median_lead_min} dk</b> önce uyarı</div>
                )}
                {res.unlabeled > 0 && <div className="text-slate-400">{res.unlabeled} etiketsiz araç da koşulu sağlıyor (tipi bilinmiyor)</div>}
                {res.total > 12 && (
                  <button className="mt-1 !text-[10px] !py-0.5" onClick={() => showAll(res)}>ilk 12'yi haritada göster</button>
                )}
              </div>
              <div className="max-h-[260px] overflow-y-auto space-y-1 pr-1">
                {res.hits.map((h) => (
                  <div key={h.track_id} onClick={() => showHit(h)}
                    className="cursor-pointer rounded border border-slate-800 hover:border-amber-500 px-2 py-1 text-[11px] leading-snug">
                    <div className="flex items-center gap-1.5">
                      <b className="font-mono text-amber-300">{h.trigger_time}</b>
                      <b>{h.track_id}</b>
                      <span className="text-slate-300">{h.label ? LABEL_TR[h.label] ?? h.label : "etiketsiz"}</span>
                      {h.circling && <span className="text-red-400" title={`üssün etrafında döndü ${h.circling}`}>↻ döndü</span>}
                      <span className="flex-1" />
                      <a className="text-sky-400" onClick={(e) => { e.stopPropagation(); fire({ action: "select_track", image_id: h.image_id, track_id: h.track_id }); }}>olay →</a>
                    </div>
                    <div className="text-slate-400">en yakın {km(h.min_dist_m)} ({h.min_time}) · {h.zone}</div>
                    <div className="text-slate-400">
                      fotoğraf {h.photo_time} ({km(h.photo_dist_m)})
                      {h.lead_min > 0 && <> → <b className="text-amber-300">{h.lead_min} dk önce</b> uyarı</>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
