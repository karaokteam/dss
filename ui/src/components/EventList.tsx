import { useMemo, useState } from "react";
import type { ImageSummary } from "../api";
import { RISK_COLOR, RISK_TR, rank } from "../risk";

// Sol panel: 40 olay (drone görüntüsü) zaman sırasıyla — ana gezinme
export default function EventList({ images, selected, onSelect }: {
  images: ImageSummary[]; selected: string | null; onSelect: (id: string) => void;
}) {
  const [onlyHigh, setOnlyHigh] = useState(false);
  const list = useMemo(() => images
    .filter((i) => !onlyHigh || rank(i.max_risk) <= 1)
    .sort((a, b) => a.capture_time.localeCompare(b.capture_time) || a.id.localeCompare(b.id)), [images, onlyHigh]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800">
        <span className="section-title !m-0 flex-1">Olaylar</span>
        <button className={`text-xs !py-0.5 ${onlyHigh ? "!border-orange-500" : ""}`} onClick={() => setOnlyHigh(!onlyHigh)}>
          {onlyHigh ? "tümü" : "yüksek+"}
        </button>
      </div>
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
            </div>
          );
        })}
      </div>
    </div>
  );
}
