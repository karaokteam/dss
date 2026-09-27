"""Agent mesajlarını kurar: system prompt (backend/prompts/agent_system.md) + kompakt kanıt dosyası.

Kanıt dosyasının JSON'u ~25 KB; burada agent'ın karar için ihtiyaç duyduğu alanlar okunur bir metne sıkıştırılır.
"""

from __future__ import annotations

from backend.config import settings
from backend.engine.agent.schemas import OUTPUT_SCHEMA_TEXT
from backend.engine.llm.prompt_loader import Prompt, render
from backend.engine.models import ClaimCheck, ImageDossier, Kinematics, ReportSummary, VehicleEvidence

_STATUS_TR = {"verified": "DOĞRULANDI", "partial": "KISMEN", "contradicted": "ÇELİŞKİLİ",
              "unverifiable": "DOĞRULANAMAZ"}
_MOTION_TR = {"approaching": "yaklaşıyor", "receding": "uzaklaşıyor", "lateral": "yanal", "stationary": "duruyor"}


def system_prompt() -> Prompt:
    return render("agent_system", max_tool_calls=settings.agent.max_tool_calls,
                  output_schema=OUTPUT_SCHEMA_TEXT)


def build_messages(dossier: ImageDossier) -> tuple[list[dict], Prompt]:
    prompt = system_prompt()
    return [{"role": "system", "content": prompt.text},
            {"role": "user", "content": dossier_text(dossier)}], prompt


def repair_message(errors: list[str]) -> dict:
    return {"role": "user", "content": (
        "Çıktın şema doğrulamasından geçmedi:\n- " + "\n- ".join(errors[:15])
        + "\nHataları düzeltip YALNIZCA düzeltilmiş JSON nesnesini döndür.")}


# ---------------------------------------------------------------- kanıt dosyası → metin

def dossier_text(d: ImageDossier) -> str:
    lines = [
        f"GÖRÜNTÜ {d.image_id} | çekim {d.capture_time} | bölge {d.zone} | üsse {d.dist_to_base_m:.0f} m | "
        f"alan {d.footprint_m[0]:.0f}×{d.footprint_m[1]:.0f} m | temel en yüksek risk: {d.max_risk.value}",
        "",
        _global_text(d.global_context),
        "",
        f"ARAÇLAR ({len(d.vehicles)}, temel riske göre sıralı):",
    ]
    for v in d.vehicles:
        lines += _vehicle_text(v)

    lines += ["", "RAPORLAR (bu görüntüye bağlı):"]
    lines += [_report_text(r) for r in d.reports] or ["- yok"]
    lines += ["", "BAĞLAM RAPORLARI (bölge / genel duyuru):"]
    lines += [_report_text(r) for r in d.context_reports] or ["- yok"]
    lines += ["", "ANOMALİLER:"]
    lines += [f"- [{a.type}] {a.detail}" for a in d.anomalies] or ["- yok"]
    lines += ["", "Bu görüntüyü değerlendir. Gerekirse tool kullan, sonunda yalnızca şemaya uygun JSON döndür."]
    return "\n".join(lines)


def _global_text(g: dict) -> str:
    if not g:
        return "GENEL TABLO: yok"
    zones = "; ".join(f"{z}: {info['count']} araç ({info['heavy']} ağır, en yakın {info['closest_m']} m; "
                      f"{', '.join(info['tracks'])})" for z, info in g["by_zone"].items())
    return (f"GENEL TABLO ({g['time']} itibarıyla tüm bölgelerde üsse tutarlı yaklaşan araçlar): "
            f"{g['consistent_approachers']}" + (f" — {zones}" if zones else ""))


def _kin_text(k: Kinematics) -> str:
    parts = [f"{_MOTION_TR.get(k.motion, k.motion)}",
             f"üsse {k.dist_to_base_start_m:.0f}→{k.dist_to_base_m:.0f} m (2 sa)"]
    if k.radial_change_window_m is not None:
        parts.append(f"son 60 dk Δ{k.radial_change_window_m:+.0f} m")
    if k.stationary_min:
        parts.append(f"{k.stationary_min} dk duruyor")
    parts.append(f"{k.moves} hareket ({k.approach_moves} yaklaşan/{k.recede_moves} uzaklaşan)")
    if k.consistent_approach:
        parts.append("TUTARLI YAKLAŞMA")
    if k.eta_min is not None:
        parts.append(f"ETA {k.eta_min:.0f} dk")
    if k.tortuosity:
        parts.append(f"dolaşma {k.tortuosity:.1f}")
    if k.heading_to_base_diff_deg is not None and k.moves:
        parts.append(f"son hareket üsse {k.heading_to_base_diff_deg:.0f}° açıyla")
    return ", ".join(parts)


def _vehicle_text(v: VehicleEvidence) -> list[str]:
    r = v.baseline_risk
    what = f"{v.label} {v.confidence:.2f}" if v.label else "tespit yok"
    if v.alt_labels:
        what += " (alt: " + ", ".join(f"{a.label} {a.confidence:.2f}" for a in v.alt_labels) + ")"
    head = (f"- {v.vehicle_id} | {what} | track {v.track_id or '-'} | üsse {v.dist_to_base_m:.0f} m | "
            f"TEMEL {r.score} {r.level.value}")
    lines = [head]
    if v.kinematics:
        lines.append(f"    hareket: {_kin_text(v.kinematics)}")
    elif "parked" in v.flags:
        lines.append("    hareket: track yok (park halinde / hareket kaydı yok)")
    if r.factors:
        lines.append("    faktörler: " + "; ".join(f"{f.name}({f.weight:+d}): {f.detail}" for f in r.factors))
    if v.flags:
        lines.append("    bayraklar: " + ", ".join(v.flags))
    if v.candidates:
        lines.append("    eşik altı aday: " + ", ".join(f"{c.label} {c.confidence:.2f}" for c in v.candidates))
    for c in v.claims:
        lines.append(f"    iddia {_claim_text(c)}")
    return lines


def _claim_text(c: ClaimCheck) -> str:
    return (f"{c.report_id} ({c.time}, {c.source}) {c.claim_type.value}: "
            f"{_STATUS_TR.get(c.status.value, c.status.value)} — {c.reason}")


def _report_text(r: ReportSummary) -> str:
    checks = "; ".join(f"{c.claim_type.value}={_STATUS_TR.get(c.status.value, c.status.value)}" for c in r.checks)
    return f"- {r.report_id} {r.time} {r.source}: \"{r.text}\" → {checks or '-'}"
