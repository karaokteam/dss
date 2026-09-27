import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, MessageSquare, Send, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Analist Asistanı: /api/chat → cevap + UI aksiyonları (window 'dss-action' olayıyla Ops ekranına iletilir)
export interface DssAction { action: string; image_id?: string; vehicle_id?: string | null; track_id?: string; report_id?: string; status?: string | null; track_ids?: string[]; title?: string | null; time?: string }
interface Msg { role: "user" | "assistant"; content: string; actions?: DssAction[] }

// Ops ekranı seçili olay/araç/saat bilgisini buraya yazar (chatbot bağlamı)
export const screenContext: Record<string, unknown> = {};

const SUGGESTIONS = [
  "En kritik 3 tehdit ne?",
  "Bu olayda neye dikkat etmeliyim?",
  "Resmi raporların kaçı çelişkili?",
  "Üsse tutarlı yaklaşan araçları göster",
  "Bir kamyon üsse 1 km'den fazla yaklaşırsa uyar",
];

const ACTION_TR: Record<string, string> = {
  open_event: "olay açıldı", play_track: "iz oynatılıyor", focus_report: "rapor gösteriliyor", show_reports: "rapor tablosu açıldı",
  highlight_tracks: "haritada vurgulandı",
};

export default function ChatPanel() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { box.current?.scrollTo(0, box.current.scrollHeight); }, [msgs, busy]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    const next: Msg[] = [...msgs, { role: "user", content: text.trim() }];
    setMsgs(next); setInput(""); setBusy(true);
    try {
      const r = await fetch("api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next.map(({ role, content }) => ({ role, content })), context: screenContext }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.error?.message || r.statusText);
      setMsgs([...next, { role: "assistant", content: j.reply, actions: j.actions }]);
      (j.actions as DssAction[]).forEach((a) => window.dispatchEvent(new CustomEvent("dss-action", { detail: a })));
    } catch (e) {
      setMsgs([...next, { role: "assistant", content: `Hata: ${e}` }]);
    } finally { setBusy(false); }
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="fixed right-5 bottom-5 z-[2000] !rounded-full !px-4 !py-3 !bg-sky-700 !border-sky-500 shadow-lg shadow-sky-900/50">
        <MessageSquare size={18} className="inline mr-2" />Asistan
      </button>
    );
  }
  return (
    <div className="fixed right-5 bottom-5 z-[2000] w-[400px] h-[560px] flex flex-col rounded-xl border border-slate-700 bg-slate-950/95 shadow-2xl shadow-black">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800">
        <Bot size={16} className="text-sky-400" /><b className="text-sm flex-1">Analist Asistanı</b>
        {msgs.length > 0 && <button className="text-[11px] !py-0.5" onClick={() => setMsgs([])}>temizle</button>}
        <button className="!p-1" onClick={() => setOpen(false)}><X size={14} /></button>
      </div>
      <div ref={box} className="flex-1 overflow-y-auto p-3 space-y-3">
        {msgs.length === 0 && (
          <div className="text-xs text-slate-400">
            Veriye soru sor ya da ekranı yönet: olay aç, iz oynat, raporu haritada göster.
            <div className="mt-3 flex flex-col gap-1.5">
              {SUGGESTIONS.map((s) => <button key={s} className="text-left text-xs" onClick={() => send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div className={`inline-block text-left text-[13px] leading-relaxed rounded-lg px-3 py-2 whitespace-pre-wrap max-w-[92%] ${m.role === "user" ? "bg-sky-800" : "bg-slate-800"}`}>
              {m.role === "assistant" ? <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div> : m.content}
            </div>
            {m.actions?.map((a, j) => (
              <div key={j} className="text-[11px] text-sky-300 mt-1">↳ {ACTION_TR[a.action] ?? a.action} {a.track_ids?.join(", ") ?? a.track_id ?? a.report_id ?? a.image_id ?? ""}</div>
            ))}
          </div>
        ))}
        {busy && <div className="text-xs text-slate-400"><Loader2 size={12} className="inline animate-spin mr-1" />veriye bakıyor…</div>}
      </div>
      <form className="flex gap-2 p-2 border-t border-slate-800" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Örn: T0122 üsse nasıl yaklaştı?"
          className="flex-1 bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm outline-none focus:border-sky-500" />
        <button type="submit" disabled={busy} className="!bg-sky-700"><Send size={14} /></button>
      </form>
    </div>
  );
}
