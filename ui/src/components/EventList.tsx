import { useMemo, useState } from "react";
import type { ImageSummary, Level } from "../api";
import { RISK_COLOR, RISK_TR, rank } from "../risk";

const MAX_IDS = 6;   // satırda gösterilen track sayısı (riskliden az riskliye)

// Sol panel: 40 olay (drone görüntüsü) zaman sırasıyla — ana gezinme
export default function EventList({ images, selected, onSelect, zone = null, onClearZone, trackFocus = null, onClearTrack,
  tracksByImage = {}, onSelectTrack }: {
  images: ImageSummary[]; selected: string | null; onSelect: (id: string) => void;
  zone?: string | null; onClearZone?: () => void;   // haritada seçilen bölge dilimi
  trackFocus?: string | null; onClearTrack?: () => void;   // aramadan seçilen iz: yalnızca onun olayı
  tracksByImage?: Record<string, { id: string; risk: Level | null }[]>;
  onSelectTrack?: (imageId: string, trackId: string) => void;
}) {
  const [onlyHigh, setOnlyHigh] = useState(false);
  const list = useMemo(() => images
    .filter((i) => trackFocus ? i.id === selected : (!onlyHigh || rank(i.max_risk) <= 1) && (!zone || i.zone === zone))
    .sort((a, b) => a.capture_time.localeCompare(b.capture_time) || a.id.localeCompare(b.id)), [images, onlyHigh, zone, trackFocus, selected]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800">
        <span className="section-title !m-0 flex-1">Olaylar</span>
        <button className={`text-xs !py-0.5 ${onlyHigh ? "!border-orange-500" : ""}`} onClick={() => setOnlyHigh(!onlyHigh)}>
          {onlyHigh ? "tümü" : "yüksek+"}
        </button>
      </div>
      {trackFocus && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-slate-800 bg-amber-950/40 text-xs">
          <span className="flex-1">İz: <b>{trackFocus}</b> <span className="text-slate-400">· {list.length} olay</span></span>
          <button className="!py-0 !px-1.5 !text-[10px]" onClick={onClearTrack} title="iz filtresini kaldır">✕ tümü</button>
        </div>
      )}
      {zone && !trackFocus && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-slate-800 bg-slate-900/60 text-xs">
          <span className="flex-1">Bölge: <b>{zone}</b> <span className="text-slate-400">· {list.length} olay</span></span>
          <button className="!py-0 !px-1.5 !text-[10px]" onClick={onClearZone} title="bölge filtresini kaldır">✕ tümü</button>
        </div>
      )}
      <div className="overflow-y-auto flex-1">
        {list.map((i) => {
          const sel = i.id === selected;
          return (
            <div key={i.id} onClick={() => onSelect(i.id)} title={i.summary ?? undefined}
              className={`px-3 py-2 border-b border-slate-800/70 cursor-pointer transition-colors ${sel ? "bg-slate-800" : "hover:bg-slate-900"}`}
              style={{ borderLeft: `4px solid ${sel ? RISK_COLOR[i.max_risk] : "transparent"}` }}>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold">{i.capture_time}</span>
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: RISK_COLOR[i.max_risk] }} />
                <span className="text-xs font-bold" style={{ color: RISK_COLOR[i.max_risk] }}>{RISK_TR[i.max_risk]}</span>
              </div>
              <div className="text-xs text-slate-400 truncate">{i.zone}</div>
              {(() => {
                const all = tracksByImage[i.id] ?? [];
                if (!all.length) return null;
                const shown = all.slice(0, MAX_IDS);
                const focused = all.find((t) => t.id === trackFocus);
                if (focused && !shown.includes(focused)) shown.push(focused);
                return (
                  <div className="mt-0.5 flex flex-wrap gap-x-1.5 font-mono text-[10px] leading-tight">
                    {shown.map((t) => (
                      <span key={t.id} title={`${t.id} izini göster`}
                        onClick={(e) => { e.stopPropagation(); onSelectTrack?.(i.id, t.id); }}
                        className={`cursor-pointer hover:underline ${t.id === trackFocus ? "underline font-bold" : ""}`}
                        style={{ color: t.risk && t.risk !== "low" ? RISK_COLOR[t.risk] : "#94a3b8" }}>{t.id}</span>
                    ))}
                    {all.length > shown.length && <span className="text-slate-500">+{all.length - shown.length}</span>}
                  </div>
                );
              })()}
            </div>
          );
        })}
      </div>
    </div>
  );
}
