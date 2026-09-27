import { Fragment, useEffect, useMemo, useState } from "react";
import { api, type Report } from "../api";
import { CLAIM_TR, STATUS_COLOR, STATUS_TR } from "../risk";

const STATUSES = ["contradicted", "partial", "verified", "unverifiable"];

export default function Reports({ initialStatus = "" }: { initialStatus?: string }) {
  const [items, setItems] = useState<Report[]>([]);
  const [status, setStatus] = useState(initialStatus);
  const [source, setSource] = useState("");
  const [category, setCategory] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => { api.reports().then((r) => setItems(r.items)); }, []);

  const rows = useMemo(() => items.filter((r) =>
    (!status || r.status === status) && (!source || r.source === source) && (!category || r.category === category)), [items, status, source, category]);

  // Kaynağa göre doğrulama dağılımı (yalnızca koordinatlı raporlar — gözlemle sınanabilenler)
  const matrix = useMemo(() => {
    const m: Record<string, Record<string, number>> = {};
    items.filter((r) => r.category === "coordinate").forEach((r) => {
      m[r.source] ??= {};
      m[r.source][r.status] = (m[r.source][r.status] ?? 0) + 1;
    });
    return m;
  }, [items]);

  return (
    <div className="page">
      <div className="flex gap-6 flex-wrap mb-4">
        <div>
          <h2 className="text-lg font-bold mb-1">Saha raporları — gözlemle doğrulama</h2>
          <div className="muted small max-w-xl">
            Her rapor iddiası, raporun anlattığı araçla (rapor saatindeki track konumu ya da park halindeki tespit) karşılaştırıldı.
            Kanıt hiyerarşisi: tespit &gt; hareket kaydı &gt; rapor.
          </div>
        </div>
        <table style={{ width: "auto" }}>
          <thead><tr><th>Koordinatlı</th>{STATUSES.map((s) => <th key={s}>{STATUS_TR[s]}</th>)}</tr></thead>
          <tbody>
            {Object.entries(matrix).map(([src, c]) => {
              const total = Object.values(c).reduce((a, b) => a + b, 0);
              return (
                <tr key={src}><td>{src} ({total})</td>
                  {STATUSES.map((s) => <td key={s} style={{ color: STATUS_COLOR[s] }}>{c[s] ?? 0} <span className="muted small">%{Math.round(100 * (c[s] ?? 0) / total)}</span></td>)}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex gap-2 mb-3 items-center">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">tüm durumlar</option>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_TR[s]}</option>)}
        </select>
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">tüm kaynaklar</option><option value="official">official</option><option value="third_party">third_party</option>
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">tüm kategoriler</option><option value="coordinate">koordinatlı</option><option value="zone">bölge</option><option value="general">genel</option>
        </select>
        <span className="muted small">{rows.length} rapor</span>
      </div>

      <table>
        <thead><tr><th>ID</th><th>Saat</th><th>Kaynak</th><th>Rapor</th><th>İddia</th><th>Sonuç</th><th>Görüntü</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <Fragment key={r.id}>
              <tr onClick={() => setOpen(open === r.id ? null : r.id)} style={{ cursor: "pointer" }}>
                <td><b>{r.id}</b></td>
                <td>{r.time}</td>
                <td className="muted">{r.source}</td>
                <td>{r.text}</td>
                <td className="muted small">{r.claim.claim_types.map((t) => CLAIM_TR[t] ?? t).join(", ")}{r.claim.friendly && " · dost iddiası"}</td>
                <td><span className="badge" style={{ background: STATUS_COLOR[r.status] }}>{STATUS_TR[r.status]}</span></td>
                <td>{r.links.images.map((i) => <a key={i} href={`#/image/${i}`} onClick={(e) => e.stopPropagation()}>{i} </a>)}</td>
              </tr>
              {open === r.id && (
                <tr><td colSpan={7}>
                  {r.checks.map((c, i) => (
                    <div key={i} className="small mb-1">
                      <span className="badge" style={{ background: STATUS_COLOR[c.status] }}>{STATUS_TR[c.status]}</span>{" "}
                      <b>{CLAIM_TR[c.claim_type] ?? c.claim_type}:</b> <span className="muted">{c.reason}</span>
                    </div>
                  ))}
                </td></tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
