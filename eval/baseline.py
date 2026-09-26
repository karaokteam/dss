"""
Sahibi : Kişi 4
Görev  : LLM'siz, kural tabanlı rapor hükmü — yalnızca değerlendirme için referans çizgi

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    baseline_verdicts(pack, D) -> list[ReportVerdict]

Kanıt paketine GİRMEZ: LLM'in önüne konursa LLM onu kopyalar. Amaç, "LLM kural tabanına göre
ne kadar iyi?" sorusunu run_eval ile sayıya dökmek.
"""
from dss.evidence.builder import Data
from dss.reports.claims import Claim, norm, parse_claim
from dss.reports.trace import ReportTrace, trace_for
from dss.schemas import EvidencePack, ReportEv, ReportVerdict

STILL_M = 25          # bu kadar oynayan araç "duruyor" sayılır
MOVED_M = 100         # bundan fazla oynayan araç "hareket etti" sayılır
TREND_M = 300         # 30 dk'da üsse yaklaşma/uzaklaşma eşiği
FULL_COVERAGE = 0.9   # iddia edilen sürenin bu kadarı kapsanıyorsa tam doğrulama
CONF_OK = 0.5
HEAVY = {"truck", "bus"}


def _label(pack: EvidencePack, tr: ReportTrace) -> tuple[str | None, float]:
    det = next((d for d in pack.detections if d.det_id == tr.target_det), None)
    if det:
        return det.label, det.conf
    f = next((f for f in tr.followed_tracks if f.track_id == tr.target_track and f.label_at_capture), None)
    return (f.label_at_capture, 1.0) if f else (None, 0.0)


def _class_ok(claimed: str | None, seen: str | None) -> bool | None:
    if claimed is None or seen is None:
        return None
    return seen in HEAVY if claimed == "heavy" else seen == claimed


def _status(c: Claim, r: ReportEv, tr: ReportTrace | None, pack: EvidencePack) -> str:
    if c.category == "gurultu":
        return "DOGRULANAMADI" if "telsiz" in norm(r.text) else "ILGISIZ"
    if tr is None or c.category in ("bolge_olumsuz", "olagan_yogunluk"):
        return "DOGRULANAMADI"
    if not tr.target_track and not tr.target_det and not tr.followed_tracks:
        return "CELISIYOR" if c.coord_decimals == 5 else "DOGRULANAMADI"

    label, conf = _label(pack, tr)
    cls = _class_ok(c.vehicle_class, label)
    if cls is False and conf >= CONF_OK:
        return "CELISIYOR"
    approach, moved = tr.target_approach_30m_before_report_m, tr.target_moved_30m_before_report_m

    if c.category == "dost_kimlik":
        if c.motion != "usse_yaklasiyor" or approach is None:
            return "DOGRULANAMADI"
        return "KISMEN_DOGRULANDI" if approach >= TREND_M else "CELISIYOR"
    if c.category == "hareketsizlik":
        if tr.duration_max_move_m is not None:
            if tr.duration_max_move_m > MOVED_M:
                return "CELISIYOR"
            if tr.duration_max_move_m <= STILL_M:
                full = tr.duration_covered_min >= FULL_COVERAGE * (tr.claimed_duration_min or 0)
                return "DOGRULANDI" if full else "KISMEN_DOGRULANDI"
        if moved is not None:
            return "DOGRULANDI" if moved <= STILL_M else "CELISIYOR" if moved > MOVED_M else "KISMEN_DOGRULANDI"
        return "DOGRULANAMADI"
    if c.category == "hareket_yonu" and approach is not None:
        if c.motion == "uzaklasiyor":
            return "DOGRULANDI" if approach <= -TREND_M else "CELISIYOR" if approach >= TREND_M else "KISMEN_DOGRULANDI"
        if c.motion == "usse_yaklasiyor":
            return "DOGRULANDI" if approach >= TREND_M else "CELISIYOR"
        return "DOGRULANDI" if (moved or 0) >= MOVED_M else "CELISIYOR"
    if c.category == "gorulme":
        return "DOGRULANDI" if cls else "DOGRULANAMADI"
    return "DOGRULANAMADI"


def baseline_verdicts(pack: EvidencePack, D: Data) -> list[ReportVerdict]:
    out = []
    for r in pack.reports:
        c = parse_claim(r.text, D.zones)
        tr = trace_for(r, pack.detections, pack.image.image_id, D, c) if r.scope == "koordinat" else None
        status = _status(c, r, tr, pack)
        evidence = [e for e in (tr.target_track, tr.target_det) if e] if tr else []
        if status in ("DOGRULANDI", "CELISIYOR", "KISMEN_DOGRULANDI") and not evidence:
            evidence = [r.report_id]  # yokluk kanıtının kimliği yok (hayalet rapor)
        out.append(ReportVerdict(report_id=r.report_id, category=c.category or "gurultu",
                                 claim=r.text, status=status, reason="kural tabanı",
                                 evidence=evidence, risk_effect="etkisiz"))
    return out
