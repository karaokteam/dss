"""Agent çıktısı (Assessment): şema, doğrulama ve sonlandırma.

Agent yalnızca ÖNEMLİ araçları yazar (temel risk ≥ medium ya da seviyesini değiştirdikleri);
yazılmayan araçlar temel seviyeleriyle sonuca eklenir. Temel seviyeden sapma gerekçe ister.
"""

from __future__ import annotations

import re

from backend.engine.data.repository import get_repository
from backend.engine.models import ImageDossier, RiskLevel

LEVELS = [l.value for l in RiskLevel]                  # critical, high, medium, low
REPORT_VERDICTS = ("reliable", "partly_reliable", "unreliable", "unverifiable")
_REF = re.compile(r"^(det|track|report|image):(.+)$")

OUTPUT_SCHEMA_TEXT = """{
  "overall_risk": "critical" | "high" | "medium" | "low",
  "summary": "1–3 cümle Türkçe özet: bu görüntüde neye dikkat edilmeli, neden",
  "vehicles": [
    {
      "vehicle_id": "kanıt dosyasındaki araç kimliği (örn. img_000267_003 ya da track:T0057)",
      "risk_level": "critical" | "high" | "medium" | "low",
      "override_reason": "risk_level temel seviyeden farklıysa zorunlu gerekçe, aynıysa null",
      "rationale": "Türkçe, sayılarla gerekçe",
      "evidence": ["det:...", "track:...", "report:...", "image:..."]
    }
  ],
  "attention_items": [
    {"title": "kısa başlık", "risk_level": "...", "rationale": "...", "evidence": ["..."]}
  ],
  "report_notes": [
    {"report_id": "R053", "verdict": "reliable" | "partly_reliable" | "unreliable" | "unverifiable", "note": "kısa gerekçe"}
  ]
}"""


_CONSISTENT = re.compile(r"tutarl[ıi]\s+yakla[şs]\w*", re.I)
_NEGATION = re.compile(r"^\W*(işareti\s+)?(yok|değil|degil|olmad|görülmed|gorulmed|bulunm|sayılmaz|sayilmaz)", re.I)


def _claims_consistent_approach(text: str) -> bool:
    """Metin bir aracın 'tutarlı yaklaştığını' OLUMLU olarak iddia ediyor mu? ("... işareti yok" gibi olumsuzlar sayılmaz)"""
    for m in _CONSISTENT.finditer(text):
        after = text[m.end():m.end() + 30]
        before = text[max(0, m.start() - 12):m.start()].lower()
        if _NEGATION.match(after) or "değil" in before or "degil" in before:
            continue
        return True
    return False


def _level_idx(level: str) -> int:
    return LEVELS.index(level)


def _check_refs(refs, where: str, errors: list[str]) -> None:
    repo = get_repository()
    if not isinstance(refs, list) or not refs:
        errors.append(f"{where}.evidence boş olamaz (en az bir kanıt kimliği)")
        return
    for ref in refs:
        m = _REF.match(str(ref))
        if not m:
            errors.append(f"{where}.evidence: '{ref}' biçimi 'det:/track:/report:/image:<id>' olmalı")
            continue
        kind, key = m[1], m[2]
        try:
            {"det": repo.detection, "track": repo.track, "report": repo.report, "image": repo.image}[kind](key)
        except KeyError:
            errors.append(f"{where}.evidence: '{ref}' veride yok")


def validate(raw: dict, dossier: ImageDossier) -> list[str]:
    """Hata listesi (boşsa geçerli)."""
    errors: list[str] = []
    if not isinstance(raw, dict):
        return ["çıktı bir JSON nesnesi olmalı"]
    baseline = {v.vehicle_id: v.baseline_risk.level.value for v in dossier.vehicles}

    overall = raw.get("overall_risk")
    if overall not in LEVELS:
        errors.append(f"overall_risk {LEVELS} içinden olmalı")
    if not str(raw.get("summary") or "").strip():
        errors.append("summary boş olamaz")

    vehicles = raw.get("vehicles")
    if not isinstance(vehicles, list):
        errors.append("vehicles bir liste olmalı")
        vehicles = []
    seen = set()
    for i, v in enumerate(vehicles):
        where = f"vehicles[{i}]"
        if not isinstance(v, dict):
            errors.append(f"{where} nesne olmalı")
            continue
        vid = v.get("vehicle_id")
        if vid not in baseline:
            errors.append(f"{where}.vehicle_id '{vid}' kanıt dosyasında yok")
            continue
        if vid in seen:
            errors.append(f"{where}.vehicle_id '{vid}' tekrar ediyor")
        seen.add(vid)
        level = v.get("risk_level")
        if level not in LEVELS:
            errors.append(f"{where}.risk_level {LEVELS} içinden olmalı")
            continue
        if level != baseline[vid] and not str(v.get("override_reason") or "").strip():
            errors.append(f"{where}: risk_level ({level}) temel seviyeden ({baseline[vid]}) farklı; "
                          "override_reason zorunlu")
        if not str(v.get("rationale") or "").strip():
            errors.append(f"{where}.rationale boş olamaz")
        _check_refs(v.get("evidence"), where, errors)

    # "Tutarlı yaklaşma" yalnızca kanıt dosyasında işaretli araçlar için kullanılabilir (bilinen aşırı yorum)
    consistent = {v.vehicle_id for v in dossier.vehicles if v.kinematics and v.kinematics.consistent_approach}
    for i, v in enumerate(vehicles):
        if isinstance(v, dict) and v.get("vehicle_id") in baseline and v["vehicle_id"] not in consistent:
            text = f"{v.get('rationale', '')} {v.get('override_reason') or ''}"
            if _claims_consistent_approach(text):
                errors.append(f"vehicles[{i}] ({v['vehicle_id']}): kanıt dosyasında TUTARLI YAKLAŞMA işareti yok; "
                              "'tutarlı yaklaşma' deme, 'yaklaşıyor' ve hareket sayılarını kullan")

    # Temel seviyesi ≥ medium olan her araç yazılmalı (önemli araç atlanmasın)
    missing = [vid for vid, lvl in baseline.items()
               if _level_idx(lvl) <= _level_idx("medium") and vid not in seen]
    if missing:
        errors.append(f"temel riski medium ve üstü olan şu araçlar vehicles'ta yok: {missing}")

    for i, a in enumerate(raw.get("attention_items") or []):
        where = f"attention_items[{i}]"
        if not isinstance(a, dict) or not str(a.get("title") or "").strip():
            errors.append(f"{where}.title boş olamaz")
            continue
        if a.get("risk_level") not in LEVELS:
            errors.append(f"{where}.risk_level {LEVELS} içinden olmalı")
        _check_refs(a.get("evidence"), where, errors)

    report_ids = {r.report_id for r in dossier.reports} | {r.report_id for r in dossier.context_reports}
    for i, n in enumerate(raw.get("report_notes") or []):
        where = f"report_notes[{i}]"
        if not isinstance(n, dict) or n.get("report_id") not in report_ids:
            errors.append(f"{where}.report_id kanıt dosyasındaki raporlardan olmalı")
        elif n.get("verdict") not in REPORT_VERDICTS:
            errors.append(f"{where}.verdict {list(REPORT_VERDICTS)} içinden olmalı")

    if overall in LEVELS:
        levels = [v.get("risk_level") for v in vehicles if isinstance(v, dict) and v.get("risk_level") in LEVELS]
        levels += [a.get("risk_level") for a in raw.get("attention_items") or []
                   if isinstance(a, dict) and a.get("risk_level") in LEVELS]
        if levels and _level_idx(overall) > min(_level_idx(l) for l in levels):
            errors.append("overall_risk, araç ve dikkat maddelerindeki en yüksek seviyeden düşük olamaz")
    return errors


def finalize(raw: dict, dossier: ImageDossier, trace: dict) -> dict:
    """Doğrulanmış çıktıyı tam sonuca çevirir: yazılmayan araçlar temel seviyeyle eklenir."""
    by_id = {v["vehicle_id"]: v for v in raw.get("vehicles", [])}
    vehicles = []
    for v in dossier.vehicles:
        base = v.baseline_risk
        if v.vehicle_id in by_id:
            a = by_id[v.vehicle_id]
            vehicles.append({
                "vehicle_id": v.vehicle_id, "label": v.label, "track_id": v.track_id,
                "risk_level": a["risk_level"], "baseline_level": base.level.value, "baseline_score": base.score,
                "override_reason": a.get("override_reason") if a["risk_level"] != base.level.value else None,
                "rationale": a["rationale"], "evidence": a["evidence"], "source": "agent",
            })
        else:
            vehicles.append({
                "vehicle_id": v.vehicle_id, "label": v.label, "track_id": v.track_id,
                "risk_level": base.level.value, "baseline_level": base.level.value, "baseline_score": base.score,
                "override_reason": None,
                "rationale": "; ".join(f.detail for f in base.factors) or "belirgin risk faktörü yok",
                "evidence": [f"det:{v.vehicle_id}"] if not v.vehicle_id.startswith("track:") else [v.vehicle_id],
                "source": "baseline",
            })
    vehicles.sort(key=lambda x: (_level_idx(x["risk_level"]), -x["baseline_score"]))
    return {
        "image_id": dossier.image_id,
        "capture_time": dossier.capture_time,
        "zone": dossier.zone,
        "overall_risk": raw["overall_risk"],
        "summary": raw["summary"],
        "vehicles": vehicles,
        "attention_items": raw.get("attention_items") or [],
        "report_notes": raw.get("report_notes") or [],
        "trace": trace,
    }


def fallback(dossier: ImageDossier, trace: dict, reason: str) -> dict:
    """LLM başarısızsa kural tabanlı sonuç (Katman 1)."""
    top = [v for v in dossier.vehicles if _level_idx(v.baseline_risk.level.value) <= _level_idx("high")]
    summary = ("Kural tabanlı değerlendirme (agent çıktısı doğrulanamadı; ayrıntı trace'te). "
               + (f"{len(top)} araç yüksek/kritik: " + ", ".join(v.vehicle_id for v in top[:5]) + "."
                  if top else "Yüksek riskli araç yok."))
    raw = {"overall_risk": dossier.max_risk.value, "summary": summary, "vehicles": [],
           "attention_items": [{"title": a.type, "risk_level": "medium", "rationale": a.detail,
                                "evidence": list(a.evidence) or [f"image:{dossier.image_id}"]}
                               for a in dossier.anomalies],
           "report_notes": []}
    return finalize(raw, dossier, {**trace, "fallback": True, "fallback_reason": reason})
