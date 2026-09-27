import { useEffect, useRef, useState } from "react";
import { rel } from "../api";

// SSE canlı agent izi: /api/jobs/<id>/events
interface Ev { id: number; type: string; [k: string]: unknown }

const ICON: Record<string, string> = {
  job_started: "▶", start: "•", llm: "🧠", reasoning: "💭", tool_call: "🔧", tool_result: "↩",
  repair: "⚠", done: "✅", fallback: "🛟", job_finished: "■",
};

function line(e: Ev): string {
  switch (e.type) {
    case "job_started": return "Analiz başladı";
    case "start": return `Kanıt dosyası yüklendi (prompt ${e.prompt_version ?? ""})`;
    case "llm": return `Model düşünüyor (iterasyon ${e.iteration}${e.tools_offered ? "" : ", son cevap"})`;
    case "reasoning": return String(e.text ?? "");
    case "tool_call": return `${e.tool}(${e.args})`;
    case "tool_result": return String(e.summary ?? "");
    case "repair": return `Şema hatası, düzeltme isteniyor: ${JSON.stringify(e.errors)}`;
    case "done": return `Tamamlandı → ${String(e.overall_risk).toUpperCase()}${e.cached ? " (önbellek)" : ""}`;
    case "fallback": return `Kural tabanlı sonuca düşüldü: ${e.reason}`;
    case "job_finished": return `İş bitti (${e.status}, ${e.duration_s ?? "?"} sn)`;
    default: return JSON.stringify(e);
  }
}

export default function AgentTrace({ eventsUrl, onFinished }: { eventsUrl: string; onFinished: () => void }) {
  const [events, setEvents] = useState<Ev[]>([]);
  const box = useRef<HTMLDivElement>(null);
  const done = useRef(onFinished);
  done.current = onFinished;

  useEffect(() => {
    const es = new EventSource(rel(eventsUrl));
    const types = Object.keys(ICON);
    const handler = (m: MessageEvent) => {
      const e = JSON.parse(m.data) as Ev;
      setEvents((prev) => (prev.some((p) => p.id === e.id) ? prev : [...prev, e]));
      if (e.type === "job_finished") { es.close(); done.current(); }
    };
    types.forEach((t) => es.addEventListener(t, handler as EventListener));
    return () => es.close();
  }, [eventsUrl]);

  useEffect(() => { box.current?.scrollTo(0, box.current.scrollHeight); }, [events]);

  return (
    <div className="trace" ref={box}>
      {events.length === 0 && <div className="muted">Bağlanıyor…</div>}
      {events.map((e) => (
        <div key={e.id} style={{ color: e.type === "reasoning" ? "#8a9bb0" : e.type === "tool_call" ? "#38bdf8" : undefined }}>
          {ICON[e.type] ?? "·"} {line(e)}
        </div>
      ))}
    </div>
  );
}
