"""Katman 1 orkestrasyonu: bir görüntü için kanıt dosyası (ImageDossier) üretir. LLM kullanmaz."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import replace
from itertools import combinations

from backend.config import settings
from backend.engine.analysis.consistency import (
    EvidenceContext, _label_matches, check_report, get_context,
)
from backend.engine.analysis.risk import HEAVY, RiskInput, level_for, score
from backend.engine.fusion.kinematics import move_steps, track_state_at
from backend.engine.geo.geometry import bbox_center, dist_to_base_m, distance_m, footprint_size_m, pixel_to_latlon
from backend.engine.geo.zones import nearest_zone
from backend.engine.models import (
    Anomaly, ClaimCheck, ClaimStatus, ImageDossier, ReportSummary, RiskLevel, VehicleEvidence, fmt_hhmm,
)

_LEVEL_ORDER = [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]


def _checks(ctx: EvidenceContext, report_id: str) -> tuple[ClaimCheck, ...]:
    cache = ctx.__dict__.setdefault("_check_cache", {})
    if report_id not in cache:
        cache[report_id] = check_report(ctx, ctx.repo.report(report_id))
    return cache[report_id]


def _summary(ctx: EvidenceContext, report_id: str, with_checks: bool = True) -> ReportSummary:
    r, c = ctx.repo.report(report_id), ctx.claims[report_id]
    return ReportSummary(report_id=r.id, time=r.time, source=r.source.value, text=r.text,
                         claim_types=c.claim_types, checks=_checks(ctx, r.id) if with_checks else ())


def _claims_for_vehicle(ctx: EvidenceContext, report_ids: list[str], det_id: str | None,
                        track_id: str | None) -> tuple[ClaimCheck, ...]:
    """Raporun özneleri arasında bu araç varsa iddialarını bağlar. Tip belirten iddialarda, tip uyumlu özne
    varsa yalnızca onlara bağlanır ("kamyon durağan" iddiası yanındaki otomobile yüklenmez)."""
    out = []
    for rid in report_ids:
        claim = ctx.claims[rid]
        for check in _checks(ctx, rid):
            subjects = check.subjects
            typed = [s for s in subjects if s.label and _label_matches(claim.vehicle_type, s.label)]
            pool = typed or subjects
            if any((det_id and s.detection_id == det_id) or (track_id and s.track_id == track_id) for s in pool):
                out.append(check)
    return tuple(out)


def build_dossier(image_id: str, ctx: EvidenceContext | None = None) -> ImageDossier:
    ctx = ctx or get_context()
    repo = ctx.repo
    img = repo.image(image_id)
    match = ctx.matches[image_id]
    zone = nearest_zone(*img.center, repo.zones)[0].name

    report_ids = [rid for rid, l in ctx.links.items()
                  if ctx.claims[rid].category == "coordinate" and any(il.image_id == image_id for il in l.images)]
    report_ids.sort(key=lambda rid: (repo.report(rid).t, rid))

    # ---- araç adayları: tespitler + görüntü içinde kalan tespitsiz track'ler
    dets = repo.detections_for(image_id)
    confident_heavy = [d for d in dets if d.label in HEAVY and d.confidence >= settings.match.low_confidence]
    vehicles = []
    for det in dets:
        m = next((x for x in match.matches if x.detection_id == det.id), None)
        track_id = m.track_id if m else None
        kin = ctx.kinematics.get(track_id) if track_id else None
        flags = []
        if not track_id:
            flags.append("parked")
        if det.confidence < settings.match.low_confidence:
            flags.append("low_confidence")
        if m and m.alternatives:
            flags.append("ambiguous_match")
        group = sum(distance_m(det.lat, det.lon, h.lat, h.lon) <= settings.risk.group_radius_m
                    for h in confident_heavy) if det.label in HEAVY else 0
        claims = _claims_for_vehicle(ctx, report_ids, det.id, track_id)
        dist = dist_to_base_m(repo.base, det.lat, det.lon)
        risk = score(RiskInput(label=det.label, confidence=det.confidence, has_track=bool(track_id),
                               dist_to_base_m=dist, kinematics=kin, claims=claims, heavy_group_size=group))
        vehicles.append(VehicleEvidence(
            vehicle_id=det.id, label=det.label, confidence=det.confidence, alt_labels=det.alt_labels,
            bbox_xywh=det.bbox_xywh, lat=det.lat, lon=det.lon, dist_to_base_m=round(dist, 1),
            zone=nearest_zone(det.lat, det.lon, repo.zones)[0].name, track_id=track_id,
            match_dist_m=m.dist_m if m else None, kinematics=kin, claims=claims,
            flags=tuple(flags), baseline_risk=risk,
        ))

    anomalies: list[Anomaly] = []
    for ut in match.unmatched_tracks:
        if not ut.in_frame:
            continue
        last = repo.track(ut.track_id).last
        kin = ctx.kinematics[ut.track_id]
        candidates = _missed_candidates(ctx, image_id, last.lat, last.lon)
        claims = _claims_for_vehicle(ctx, report_ids, None, ut.track_id)
        dist = dist_to_base_m(repo.base, last.lat, last.lon)
        risk = score(RiskInput(label=None, confidence=None, has_track=True, dist_to_base_m=dist,
                               kinematics=kin, claims=claims))
        vehicles.append(VehicleEvidence(
            vehicle_id=f"track:{ut.track_id}", label=None, confidence=None, alt_labels=(),
            bbox_xywh=candidates[0].bbox_xywh if candidates else None,
            lat=last.lat, lon=last.lon, dist_to_base_m=round(dist, 1),
            zone=nearest_zone(last.lat, last.lon, repo.zones)[0].name, track_id=ut.track_id,
            match_dist_m=None, kinematics=kin, claims=claims, flags=("possible_missed_detection",),
            baseline_risk=risk, candidates=candidates,
        ))
        cand = (f" Aynı noktada eşik altı ham tahmin var: "
                + ", ".join(f"{c.label} {c.confidence:.2f}" for c in candidates) if candidates
                else " Yakında eşik altı ham tahmin de yok.")
        anomalies.append(Anomaly(
            type="possible_missed_detection",
            detail=f"{ut.track_id} çekim anında görüntü içinde ama eşleşen tespit yok (model kaçırmış olabilir).{cand}",
            evidence=(f"track:{ut.track_id}",)))

    coordinated = _coordination(ctx, [v.track_id for v in vehicles if v.track_id])
    anomalies += coordinated
    in_group = {e.split(":", 1)[1] for a in coordinated for e in a.evidence if e.startswith("track:")}
    vehicles = [_with_flag(v, "coordinated") if v.track_id in in_group else v for v in vehicles]

    vehicles.sort(key=lambda v: (-v.baseline_risk.score, v.vehicle_id))

    # ---- rapor özetleri ve rapor kaynaklı anomaliler
    reports = tuple(_summary(ctx, rid) for rid in report_ids)
    for rs in reports:
        for c in rs.checks:
            if not c.subjects and c.status in (ClaimStatus.UNVERIFIABLE, ClaimStatus.CONTRADICTED) \
                    and ctx.claims[rs.report_id].category == "coordinate":
                anomalies.append(Anomaly(
                    type="claim_without_vehicle",
                    detail=f"{rs.report_id} ({rs.time}) anlattığı aracın izine rastlanmadı: {c.reason}",
                    evidence=(f"report:{rs.report_id}",)))
                break

    context_ids = [rid for rid, l in ctx.links.items()
                   if ctx.claims[rid].category == "zone" and any(il.image_id == image_id for il in l.images)]
    lo, hi = img.capture_min - settings.reports.window_min, img.capture_min
    context_ids += [r.id for r in repo.reports_between(lo, hi) if ctx.claims[r.id].blanket_friendly]
    context = tuple(_summary(ctx, rid) for rid in sorted(set(context_ids), key=lambda x: (repo.report(x).t, x)))
    for rs in context:
        bad = [c for c in rs.checks if c.status in (ClaimStatus.CONTRADICTED, ClaimStatus.PARTIAL)]
        if bad:
            anomalies.append(Anomaly(type="zone_report_mismatch", detail=f"{rs.report_id} ({rs.time}): {bad[0].reason}",
                                     evidence=(f"report:{rs.report_id}",) + bad[0].evidence[1:]))

    counts = defaultdict(int)
    for v in vehicles:
        counts[v.baseline_risk.level.value] += 1
    max_risk = min((v.baseline_risk.level for v in vehicles), key=_LEVEL_ORDER.index, default=RiskLevel.LOW)

    return ImageDossier(
        image_id=image_id, capture_time=img.capture_time, zone=zone, center=img.center,
        dist_to_base_m=round(dist_to_base_m(repo.base, *img.center), 1),
        footprint_m=tuple(round(x, 1) for x in footprint_size_m(img)),
        vehicles=tuple(vehicles), reports=reports, context_reports=context,
        anomalies=tuple(anomalies), max_risk=max_risk,
        risk_counts={lvl.value: counts.get(lvl.value, 0) for lvl in _LEVEL_ORDER},
        global_context=global_context(ctx, img.capture_min),
    )


# ---------------------------------------------------------------- yardımcılar (A4, A5, A6)

def _with_flag(v: VehicleEvidence, flag: str) -> VehicleEvidence:
    return replace(v, flags=v.flags + (flag,))


def _missed_candidates(ctx: EvidenceContext, image_id: str, lat: float, lon: float):
    """Tespitsiz track'in son noktası yakınında, yayınlanan eşiğin altında kalmış ham tahminler."""
    img = ctx.repo.image(image_id)
    cfg = settings.match
    near = []
    for p in ctx.repo.raw_predictions(image_id):
        if p.confidence >= cfg.min_confidence:
            continue   # eşik üstü olanlar zaten tespit listesinde
        plat, plon = pixel_to_latlon(img, *bbox_center(p.bbox_xywh))
        if distance_m(lat, lon, plat, plon) <= cfg.missed_candidate_radius_m:
            near.append(p)
    near.sort(key=lambda p: -p.confidence)
    return tuple(near[:3])


def _coordination(ctx: EvidenceContext, track_ids: list[str]) -> list[Anomaly]:
    """Aynı görüntüdeki araç çiftlerinde konvoy: 2 saat boyunca yakın kalıp birlikte hareket etmek.

    "Ayrı yerlerden aynı anlarda hareketle buluşma" burada kullanılmaz: veride aynı görüntüdeki 580 çiftte
    ≥4 eşzamanlı hareket tesadüfen ~%5 (≈29 çift) beklenir, bulunan 24 → tesadüften ayırt edilemiyor.
    Bu hipotez agent'ın co_movement tool'unda, çoklu karşılaştırma uyarısıyla kalır."""
    cfg, repo = settings.agent, ctx.repo
    moves = {t: move_steps(repo.track(t), repo.base) for t in track_ids}
    out = []
    for a, b in combinations(sorted(track_ids), 2):
        ta, tb = repo.track(a), repo.track(b)
        common = sorted({p.t for p in ta.points} & {p.t for p in tb.points})
        if not common:
            continue
        dists = [distance_m(ta.position_at(t).lat, ta.position_at(t).lon, tb.position_at(t).lat, tb.position_at(t).lon)
                 for t in common]
        sync = sum(1 for t in moves[a] if t in moves[b])
        if max(dists) <= cfg.co_move_radius_m and sync >= cfg.co_move_min_sync:
            out.append(Anomaly(type="convoy", evidence=(f"track:{a}", f"track:{b}"), detail=(
                f"{a} ve {b} 2 saat boyunca ≤ {max(dists):.0f} m arayla, {sync} kez aynı anda hareket etti (konvoy).")))
    return out


def global_context(ctx: EvidenceContext, t: int) -> dict:
    """Çekim anında tüm bölgelerde üsse tutarlı yaklaşan araçlar (yalnızca o ana kadarki kayıtla)."""
    cache = ctx.__dict__.setdefault("_global_cache", {})
    if t in cache:
        return cache[t]
    repo = ctx.repo
    window = settings.kinematics.radial_window_min
    by_zone: dict[str, dict] = {}
    total = 0
    for tr in repo.tracks():
        if tr.start_min > t - window or tr.end_min < t:
            continue
        k = track_state_at(tr, repo.base, t)
        if k is None or not k.consistent_approach:
            continue
        total += 1
        zone = nearest_zone(k.lat, k.lon, repo.zones)[0].name
        z = by_zone.setdefault(zone, {"count": 0, "heavy": 0, "closest_m": None, "tracks": []})
        z["count"] += 1
        z["heavy"] += int(ctx.label_of_track(tr.id) in HEAVY)
        z["closest_m"] = round(min(z["closest_m"] or k.dist_to_base_m, k.dist_to_base_m))
        z["tracks"].append(tr.id)
    cache[t] = {"time": fmt_hhmm(t), "consistent_approachers": total, "by_zone": dict(sorted(by_zone.items()))}
    return cache[t]


def build_all(ctx: EvidenceContext | None = None) -> dict[str, ImageDossier]:
    ctx = ctx or get_context()
    return {img.id: build_dossier(img.id, ctx) for img in ctx.repo.images()}


def save_dossier(dossier: ImageDossier) -> None:
    path = settings.paths.dossiers / f"{dossier.image_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dossier.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
