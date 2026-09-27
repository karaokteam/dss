"""Rapor iddialarını gözlemle karşılaştırır → ClaimCheck (verified / partial / contradicted / unverifiable).

Kanıt hiyerarşisi: tespit > track > rapor. Rapor, gözlemle doğrulandığı ölçüde ağırlık alır.

"Özne" = raporun anlattığı olası araç:
  - tracked: rapor saatinde koordinata ≤ track_close_m olan track (+ çekimde eşleştiği tespit)
  - parked : bağlı görüntüde koordinata ≤ track_close_m olan, track'i olmayan ve güveni ≥ low_confidence
             tespit (park halinde kabul edilir; düşük güvenli track'siz tespitler yanlış pozitif olabilir)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from backend.config import settings
from backend.engine.data.repository import Repository, get_repository
from backend.engine.fusion.kinematics import compute_kinematics, track_state_at
from backend.engine.fusion.matcher import match_all
from backend.engine.geo.geometry import dist_to_base_m, distance_m
from backend.engine.geo.zones import nearest_zone
from backend.engine.models import (
    Claim, ClaimCheck, ClaimStatus, ClaimType, Detection, ImageMatch, Kinematics, Report,
    ReportLinks, Subject,
)
from backend.engine.reports.claim_parser import load_claims, parse_all
from backend.engine.reports.linker import link_all

S = ClaimStatus
HEAVY = {"truck", "bus"}


# ---------------------------------------------------------------- kanıt bağlamı

@dataclass
class EvidenceContext:
    repo: Repository
    matches: dict[str, ImageMatch]
    track_det: dict[str, str]                 # track → eşleştiği tespit
    det_track: dict[str, str]
    kinematics: dict[str, Kinematics]         # track → çekim anındaki kinematik
    claims: dict[str, Claim]
    links: dict[str, ReportLinks]

    def label_of_track(self, track_id: str) -> str | None:
        det = self.track_det.get(track_id)
        return self.repo.detection(det).label if det else None


def build_context(repo: Repository | None = None, claims: dict[str, Claim] | None = None) -> EvidenceContext:
    repo = repo or get_repository()
    matches = match_all(repo)
    track_det = {m.track_id: m.detection_id for im in matches.values() for m in im.matches}
    if claims is None:
        # LLM ile üretilmiş claims.json varsa onu, yoksa kural parser'ı kullan (Katman 1 LLM'siz çalışır)
        claims = load_claims() or parse_all(repo.reports(), repo.zones, mode="rules")
    return EvidenceContext(
        repo=repo, matches=matches, track_det=track_det,
        det_track={d: t for t, d in track_det.items()},
        kinematics={t.id: compute_kinematics(t, repo.base) for t in repo.tracks()},
        claims=claims, links=link_all(repo, claims),
    )


@lru_cache(maxsize=1)
def get_context() -> EvidenceContext:
    return build_context()


# ---------------------------------------------------------------- tip uyumu

def type_compatible(claimed: str | None, det: Detection | None) -> bool | None:
    """İddia edilen tip tespitle uyumlu mu? Tespit yoksa / iddia tip belirtmiyorsa None."""
    if claimed in (None, "vehicle") or det is None:
        return None
    labels = {det.label} | {a.label for a in det.alt_labels}
    wanted = HEAVY if claimed == "heavy" else {claimed}
    return bool(labels & wanted) if claimed != "heavy" else det.label in HEAVY or bool(labels & HEAVY)


def _label_matches(claimed: str | None, label: str | None) -> bool:
    if claimed in (None, "vehicle"):
        return True
    return label in (HEAVY if claimed == "heavy" else {claimed})


# ---------------------------------------------------------------- özneler

def resolve_subjects(ctx: EvidenceContext, links: ReportLinks) -> list[Subject]:
    close = settings.reports.track_close_m
    subjects = []
    for tl in links.tracks:
        if tl.dist_m > close:
            continue
        det = ctx.track_det.get(tl.track_id)
        subjects.append(Subject(kind="tracked", detection_id=det, track_id=tl.track_id,
                                label=ctx.repo.detection(det).label if det else None, dist_m=tl.dist_m))
    for dl in _parked(ctx, links):
        if dl.dist_m <= close:
            subjects.append(Subject(kind="parked", detection_id=dl.detection_id, track_id=None,
                                    label=dl.label, dist_m=dl.dist_m))
    return subjects


def _parked(ctx: EvidenceContext, links: ReportLinks) -> list:
    """Bağlı tespitlerden track'i olmayan ve yeterince güvenli olanlar."""
    floor = settings.match.low_confidence
    return [d for d in links.detections
            if d.detection_id not in ctx.det_track and ctx.repo.detection(d.detection_id).confidence >= floor]


def _refs(subjects: list[Subject]) -> tuple[str, ...]:
    out = []
    for s in subjects:
        if s.detection_id:
            out.append(f"det:{s.detection_id}")
        if s.track_id:
            out.append(f"track:{s.track_id}")
    return tuple(out)


def _describe(s: Subject) -> str:
    who = s.track_id or s.detection_id
    what = s.label or "etiketsiz"
    return f"{who} ({what}, {'park halinde' if s.kind == 'parked' else 'track'}, {s.dist_m:.0f} m)"


# ---------------------------------------------------------------- dış arayüz

def check_report(ctx: EvidenceContext, report: Report) -> tuple[ClaimCheck, ...]:
    claim, links = ctx.claims[report.id], ctx.links[report.id]
    subjects = resolve_subjects(ctx, links) if claim.category == "coordinate" else []
    checks = []
    for ct in claim.claim_types:
        fn = _CHECKS.get(ct, _check_unverifiable)
        status, reason, observed, extra_refs = fn(ctx, report, claim, links, subjects)
        checks.append(ClaimCheck(
            report_id=report.id, time=report.time, source=report.source.value, claim_type=ct,
            status=status, reason=reason, subjects=tuple(subjects), observed=observed,
            evidence=(f"report:{report.id}",) + _refs(subjects) + tuple(extra_refs),
        ))
    return tuple(checks)


def report_status(checks: tuple[ClaimCheck, ...]) -> ClaimStatus:
    """Raporun bütün iddialarının en kötüsü (çelişki > kısmi > doğrulandı > doğrulanamaz)."""
    order = [S.CONTRADICTED, S.PARTIAL, S.VERIFIED, S.UNVERIFIABLE]
    return min((c.status for c in checks), key=order.index, default=S.UNVERIFIABLE)


# ---------------------------------------------------------------- iddia tipleri

def _no_subject(links: ReportLinks) -> tuple:
    near = f"; en yakın track {links.nearest_track_m:.0f} m" if links.nearest_track_m is not None else ""
    return (S.UNVERIFIABLE,
            f"Rapor saatinde koordinatın {settings.reports.track_close_m:.0f} m yakınında track yok ve "
            f"çekimde orada track'siz araç görülmedi{near}. Anlatılan araç bulunamadı.",
            {"subjects": 0, "nearest_track_m": links.nearest_track_m}, ())


def _check_stationary(ctx, report, claim, links, subjects):
    if not subjects:
        return _no_subject(links)
    required = claim.stationary_min or settings.reports.long_stationary_min
    results = []
    for s in subjects:
        type_ok = _label_matches(claim.vehicle_type, s.label) if s.label else None
        if s.kind == "parked":
            results.append((S.VERIFIED if type_ok is not False else S.PARTIAL, s,
                            f"{_describe(s)}: track'i yok, park halinde"))
            continue
        k = track_state_at(ctx.repo.track(s.track_id), ctx.repo.base, report.t)
        whole = k.stationary_min == k.observed_min and k.observed_min > 0
        if k.stationary_min >= required or whole:
            st = S.VERIFIED if type_ok is not False else S.PARTIAL
            note = (f"kayıt başından ({k.observed_min} dk) beri durağan" if whole and k.stationary_min < required
                    else f"{k.stationary_min} dk durağan")
        elif k.stationary_min > 0:
            st, note = S.PARTIAL, f"yalnızca {k.stationary_min} dk durağan (iddia ≥ {required} dk)"
        else:
            st, note = S.CONTRADICTED, f"rapor saatinde hareket halinde ({k.speed_mps:.1f} m/s)"
        if type_ok is False:
            note += f"; tip uyuşmuyor (iddia {claim.vehicle_type}, tespit {s.label})"
        results.append((st, s, f"{_describe(s)}: {note}"))
    best = _best(results, claim.vehicle_type)
    return best[0], "; ".join(r[2] for r in results), {"required_min": required}, ()


def _check_count(ctx, report, claim, links, subjects):
    if claim.count is None:
        return S.UNVERIFIABLE, "Sayı belirtilmemiş.", {}, ()
    if not subjects:
        return _no_subject(links)
    matching = [s for s in subjects if s.label and _label_matches(claim.vehicle_type, s.label)]
    unlabeled = [s for s in subjects if not s.label]
    observed = len(matching)
    obs = {"claimed": claim.count, "observed": observed, "subjects": len(subjects)}
    kinds = ", ".join(_describe(s) for s in subjects)
    if observed == claim.count:
        return S.VERIFIED, f"İddia {claim.count} {claim.vehicle_type}; gözlenen {observed}: {kinds}.", obs, ()
    if observed == 0 and not unlabeled:
        return (S.CONTRADICTED,
                f"İddia {claim.count} {claim.vehicle_type}; bu tipte araç yok. Yakındakiler: {kinds}.", obs, ())
    return (S.PARTIAL,
            f"İddia {claim.count} {claim.vehicle_type}; gözlenen {observed}"
            f"{f' (+{len(unlabeled)} etiketsiz track)' if unlabeled else ''}: {kinds}.", obs, ())


def _check_motion(ctx, report, claim, links, subjects):
    motion = claim.motion
    if motion in (None, "stationary"):
        return S.UNVERIFIABLE, "Hareket iddiası yok.", {}, ()
    if not subjects:
        return _no_subject(links)
    cfg = settings.kinematics
    results = []
    for s in subjects:
        if s.kind == "parked":
            results.append((S.CONTRADICTED, s, f"{_describe(s)}: hareket kaydı yok, park halinde"))
            continue
        track = ctx.repo.track(s.track_id)
        at = track_state_at(track, ctx.repo.base, report.t)
        end = ctx.kinematics[s.track_id]
        after = end.dist_to_base_m - at.dist_to_base_m          # rapordan çekime üsse uzaklık değişimi
        moved_after = any(seg.kind == "move" and seg.end > report.time for seg in end.segments)
        moving_now = at.state == "moving" or at.stationary_min < cfg.speed_window_min
        if motion == "approaching_base":
            ok = (at.motion == "approaching" and moving_now) or after <= -cfg.approach_net_m
            bad = after >= cfg.approach_net_m or (not moved_after and not moving_now)
            note = f"rapordan çekime üsse uzaklık {after:+.0f} m; rapor anında {at.motion}"
        elif motion == "leaving_area":
            away = distance_m(claim.lat, claim.lon, end.lat, end.lon)
            ok, bad = away > settings.reports.link_radius_m, not moved_after
            note = f"çekimde rapor noktasına {away:.0f} m uzakta"
        elif motion in ("transit", "moving"):
            ok, bad = moving_now or moved_after, not (moving_now or moved_after)
            note = "rapordan sonra hareket etti" if moved_after else "rapordan sonra hareket etmedi"
        else:  # normal_activity
            ok, bad = not end.consistent_approach, end.consistent_approach
            note = "üsse tutarlı yaklaşma var" if bad else "belirgin tehdit hareketi yok"
        st = S.VERIFIED if ok and not bad else S.CONTRADICTED if bad and not ok else S.PARTIAL
        results.append((st, s, f"{_describe(s)}: {note}"))
    best = _best(results, claim.vehicle_type)
    return best[0], "; ".join(r[2] for r in results), {"claimed_motion": motion}, ()


def _check_identity(ctx, report, claim, links, subjects):
    """Dost/ikmal iddiası veriden doğrudan teyit edilemez. Fiziksel ayrıntılar (varlık, tip, hareket) tutarlıysa
    'verified' = 'fiziksel olarak tutarlı'; renk iddiası görsel kontrol gerektirdiğinden en fazla 'partial'."""
    if not subjects:
        st, reason, obs, refs = _no_subject(links)
        return S.CONTRADICTED, "Dost iddiası: " + reason, obs, refs
    typed = [s for s in subjects if s.label]
    type_ok = any(_label_matches(claim.vehicle_type, s.label) for s in typed) if typed else None
    motion_status = None
    if claim.motion and claim.motion != "stationary":
        motion_status = _check_motion(ctx, report, claim, links, subjects)[0]
    problems = []
    if type_ok is False:
        problems.append(f"tip uyuşmuyor (iddia {claim.vehicle_type}, tespit {', '.join(s.label for s in typed)})")
    if motion_status == S.CONTRADICTED:
        problems.append(f"hareket iddiası ({claim.motion}) gözlemle çelişiyor")
    if problems:
        return S.CONTRADICTED, "Dost iddiası şüpheli: " + "; ".join(problems) + ".", {}, ()
    if claim.color:
        return (S.PARTIAL, f"Varlık ve tip tutarlı; '{claim.color}' renk iddiası görsel kontrol gerektirir.",
                {"needs_visual": True}, ())
    if motion_status == S.PARTIAL or type_ok is None:
        return S.PARTIAL, "Dost iddiası kısmen tutarlı; kimlik veriden teyit edilemez.", {}, ()
    return S.VERIFIED, "Varlık, tip ve hareket tutarlı (kimliğin kendisi veriden teyit edilemez).", {}, ()


def _check_density(ctx, report, claim, links, subjects):
    radius = settings.reports.track_link_radius_m
    tracked = [t for t in links.tracks if t.dist_m <= radius]
    parked = _parked(ctx, links)
    observed = len(tracked) + len(parked)
    normal = claim.normal_count
    obs = {"normal": normal, "observed": observed, "radius_m": radius}
    if normal is None:
        return S.UNVERIFIABLE, f"Olağan sayı belirtilmemiş; {radius:.0f} m içinde {observed} araç.", obs, ()
    detail = f"{radius:.0f} m içinde {len(tracked)} track + {len(parked)} park halinde araç = {observed} (olağan {normal})"
    if observed > normal:
        return S.VERIFIED, f"Yoğunluk doğrulandı: {detail}.", obs, ()
    if observed == normal:
        return S.PARTIAL, f"Olağan düzeyde: {detail}.", obs, ()
    return S.CONTRADICTED, f"Olağanın altında: {detail}.", obs, ()


def _check_zone_status(ctx, report, claim, links, subjects):
    status = claim.zone_status
    if status == "no_heavy":
        heavy = []
        for il in links.images:
            heavy += [d.id for d in ctx.repo.detections_for(il.image_id) if d.label in HEAVY]
        heavy_tracks = [t for t in links.zone_tracks if ctx.label_of_track(t) in HEAVY]
        obs = {"heavy_detections": len(heavy), "heavy_tracks": len(heavy_tracks)}
        refs = tuple(f"det:{d}" for d in heavy) + tuple(f"track:{t}" for t in heavy_tracks)
        if heavy or heavy_tracks:
            return (S.CONTRADICTED, f"'{claim.zone}' bölgesinde ağır araç yok deniyor; bölge görüntülerinde "
                    f"{len(heavy)} ağır araç tespiti, rapor saatinde {len(heavy_tracks)} ağır araç track'i var.",
                    obs, refs)
        return S.VERIFIED, f"'{claim.zone}' bölgesinde ağır araç görülmedi.", obs, ()
    if status == "normal":
        approachers = [t for t in links.zone_tracks if ctx.kinematics[t].consistent_approach]
        if approachers:
            return (S.PARTIAL, f"'{claim.zone}' için 'normal' deniyor; bölgede üsse tutarlı yaklaşan "
                    f"{len(approachers)} araç var.", {"consistent_approachers": len(approachers)},
                    tuple(f"track:{t}" for t in approachers))
        return S.VERIFIED, f"'{claim.zone}' bölgesinde üsse tutarlı yaklaşan araç yok.", {}, ()
    return S.UNVERIFIABLE, "Bölge bağlamı (ihbar / iletişim durumu); gözlemle doğrulanamaz.", {}, ()


def _check_unverifiable(ctx, report, claim, links, subjects):
    if claim.blanket_friendly:
        return (S.UNVERIFIABLE, "Konumsuz genel dost duyurusu; hiçbir aracın riskini tek başına düşürmez.",
                {"blanket_friendly": True}, ())
    return S.UNVERIFIABLE, "Genel bilgi; araç/konum iddiası yok.", {}, ()


def _best(results: list, claimed_type: str | None):
    """Birden fazla özne varsa raporun anlattığına en çok benzeyeni (tip uyumlu + en iyi durum) seç."""
    order = [S.VERIFIED, S.PARTIAL, S.CONTRADICTED, S.UNVERIFIABLE]
    return min(results, key=lambda r: (not _label_matches(claimed_type, r[1].label), order.index(r[0])))


_CHECKS = {
    ClaimType.STATIONARY: _check_stationary,
    ClaimType.COUNT: _check_count,
    ClaimType.MOTION: _check_motion,
    ClaimType.IDENTITY: _check_identity,
    ClaimType.DENSITY: _check_density,
    ClaimType.ZONE_STATUS: _check_zone_status,
}
