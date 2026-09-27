"""Rapor iddialarını gözlemle karşılaştırır → ClaimCheck (verified / partial / contradicted / unverifiable).

Kanıt hiyerarşisi: tespit > track > rapor. Rapor, gözlemle doğrulandığı ölçüde ağırlık alır.

Rapor ↔ araç eşleştirmesi (veriden ve görev tanımındaki örnekten):
  Rapor koordinatı, anlatılan aracın GÖRÜNTÜDEKİ (çekim anındaki) konumudur: 5 ondalıklı koordinatların
  31/35'i görüntüdeki araca ≤3 m (medyan 0,4 m); rapor anındaki konuma 0/35. Bu yüzden:
  1. Özne = bağlı görüntüde koordinata tolerans içinde (5 ondalık ≈3 m, 4 ondalık ≈12 m) duran araç.
  2. İddia, o aracın RAPORDAN ÖNCEKİ 30 DAKİKADAKİ davranışıyla değerlendirilir (hareket kaydından).
Kimlik (dost / ikmal) veriden teyit edilemez: en fazla "kısmen"; üsse yaklaşan araca iliştirilmişse
"güven verici iddia yaklaşan araçta" diye işaretlenir ve riski ASLA düşürmez.
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
REASSURING_MOTIONS = ("approaching_base", "leaving_area", "normal_activity")   # riski düşürmeye yönelik iddialar


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


# ---------------------------------------------------------------- özneler (görüntüdeki araçlar)

def _tolerance(claim: Claim) -> float:
    """Koordinat hassasiyetine göre eşleştirme toleransı: 5 ondalık ≈3 m, 4 ondalık ≈12 m."""
    return max(settings.reports.subject_tolerance_min_m, 2 * (claim.coord_precision_m or 0) + 1)


def image_vehicles(ctx: EvidenceContext, image_id: str) -> list[Subject]:
    """Görüntüdeki araçlar: tespitler (track'li ya da park halinde) + görüntü içindeki tespitsiz track'ler.
    dist_m burada 0; çağıran koordinata uzaklığı doldurur."""
    repo, floor = ctx.repo, settings.match.low_confidence
    out = []
    for d in repo.detections_for(image_id):
        tid = ctx.det_track.get(d.id)
        if tid is None and d.confidence < floor:
            continue   # track'siz, düşük güvenli tespit: yanlış pozitif olabilir
        out.append(Subject(kind="tracked" if tid else "parked", detection_id=d.id, track_id=tid,
                           label=d.label, dist_m=0.0))
    for u in ctx.matches[image_id].unmatched_tracks:
        if u.in_frame:
            out.append(Subject(kind="tracked", detection_id=None, track_id=u.track_id, label=None, dist_m=0.0))
    return out


def _position(ctx: EvidenceContext, s: Subject) -> tuple[float, float]:
    if s.detection_id:
        d = ctx.repo.detection(s.detection_id)
        return d.lat, d.lon
    last = ctx.repo.track(s.track_id).last
    return last.lat, last.lon


def resolve_subjects(ctx: EvidenceContext, claim: Claim, links: ReportLinks, radius: float | None = None) -> list[Subject]:
    """Koordinata `radius` (varsayılan: tolerans) içindeki görüntü araçları, uzaklığa göre sıralı."""
    if claim.lat is None or not links.images:
        return []
    radius = _tolerance(claim) if radius is None else radius
    found = []
    for il in links.images:
        for v in image_vehicles(ctx, il.image_id):
            lat, lon = _position(ctx, v)
            d = distance_m(claim.lat, claim.lon, lat, lon)
            if d <= radius:
                found.append(Subject(kind=v.kind, detection_id=v.detection_id, track_id=v.track_id,
                                     label=v.label, dist_m=round(d, 1)))
    return sorted(found, key=lambda x: x.dist_m)


def _primary(subjects: list[Subject], claimed_type: str | None) -> Subject | None:
    """Raporun anlattığı araç: tolerans içindekilerden tip uyumlu en yakın, yoksa en yakın."""
    if not subjects:
        return None
    typed = [s for s in subjects if s.label and _label_matches(claimed_type, s.label)]
    return (typed or subjects)[0]


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
    return f"{who} ({what}{', park halinde' if s.kind == 'parked' else ''})"


# ---------------------------------------------------------------- rapordan önceki davranış

@dataclass(frozen=True)
class Behavior:
    covered: bool             # rapor anında aracın kaydı var mı
    window_min: int           # değerlendirilen pencere (≤30 dk)
    base_delta_m: float       # pencerede üsse uzaklık değişimi (negatif = yaklaştı)
    moved: bool               # pencerede hareket adımı var mı
    state: Kinematics | None  # rapor anındaki durum (yalnızca o ana kadarki kayıtla)


def behavior(ctx: EvidenceContext, track_id: str, t: int) -> Behavior:
    tr, base, cfg = ctx.repo.track(track_id), ctx.repo.base, settings.kinematics
    end = tr.position_at(t)
    if end is None:
        return Behavior(False, 0, 0.0, False, None)
    start_t = max(tr.start_min, t - settings.reports.behavior_window_min)
    if t - start_t < 10:
        return Behavior(False, t - start_t, 0.0, False, None)   # rapordan önce en az 10 dk kayıt gerekir
    start = tr.position_at(start_t)
    pts = [start] + [p for p in tr.points if start_t < p.t < t] + [end]
    moved = any(distance_m(a.lat, a.lon, b.lat, b.lon) > cfg.move_step_m for a, b in zip(pts, pts[1:]))
    delta = dist_to_base_m(base, end.lat, end.lon) - dist_to_base_m(base, start.lat, start.lon)
    return Behavior(True, t - start_t, round(delta, 1), moved, track_state_at(tr, base, t))


def approach_after(ctx: EvidenceContext, track_id: str, t: int) -> tuple[bool, float]:
    """Araç rapordan SONRA (çekime kadar) üsse belirgin yaklaştı mı? → (bayrak, uzaklık değişimi)"""
    tr, base = ctx.repo.track(track_id), ctx.repo.base
    at = tr.position_at(t)
    if at is None:
        return False, 0.0
    delta = dist_to_base_m(base, tr.last.lat, tr.last.lon) - dist_to_base_m(base, at.lat, at.lon)
    end = ctx.kinematics[track_id]
    return (delta <= -settings.reports.after_approach_m or (end.consistent_approach and delta < 0)), round(delta, 1)


def _behavior_text(b: Behavior) -> str:
    if not b.covered:
        return "rapordan önce aracın yeterli hareket kaydı yok"
    if not b.moved:
        return f"rapordan önceki {b.window_min} dk yerinde duruyor"
    return f"rapordan önceki {b.window_min} dk'da üsse uzaklık {b.base_delta_m:+.0f} m"


# ---------------------------------------------------------------- dış arayüz

def check_report(ctx: EvidenceContext, report: Report) -> tuple[ClaimCheck, ...]:
    claim, links = ctx.claims[report.id], ctx.links[report.id]
    checks = []
    for ct in claim.claim_types:
        fn = _CHECKS.get(ct, _check_unverifiable)
        status, reason, observed, subjects = fn(ctx, report, claim, links)
        checks.append(ClaimCheck(
            report_id=report.id, time=report.time, source=report.source.value, claim_type=ct,
            status=status, reason=reason, subjects=tuple(subjects), observed=observed,
            evidence=(f"report:{report.id}",) + _refs(subjects),
        ))
    return tuple(checks)


def report_status(checks: tuple[ClaimCheck, ...]) -> ClaimStatus:
    """Raporun bütün iddialarının en kötüsü (çelişki > kısmi > doğrulandı > doğrulanamaz)."""
    order = [S.CONTRADICTED, S.PARTIAL, S.VERIFIED, S.UNVERIFIABLE]
    return min((c.status for c in checks), key=order.index, default=S.UNVERIFIABLE)


# ---------------------------------------------------------------- iddia tipleri
# Her kontrol → (durum, gerekçe, gözlem sözlüğü, ilgili özneler)

def _no_subject(ctx, claim, links) -> tuple:
    near = resolve_subjects(ctx, claim, links, radius=settings.reports.track_close_m)
    hint = f"; {near[0].dist_m:.0f} m ötede {_describe(near[0])}" if near else ""
    return (S.UNVERIFIABLE, f"Görüntüde koordinatta ({_tolerance(claim):.0f} m) araç yok{hint}. "
            "Anlatılan araç bulunamadı.", {"subjects": 0}, [])


def _check_stationary(ctx, report, claim, links):
    # "7 kamyon duruyor" gibi grup iddiasında özne, sayım yarıçapındaki araçlardan seçilir
    radius = settings.reports.track_close_m if (claim.count or 0) > 1 else None
    p = _primary(resolve_subjects(ctx, claim, links, radius=radius), claim.vehicle_type)
    if p is None:
        return _no_subject(ctx, claim, links)
    type_note = "" if _label_matches(claim.vehicle_type, p.label) or not p.label else \
        f"; tip uyuşmuyor (iddia {claim.vehicle_type}, tespit {p.label})"
    if p.kind == "parked":
        st = S.VERIFIED if not type_note else S.PARTIAL
        return st, f"{_describe(p)}: hareket kaydı yok, çekimde yerinde{type_note}.", {}, [p]
    b = behavior(ctx, p.track_id, report.t)
    if not b.covered:
        return S.UNVERIFIABLE, f"{_describe(p)}: {_behavior_text(b)}.", {}, [p]
    required = claim.stationary_min or settings.reports.long_stationary_min
    k = b.state
    whole = k.stationary_min == k.observed_min and k.observed_min > 0
    if k.stationary_min >= required:
        st = S.VERIFIED if not type_note else S.PARTIAL
        note = f"rapor anında {k.stationary_min} dk durağan"
    elif whole:     # kaydın kapsadığı sürenin tamamında durağan; iddianın geri kalanı görülemiyor
        st, note = S.PARTIAL, (f"kaydın kapsadığı {k.observed_min} dk boyunca durağan; iddia edilen {required} dk'nın "
                               f"kalanı veride yok")
    elif k.stationary_min > 0:
        st, note = S.PARTIAL, f"rapor anında yalnızca {k.stationary_min} dk durağan (iddia ≥ {required} dk)"
    else:
        st, note = S.CONTRADICTED, "rapor anında hareket halinde"
    return st, f"{_describe(p)}: {note}{type_note}.", {"required_min": required}, [p]


def _check_count(ctx, report, claim, links):
    if claim.count is None:
        return S.UNVERIFIABLE, "Sayı belirtilmemiş.", {}, []
    around = resolve_subjects(ctx, claim, links, radius=settings.reports.track_close_m)
    if not around:
        return _no_subject(ctx, claim, links)
    matching = [s for s in around if s.label and _label_matches(claim.vehicle_type, s.label)]
    unlabeled = [s for s in around if not s.label]
    observed = len(matching)
    obs = {"claimed": claim.count, "observed": observed, "nearby": len(around)}
    listing = ", ".join(_describe(s) for s in around[:6])
    radius = settings.reports.track_close_m
    if observed == claim.count:
        return S.VERIFIED, f"İddia {claim.count} {claim.vehicle_type}; görüntüde {radius:.0f} m içinde {observed}.", obs, matching
    if observed == 0 and not unlabeled:
        return (S.CONTRADICTED, f"İddia {claim.count} {claim.vehicle_type}; görüntüde {radius:.0f} m içinde bu tipte "
                f"araç yok ({listing}).", obs, around)
    if (observed + len(unlabeled)) * 2 < claim.count:
        return (S.CONTRADICTED, f"İddia {claim.count} {claim.vehicle_type}; görüntüde {radius:.0f} m içinde yalnızca "
                f"{observed}{f' (+{len(unlabeled)} etiketsiz)' if unlabeled else ''} — sayı ciddi şişirilmiş.",
                obs, matching or around)
    return (S.PARTIAL, f"İddia {claim.count} {claim.vehicle_type}; görüntüde {radius:.0f} m içinde {observed}"
            f"{f' (+{len(unlabeled)} etiketsiz)' if unlabeled else ''}.", obs, matching or around)


def _motion_verdict(claim: Claim, b: Behavior) -> tuple[ClaimStatus, str]:
    net = settings.kinematics.approach_net_m
    m = claim.motion
    if m == "approaching_base":
        if b.base_delta_m <= -net:
            return S.VERIFIED, "üsse yaklaşıyordu"
        if b.base_delta_m >= net or not b.moved:
            return S.CONTRADICTED, "üsse yaklaşmıyordu"
        return S.PARTIAL, "belirgin yaklaşma yok"
    if m == "leaving_area":
        if b.base_delta_m >= net:
            return S.VERIFIED, "üsten uzaklaşıyordu"
        if b.base_delta_m <= -net:
            return S.CONTRADICTED, "tersine üsse yaklaşıyordu"
        return (S.CONTRADICTED if not b.moved else S.PARTIAL), "uzaklaşma görülmüyor"
    if m in ("transit", "moving"):
        return (S.VERIFIED, "hareket halindeydi") if b.moved else (S.CONTRADICTED, "hareket etmiyordu")
    # normal_activity ("hareketleri olağan")
    if (b.state and b.state.consistent_approach) or b.base_delta_m <= -3 * net:
        return S.CONTRADICTED, "üsse belirgin/tutarlı yaklaşma var; 'olağan' değil"
    return S.VERIFIED, "belirgin tehdit hareketi yok"


def _flat(b: Behavior) -> bool:
    """Rapordan önceki pencerede üsse uzaklık belirgin değişmedi (duruyor / yanal)."""
    return abs(b.base_delta_m) < settings.kinematics.approach_net_m


def _check_motion(ctx, report, claim, links):
    if claim.motion in (None, "stationary"):
        return S.UNVERIFIABLE, "Hareket iddiası yok.", {}, []
    p = _primary(resolve_subjects(ctx, claim, links), claim.vehicle_type)
    if p is None:
        return _no_subject(ctx, claim, links)
    if p.kind == "parked":
        if claim.motion == "normal_activity":
            return S.VERIFIED, f"{_describe(p)}: hareket kaydı yok, yerinde.", {}, [p]
        return S.UNVERIFIABLE, f"{_describe(p)}: hareket kaydı yok; iddia edilen hareket sınanamıyor.", {}, [p]
    b = behavior(ctx, p.track_id, report.t)
    reassuring = claim.motion in ("leaving_area", "normal_activity")
    after_flag, after_delta = approach_after(ctx, p.track_id, report.t)
    if not b.covered:
        note = f"; rapordan sonra çekime kadar üsse {after_delta:+.0f} m" if reassuring and after_flag else ""
        return (S.UNVERIFIABLE, f"{_describe(p)}: {_behavior_text(b)}{note}.",
                {"claimed_motion": claim.motion, "after_delta_m": after_delta,
                 "reassuring_on_approach": reassuring and after_flag}, [p])
    st, verdict = _motion_verdict(claim, b)
    if st == S.CONTRADICTED and claim.motion == "approaching_base" and after_flag and _flat(b):
        st, verdict = S.PARTIAL, verdict + f"; ama rapordan sonra çekime kadar üsse {after_delta:+.0f} m yaklaştı"
    flag = reassuring and (b.base_delta_m <= -settings.kinematics.approach_net_m or after_flag)
    if flag and st == S.VERIFIED:      # rapor anında doğru olsa da güven verici iddia, sonra üsse yaklaşan araçta
        st = S.PARTIAL
    note = f"; rapordan sonra çekime kadar üsse {after_delta:+.0f} m" if reassuring and after_flag else ""
    obs = {"claimed_motion": claim.motion, "base_delta_m": b.base_delta_m, "window_min": b.window_min,
           "after_delta_m": after_delta, "reassuring_on_approach": flag}
    return st, f"{_describe(p)}: {_behavior_text(b)} ({verdict}){note}.", obs, [p]


def _check_identity(ctx, report, claim, links):
    """Dost / ikmal / "bize bağlı" iddiası: kimlik veriden teyit EDİLEMEZ → en fazla 'kısmen'.
    Fiziksel ayrıntılar (tip, hareket) çelişirse 'çelişkili'. Üsse yaklaşan araca iliştirilmişse bayrak."""
    p = _primary(resolve_subjects(ctx, claim, links), claim.vehicle_type)
    if p is None:
        st, reason, obs, _ = _no_subject(ctx, claim, links)
        return S.UNVERIFIABLE, "Dost iddiası: " + reason, obs, []
    problems = []
    if p.label and not _label_matches(claim.vehicle_type, p.label):
        problems.append(f"tip uyuşmuyor (iddia {claim.vehicle_type}, tespit {p.label})")
    approaching, beh = False, ""
    if p.kind == "tracked":
        b = behavior(ctx, p.track_id, report.t)
        after_flag, after_delta = approach_after(ctx, p.track_id, report.t)
        if after_flag:
            approaching, beh = True, f"rapordan sonra çekime kadar üsse {after_delta:+.0f} m"
        if b.covered:
            beh = _behavior_text(b) + (f"; {beh}" if beh else "")
            approaching = approaching or b.base_delta_m <= -settings.kinematics.approach_net_m
            if claim.motion and claim.motion != "stationary":
                st, verdict = _motion_verdict(claim, b)
                if st == S.CONTRADICTED and not (claim.motion == "approaching_base" and after_flag and _flat(b)):
                    problems.append(f"hareket iddiası tutmuyor ({verdict})")
    obs = {"reassuring_on_approach": approaching}
    if problems:
        return S.CONTRADICTED, f"Dost iddiası {_describe(p)} için gözlemle çelişiyor: " + "; ".join(problems) + ".", obs, [p]
    if approaching:
        return (S.PARTIAL, f"Güven verici iddia ÜSSE YAKLAŞAN araca iliştirilmiş: {_describe(p)}, {beh}. "
                "Kimlik veriden teyit edilemez; risk düşürülmez.", obs, [p])
    color = f"; '{claim.color}' renk iddiası görsel kontrol gerektirir" if claim.color else ""
    return (S.PARTIAL, f"Dost iddiası {_describe(p)} ile fiziksel olarak tutarlı{f' ({beh})' if beh else ''}{color}; "
            "kimlik veriden teyit edilemez.", obs, [p])


def _check_density(ctx, report, claim, links):
    radius = settings.reports.track_link_radius_m
    around = resolve_subjects(ctx, claim, links, radius=radius)
    normal, observed = claim.normal_count, len(around)
    obs = {"normal": normal, "observed": observed, "radius_m": radius}
    detail = f"görüntüde {radius:.0f} m içinde {observed} araç (olağan {normal})"
    if normal is None:
        return S.UNVERIFIABLE, f"Olağan sayı belirtilmemiş; {detail}.", obs, around
    if observed > normal:
        return S.VERIFIED, f"Yoğunluk doğrulandı: {detail}.", obs, around
    if observed == normal:
        return S.PARTIAL, f"Olağan düzeyde: {detail}.", obs, around
    return S.CONTRADICTED, f"Olağanın altında: {detail}.", obs, around


def _check_zone_status(ctx, report, claim, links):
    """Bölge raporu (koordinatsız): rapor saatinde bölgede kaydı olan track'lerle yargılanır."""
    status, repo = claim.zone_status, ctx.repo
    look = settings.reports.zone_lookback_min
    recent = [tr.id for tr in repo.tracks() if any(
        report.t - look <= p.t <= report.t and nearest_zone(p.lat, p.lon, repo.zones)[0].name == claim.zone
        for p in tr.points)]
    if status == "no_heavy":
        heavy_now = [t for t in dict.fromkeys(list(links.zone_tracks) + recent) if ctx.label_of_track(t) in HEAVY]
        subj = [Subject(kind="tracked", detection_id=ctx.track_det.get(t), track_id=t, label=ctx.label_of_track(t),
                        dist_m=0.0) for t in heavy_now]
        obs = {"heavy_tracks_at_report": len(heavy_now)}
        if heavy_now:
            return (S.CONTRADICTED, f"'{claim.zone}' bölgesinde ağır araç yok deniyor; rapor anında ({report.time}) "
                    f"ve önceki {look} dk'da bölgede {len(heavy_now)} ağır araç kaydı var: {', '.join(heavy_now)}.", obs, subj)
        return (S.PARTIAL, f"Rapor anında ({report.time}) '{claim.zone}' bölgesinde ağır araç kaydı yok; park halindeki "
                "araçların track'i olmayabileceği için yokluk tam doğrulanamaz.", obs, [])
    if status == "normal":
        flagged, circling = [], []
        for t in dict.fromkeys(list(links.zone_tracks) + recent):
            k = track_state_at(repo.track(t), repo.base, report.t)
            if k is None:
                continue
            if k.circling:
                circling.append(t)
            elif k.consistent_approach:
                flagged.append(t)
        subj = [Subject(kind="tracked", detection_id=ctx.track_det.get(t), track_id=t, label=ctx.label_of_track(t),
                        dist_m=0.0) for t in circling + flagged]
        if circling:
            return (S.CONTRADICTED, f"'{claim.zone}' için 'olağandışı durum yok' deniyor; rapor anında bölgede ÜSSÜN "
                    f"ETRAFINDA DÖNEN araç var (son {look} dk): {', '.join(circling)}.", {"circling": len(circling)}, subj)
        if flagged:
            return (S.PARTIAL, f"'{claim.zone}' için 'normal' deniyor; rapor anında bölgede üsse tutarlı yaklaşan "
                    f"{len(flagged)} araç var: {', '.join(flagged)}.", {"consistent_approachers": len(flagged)}, subj)
        return S.VERIFIED, f"Rapor anında '{claim.zone}' bölgesinde olağandışı hareket yok.", {}, []
    return S.UNVERIFIABLE, "Bölge bağlamı (ihbar / iletişim durumu); gözlemle doğrulanamaz.", {}, []


def _check_unverifiable(ctx, report, claim, links):
    if claim.blanket_friendly:
        return (S.UNVERIFIABLE, "Konumsuz genel dost duyurusu; hiçbir aracın riskini tek başına düşürmez.",
                {"blanket_friendly": True}, [])
    return S.UNVERIFIABLE, "Genel bilgi; araç/konum iddiası yok.", {}, []


_CHECKS = {
    ClaimType.STATIONARY: _check_stationary,
    ClaimType.COUNT: _check_count,
    ClaimType.MOTION: _check_motion,
    ClaimType.IDENTITY: _check_identity,
    ClaimType.DENSITY: _check_density,
    ClaimType.ZONE_STATUS: _check_zone_status,
}
