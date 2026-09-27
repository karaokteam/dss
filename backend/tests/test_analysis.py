import json

import pytest

from backend.engine.analysis.consistency import build_context, check_report, report_status
from backend.engine.analysis.dossier import build_all, build_dossier
from backend.engine.analysis.risk import level_for
from backend.engine.data.repository import get_repository
from backend.engine.models import ClaimStatus, ClaimType, RiskLevel
from backend.engine.reports.claim_parser import parse_all
from backend.tests.conftest import SAMPLE_IMAGE, SAMPLE_TRUCK_DET, SAMPLE_TRUCK_TRACK

S = ClaimStatus


@pytest.fixture(scope="module")
def ctx():
    repo = get_repository()
    # Testler ağsız ve deterministik: kural parser (LLM ile 137/137 uyumlu)
    return build_context(repo, claims=parse_all(repo.reports(), repo.zones, mode="rules"))


@pytest.fixture(scope="module")
def dossiers(ctx):
    return build_all(ctx)


def _status(ctx, report_id, claim_type):
    checks = check_report(ctx, ctx.repo.report(report_id))
    return next(c for c in checks if c.claim_type == claim_type)


# ---------------------------------------------------------------- iddia doğrulama

def test_stationary_truck_report_verified(ctx):
    c = _status(ctx, "R053", ClaimType.STATIONARY)       # 08:50 "kamyon bir saatten uzun süredir"
    assert c.status == S.VERIFIED
    assert "kayıt başından" in c.reason                  # kayıt 08:15'te başlıyor → alt sınır


def test_count_inflation_is_partial(ctx):
    c = _status(ctx, "R094", ClaimType.COUNT)            # "2 kamyon" → 1
    assert c.status == S.PARTIAL and c.observed["claimed"] == 2 and c.observed["observed"] == 1
    c = _status(ctx, "R101", ClaimType.COUNT)            # "7 kamyon" → 1 park halinde
    assert c.status == S.PARTIAL and c.observed["observed"] == 1


def test_img_003201_conflicting_reports(ctx):
    assert _status(ctx, "R130", ClaimType.COUNT).status == S.CONTRADICTED       # "ağır araç" → yalnızca otomobil
    assert _status(ctx, "R129", ClaimType.MOTION).status == S.CONTRADICTED      # "üsse ilerleyen" → duruyor
    assert _status(ctx, "R129", ClaimType.IDENTITY).status == S.CONTRADICTED    # ikmal iddiası şüpheli
    assert _status(ctx, "R019", ClaimType.STATIONARY).status == S.VERIFIED      # "otomobil hareketsiz" doğru


def test_friendly_claim_without_vehicle(ctx):
    """R007 (14:15) "üsse gelen otomobil bize bağlı": rapor saatinde orada araç yok. Koordinattaki otomobil
    (T0131) oraya ancak 15:00–15:15'te geliyor; yanındaki 0.12 güvenli tespit özne sayılmaz."""
    assert _status(ctx, "R007", ClaimType.IDENTITY).status == S.CONTRADICTED
    motion = _status(ctx, "R007", ClaimType.MOTION)
    assert motion.status == S.UNVERIFIABLE and motion.subjects == ()


def test_friendly_supply_claim_on_stationary_truck(ctx):
    """R083 (08:50) "üsse ilerleyen otomobil, planlı ikmal": yakında yalnızca duran kamyon T0045 var."""
    assert _status(ctx, "R083", ClaimType.MOTION).status == S.CONTRADICTED
    ident = _status(ctx, "R083", ClaimType.IDENTITY)
    assert ident.status == S.CONTRADICTED and "tip uyuşmuyor" in ident.reason


def test_report_status_takes_worst(ctx):
    checks = check_report(ctx, ctx.repo.report("R129"))
    assert report_status(checks) == S.CONTRADICTED
    assert report_status(()) == S.UNVERIFIABLE


def test_noise_and_blanket_unverifiable(ctx):
    for rid, claim in ctx.claims.items():
        if claim.claim_types == (ClaimType.NOISE,):
            assert all(c.status == S.UNVERIFIABLE for c in check_report(ctx, ctx.repo.report(rid)))


def test_low_confidence_detections_not_parked_subjects(ctx):
    from backend.config import settings
    for rid in ctx.claims:
        for c in check_report(ctx, ctx.repo.report(rid)):
            for s in c.subjects:
                if s.kind == "parked":
                    assert ctx.repo.detection(s.detection_id).confidence >= settings.match.low_confidence


# ---------------------------------------------------------------- risk

def test_level_thresholds():
    assert level_for(75) == RiskLevel.CRITICAL
    assert level_for(50) == RiskLevel.HIGH
    assert level_for(25) == RiskLevel.MEDIUM
    assert level_for(0) == RiskLevel.LOW


def test_scores_in_range_and_factors_explain(dossiers):
    for d in dossiers.values():
        for v in d.vehicles:
            r = v.baseline_risk
            assert 0 <= r.score <= 100
            assert r.score == max(0, min(100, sum(f.weight for f in r.factors)))


def test_unverified_friendly_never_lowers_risk(dossiers):
    for d in dossiers.values():
        for v in d.vehicles:
            names = {f.name for f in v.baseline_risk.factors}
            if "verified_friendly_claim" in names:
                ids = [c for c in v.claims if c.claim_type == ClaimType.IDENTITY]
                assert ids and all(c.status == S.VERIFIED for c in ids)


def test_top_threat_is_consistent_approaching_truck(dossiers):
    top = max((v for d in dossiers.values() for v in d.vehicles), key=lambda v: v.baseline_risk.score)
    assert top.track_id == "T0122" and top.label == "truck"
    assert top.baseline_risk.level == RiskLevel.CRITICAL
    assert "consistent_approach" in {f.name for f in top.baseline_risk.factors}


# ---------------------------------------------------------------- dossier

def test_all_dossiers_built(dossiers):
    assert len(dossiers) == 40
    assert sum(len(d.vehicles) for d in dossiers.values()) == 323 + 4   # tespitler + 4 tespitsiz track
    missed = [a for d in dossiers.values() for a in d.anomalies if a.type == "possible_missed_detection"]
    assert len(missed) == 4


def test_sample_dossier(ctx):
    d = build_dossier(SAMPLE_IMAGE, ctx)
    assert d.zone == "Dogu Yolu" and d.capture_time == "10:15"
    truck = next(v for v in d.vehicles if v.vehicle_id == SAMPLE_TRUCK_DET)
    assert truck.track_id == SAMPLE_TRUCK_TRACK and truck.kinematics.motion == "stationary"
    claimed = {(c.report_id, c.claim_type) for c in truck.claims}
    assert ("R053", ClaimType.STATIONARY) in claimed and ("R094", ClaimType.COUNT) in claimed
    # "kamyon durağan" iddiası yanındaki otomobile yüklenmez
    car = next(v for v in d.vehicles if v.track_id == "T0066")
    assert ("R053", ClaimType.STATIONARY) not in {(c.report_id, c.claim_type) for c in car.claims}
    json.dumps(d.to_dict(), ensure_ascii=False)    # API'ye gidebilir


def test_blanket_friendly_in_context_only(dossiers, ctx):
    blanket = {rid for rid, c in ctx.claims.items() if c.blanket_friendly}
    seen = {r.report_id for d in dossiers.values() for r in d.context_reports}
    assert blanket & seen
    for d in dossiers.values():
        for v in d.vehicles:
            assert not blanket & {c.report_id for c in v.claims}
