"""Analist Asistanı (chatbot): veriyi sorgular, cevap verir ve UI aksiyonları üretir.

Analiz agent'ından farkı: kullanıcının neyi soracağı önceden bilinmediği için burada veri GETİREN araçlar vardır
(deterministik okuma). UI aksiyon araçları bir şey hesaplamaz; ön yüzün uygulayacağı komutları kaydeder.
"""

from __future__ import annotations

import json
from typing import Literal

from backend.config import settings
from backend.engine import pipeline
from backend.engine.agent.tools import ToolSpec, invoke, spec_of
from backend.engine.agent.tools.area_tools import vehicles_in_area
from backend.engine.agent.tools.movement_tools import co_movement
from backend.engine.analysis.consistency import check_report, get_context, report_status
from backend.engine.geo.zones import nearest_zone
from backend.engine.llm.prompt_loader import render
from backend.engine.models import parse_hhmm

LEVELS = ["critical", "high", "medium", "low"]
Level = Literal["critical", "high", "medium", "low"]


def _vehicle_levels(image_id: str) -> list[dict]:
    """Görüntünün araçları, geçerli risk seviyesiyle (agent varsa agent, yoksa kural)."""
    d = pipeline.build_dossier(image_id)
    a = pipeline.load_assessment(image_id)
    agent = {v["vehicle_id"]: v for v in (a["vehicles"] if a and pipeline.is_current(a) else [])}
    out = []
    for v in d.vehicles:
        k = v.kinematics
        av = agent.get(v.vehicle_id)
        out.append({
            "vehicle_id": v.vehicle_id, "track_id": v.track_id, "label": v.label,
            "risk": av["risk_level"] if av else v.baseline_risk.level.value,
            "dist_to_base_m": round(v.dist_to_base_m),
            "consistent_approach": bool(k and k.consistent_approach),
            "circling": f"{k.circling_window}, ~{k.circling_radius_m:.0f} m" if k and k.circling else None,
            "motion": k.motion if k else "parked", "eta_min": k.eta_min if k else None,
            "why": (av["rationale"] if av else "; ".join(f.detail for f in v.baseline_risk.factors))[:220],
        })
    return out


# ---------------------------------------------------------------- veri araçları

def find_alerts(min_risk: Level = "high", zone: str | None = None, time_from: str | None = None,
                time_to: str | None = None, consistent_approach_only: bool = False, circling_only: bool = False,
                limit: int = 10) -> dict:
    """Riskli araçları (tüm olaylarda) önem sırasıyla listeler. "Tutarlı yaklaşan araçlar" sorulursa
    consistent_approach_only=true, "üssün etrafında dönen araçlar" sorulursa circling_only=true ver; ikisinde de
    min_risk="low" ver (risk seviyesinden bağımsız hepsi gelsin).

    Args:
        min_risk: En düşük risk seviyesi.
        zone: İsteğe bağlı bölge adı (örn. "Dogu Yolu").
        time_from: İsteğe bağlı başlangıç "HH:MM" (çekim saati).
        time_to: İsteğe bağlı bitiş "HH:MM".
        consistent_approach_only: Yalnızca 2 saat boyunca her hareketinde üsse yaklaşan araçlar.
        circling_only: Yalnızca üssün etrafında sabit yarıçapta tur atan araçlar.
        limit: En fazla kaç sonuç (varsayılan 10).
    """
    repo = get_context().repo
    t0 = parse_hhmm(time_from) if time_from else 0
    t1 = parse_hhmm(time_to) if time_to else 24 * 60
    rows = []
    for img in repo.images():
        if not t0 <= img.capture_min <= t1:
            continue
        for v in _vehicle_levels(img.id):
            if LEVELS.index(v["risk"]) > LEVELS.index(min_risk):
                continue
            if consistent_approach_only and not v["consistent_approach"]:
                continue
            if circling_only and not v["circling"]:
                continue
            if zone and nearest_zone(*img.center, repo.zones)[0].name != zone:
                continue
            rows.append({**v, "image_id": img.id, "time": img.capture_time})
    rows.sort(key=lambda r: (LEVELS.index(r["risk"]), r["dist_to_base_m"]))
    return {"total": len(rows), "items": rows[:max(1, min(limit, 25))]}


def get_event(image_id: str) -> dict:
    """Bir olayın (drone görüntüsü) özeti: agent değerlendirmesi, riskli araçlar, raporlar ve anomaliler.

    Args:
        image_id: Görüntü kimliği, örn. "img_000860".
    """
    d = pipeline.build_dossier(image_id)
    a = pipeline.load_assessment(image_id)
    return {
        "image_id": image_id, "time": d.capture_time, "zone": d.zone, "dist_to_base_m": round(d.dist_to_base_m),
        "overall_risk": a["overall_risk"] if a else d.max_risk.value,
        "summary": a["summary"] if a else None,
        "vehicles": [v for v in _vehicle_levels(image_id) if v["risk"] in ("critical", "high", "medium")][:8],
        "reports": [{"id": r.report_id, "time": r.time, "text": r.text,
                     "checks": [f"{c.claim_type.value}={c.status.value}" for c in r.checks]} for r in d.reports],
        "anomalies": [a_.detail[:200] for a_ in d.anomalies],
    }


def get_vehicle(track_id: str) -> dict:
    """Bir aracın (track) 2 saatlik hareket özeti, riski ve hakkındaki rapor iddiaları.

    Args:
        track_id: Track kimliği, örn. "T0122".
    """
    ctx = get_context()
    tr = ctx.repo.track(track_id)
    k = ctx.kinematics[track_id]
    d = pipeline.build_dossier(tr.image_id)
    v = next((x for x in d.vehicles if x.track_id == track_id), None)
    lv = next((x for x in _vehicle_levels(tr.image_id) if x["track_id"] == track_id), None)
    return {
        "track_id": track_id, "image_id": tr.image_id, "label": ctx.label_of_track(track_id),
        "risk": lv["risk"] if lv else None, "why": lv["why"] if lv else None,
        "dist_to_base": {"start_m": round(k.dist_to_base_start_m), "end_m": round(k.dist_to_base_m)},
        "motion": k.motion, "moves": k.moves, "approach_moves": k.approach_moves, "recede_moves": k.recede_moves,
        "consistent_approach": k.consistent_approach,
        "circling": f"{k.circling_window}, ~{k.circling_radius_m:.0f} m" if k.circling else None,
        "min_dist_to_base_m": round(k.min_dist_to_base_m), "stationary_min": k.stationary_min, "eta_min": k.eta_min,
        "segments": [f"{s.start}-{s.end} {s.kind} {s.radial_change_m:+.0f}m" for s in k.segments],
        "claims": [f"{c.report_id} {c.claim_type.value}={c.status.value}: {c.reason[:120]}" for c in (v.claims if v else ())],
    }


def find_reports(status: Literal["verified", "partial", "contradicted", "unverifiable"] | None = None,
                 zone: str | None = None, source: Literal["official", "third_party"] | None = None,
                 category: Literal["coordinate", "zone", "general"] | None = None, limit: int = 15) -> dict:
    """Saha raporlarını doğrulama sonucuyla arar ve kaynak × sonuç sayımlarını döner.

    Args:
        status: Doğruluk sonucu filtresi.
        zone: Bölge adı filtresi.
        source: Kaynak filtresi.
        category: Rapor kategorisi filtresi.
        limit: En fazla kaç rapor (varsayılan 15).
    """
    ctx = get_context()
    rows, counts = [], {}
    for r in ctx.repo.reports():
        c, links = ctx.claims[r.id], ctx.links[r.id]
        st = report_status(check_report(ctx, r)).value
        if (status and st != status) or (source and r.source.value != source) or (category and c.category != category):
            continue
        if zone and links.zone != zone:
            continue
        key = f"{r.source.value}/{st}"
        counts[key] = counts.get(key, 0) + 1
        rows.append({"id": r.id, "time": r.time, "source": r.source.value, "status": st, "text": r.text,
                     "images": [i.image_id for i in links.images]})
    return {"total": len(rows), "counts": counts, "items": rows[:max(1, min(limit, 30))]}


def zone_activity(zone: str, time: str) -> dict:
    """Bir bölgede belirli bir anda kaydı olan araçlar (tip, üsse uzaklık, tutarlı yaklaşma).

    Args:
        zone: Bölge adı, örn. "Kuzeydogu Kavsagi".
        time: Saat "HH:MM".
    """
    ctx = get_context()
    t = parse_hhmm(time)
    rows = []
    for tr, p in ctx.repo.tracks_active_at(t):
        if nearest_zone(p.lat, p.lon, ctx.repo.zones)[0].name != zone:
            continue
        rows.append({"track_id": tr.id, "label": ctx.label_of_track(tr.id), "image_id": tr.image_id,
                     "consistent_approach": ctx.kinematics[tr.id].consistent_approach})
    heavy = sum(r["label"] in ("truck", "bus") for r in rows)
    return {"zone": zone, "time": time, "vehicles": len(rows), "heavy": heavy, "items": rows[:25]}


# ---------------------------------------------------------------- UI aksiyonları

def ui_open_event(image_id: str, vehicle_id: str | None = None) -> dict:
    """Ekranda bir olayı açar (harita + detay), isteğe bağlı olarak bir aracı seçer.

    Args:
        image_id: Açılacak görüntü.
        vehicle_id: Seçilecek araç: tespit kimliği ya da "track:T0057".
    """
    get_context().repo.image(image_id)
    return {"action": "open_event", "image_id": image_id, "vehicle_id": vehicle_id}


def ui_play_track(track_id: str) -> dict:
    """Aracın olayını açar ve 2 saatlik hareketini haritada baştan oynatır.

    Args:
        track_id: Oynatılacak track, örn. "T0122".
    """
    tr = get_context().repo.track(track_id)
    return {"action": "play_track", "image_id": tr.image_id, "track_id": track_id}


def ui_focus_report(report_id: str) -> dict:
    """Bir raporu haritada gösterir: rapor saatine gider, anlattığı araca çizgi çeker ya da bölgeyi vurgular.

    Args:
        report_id: Rapor kimliği, örn. "R092".
    """
    ctx = get_context()
    ctx.repo.report(report_id)
    images = [i.image_id for i in ctx.links[report_id].images]
    if not images:
        return {"error": "bu raporun bağlı olduğu bir olay yok (genel duyuru)"}
    return {"action": "focus_report", "image_id": images[0], "report_id": report_id}


def ui_highlight_tracks(track_ids: list[str], title: str | None = None) -> dict:
    """Birden fazla aracın (farklı olaylarda olabilir) 2 saatlik izini haritada birlikte vurgular.
    "X'leri haritada göster", "tutarlı yaklaşanları göster" gibi isteklerde kullan.

    Args:
        track_ids: Vurgulanacak track kimlikleri (en fazla 12), örn. ["T0122", "T0020"].
        title: Haritada gösterilecek kısa başlık.
    """
    repo = get_context().repo
    ids = list(dict.fromkeys(track_ids))[:12]
    for t in ids:
        repo.track(t)
    return {"action": "highlight_tracks", "track_ids": ids, "title": title}


def ui_show_reports(status: Literal["verified", "partial", "contradicted", "unverifiable"] | None = None) -> dict:
    """Rapor doğrulama tablosunu açar (isteğe bağlı sonuç filtresiyle).

    Args:
        status: Gösterilecek doğruluk sonucu.
    """
    return {"action": "show_reports", "status": status}


REGISTRY: dict[str, ToolSpec] = {s.name: s for s in map(spec_of, [
    find_alerts, get_event, get_vehicle, find_reports, zone_activity, vehicles_in_area, co_movement,
    ui_open_event, ui_play_track, ui_focus_report, ui_highlight_tracks, ui_show_reports,
])}
_ACTIONS = {"ui_open_event", "ui_play_track", "ui_focus_report", "ui_highlight_tracks", "ui_show_reports"}
_MAX_ITERATIONS = 6        # son iterasyonda tool sunulmaz → model cevap vermek zorunda
_MAX_TOOL_CALLS = 8        # tek soru için toplam tool çağrısı üst sınırı (sonsuz döngü / bütçe koruması)


def chat(messages: list[dict], context: dict | None = None, client=None) -> dict:
    """messages: [{"role": "user"|"assistant", "content": str}, ...] → {"reply", "actions", "tools"}"""
    if client is None:
        from backend.engine.llm.client import get_client
        client = get_client()
    ctx_text = json.dumps(context or {}, ensure_ascii=False)
    history = [{"role": m["role"], "content": str(m["content"])[:4000]}
               for m in messages[-12:] if m.get("role") in ("user", "assistant")]
    convo = [{"role": "system", "content": render("chat_system", screen_context=ctx_text).text}] + history
    tools = [s.schema() for s in REGISTRY.values()]
    actions, used = [], []
    for i in range(_MAX_ITERATIONS):
        last = i == _MAX_ITERATIONS - 1 or len(used) >= _MAX_TOOL_CALLS
        res = client.chat(convo, tools=None if last else tools, reasoning_effort="low", max_tokens=6000,
                          purpose="chat")
        if not res.tool_calls:
            return {"reply": res.content.strip() or "…", "actions": actions, "tools": used}
        convo.append(res.assistant_message())
        for call in res.tool_calls:
            if len(used) >= _MAX_TOOL_CALLS:
                out = {"error": "tool sınırı doldu; eldeki bilgiyle cevap ver"}
                convo.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(out, ensure_ascii=False)})
                continue
            out = invoke(REGISTRY, call.name, call.arguments)
            used.append(call.name)
            if call.name in _ACTIONS and "error" not in out:
                actions.append(out)
            convo.append({"role": "tool", "tool_call_id": call.id,
                          "content": json.dumps(out, ensure_ascii=False)[:6000]})
    return {"reply": "Soruyu yanıtlarken araç sınırına ulaştım; daha dar bir soru sorabilir misin?",
            "actions": actions, "tools": used}
