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
    assert c.status == S.PARTIAL                         # kayıt 35 dk'yı kapsıyor, tamamında durağan; kalanı görülemez
    assert "kaydın kapsadığı" in c.reason
    assert _status(ctx, "R015", ClaimType.STATIONARY).status == S.VERIFIED


def test_count_inflation_is_partial(ctx):
    c = _status(ctx, "R094", ClaimType.COUNT)            # "2 kamyon" → görüntüde 1
    assert c.status == S.PARTIAL and c.observed["claimed"] == 2 and c.observed["observed"] == 1
    c = _status(ctx, "R101", ClaimType.COUNT)            # "7 kamyon" → görüntüdeki koordinatta 5
    assert c.status == S.PARTIAL and c.observed["observed"] == 5
    # grup iddiasında özne sayım yarıçapından seçilir (koordinata 28 m'deki kamyon)
    assert _status(ctx, "R101", ClaimType.STATIONARY).subjects[0].track_id == "T0135"


def test_img_003201_reports(ctx):
    assert _status(ctx, "R130", ClaimType.COUNT).status == S.VERIFIED           # görüntüde 1 ağır araç
    assert _status(ctx, "R129", ClaimType.MOTION).status == S.VERIFIED          # panelvan üsse yaklaşıyordu
    ident = _status(ctx, "R129", ClaimType.IDENTITY)                            # ikmal iddiası yaklaşan araçta
    assert ident.status == S.PARTIAL and ident.observed["reassuring_on_approach"]
    assert _status(ctx, "R019", ClaimType.STATIONARY).status == S.PARTIAL       # kaydın kapsadığı 25 dk durağan


def test_identity_never_verified(ctx):
    for rid in ctx.claims:
        for c in check_report(ctx, ctx.repo.report(rid)):
            if c.claim_type == ClaimType.IDENTITY:
                assert c.status != S.VERIFIED


def test_friendly_claim_judged_before_report(ctx):
    """R007 (14:15) "üsse gelen otomobil bize bağlı": T0131 rapordan önceki 30 dk'da üsten 1.9 km uzaklaşıyor →
    çelişkili (sonradan yaklaşması hükmü yumuşatmaz, yalnızca bayrak). R102: T0022 rapordan önce duruyor, sonra
    yaklaşıyor → kısmen."""
    motion = _status(ctx, "R007", ClaimType.MOTION)
    assert motion.status == S.CONTRADICTED and motion.subjects[0].track_id == "T0131"
    ident = _status(ctx, "R007", ClaimType.IDENTITY)
    assert ident.status == S.CONTRADICTED and ident.observed["reassuring_on_approach"]
    assert _status(ctx, "R102", ClaimType.IDENTITY).status == S.PARTIAL


def test_reassuring_claim_on_later_approacher(ctx):
    """R126 (12:35) "hareketleri olağan": rapor anında T0122 duruyor, sonra üsse 4.3 km yaklaşıyor."""
    c = _status(ctx, "R126", ClaimType.MOTION)
    assert c.status == S.PARTIAL and c.observed["reassuring_on_approach"]
    assert c.subjects[0].track_id == "T0122"


def test_report_status_takes_worst(ctx):
    assert report_status(check_report(ctx, ctx.repo.report("R129"))) == S.PARTIAL
    assert report_status(check_report(ctx, ctx.repo.report("R017"))) == S.CONTRADICTED
    assert report_status(()) == S.UNVERIFIABLE


def test_zone_reports(ctx):
    assert _status(ctx, "R017", ClaimType.ZONE_STATUS).status == S.CONTRADICTED   # rapor anında T0174 kamyon
    assert _status(ctx, "R092", ClaimType.ZONE_STATUS).status == S.PARTIAL     # yokluk tam doğrulamaz
    assert _status(ctx, "R012", ClaimType.ZONE_STATUS).status == S.CONTRADICTED  # T0174 son 15 dk'da bölgede
    c = _status(ctx, "R042", ClaimType.ZONE_STATUS)                               # "olağan" ama T0034 dönüyor
    assert c.status == S.CONTRADICTED and "T0034" in c.reason


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


def test_reports_never_lower_risk(dossiers):
    for d in dossiers.values():
        for v in d.vehicles:
            assert all(f.weight > 0 for f in v.baseline_risk.factors if f.name == "reassuring_claim")
            assert not {"verified_friendly_claim", "unverified_friendly_claim"} & {f.name for f in v.baseline_risk.factors}


def test_top_threats(dossiers):
    by_track = {}
    for d in dossiers.values():
        for v in d.vehicles:
            if v.track_id:
                by_track[v.track_id] = max(by_track.get(v.track_id, 0), v.baseline_risk.score)
    top = max(by_track.values())
    assert by_track["T0122"] == top                       # tutarlı yaklaşan kamyon + yanıltıcı "olağan" raporu
    t0122 = next(v for d in dossiers.values() for v in d.vehicles if v.track_id == "T0122")
    assert {"consistent_approach", "reassuring_claim"} <= {f.name for f in t0122.baseline_risk.factors}
    for tid in ("T0043", "T0158", "T0172", "T0198", "T0034"):   # üssün etrafında dönenler
        assert by_track[tid] >= 70


def test_circling_anomaly(dossiers):
    circ = {a.evidence[0] for d in dossiers.values() for a in d.anomalies if a.type == "circling_base"}
    assert circ == {"track:T0043", "track:T0158", "track:T0172", "track:T0198", "track:T0034"}


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


def test_image_position_semantics(ctx):
    """Rapor koordinatı aracın GÖRÜNTÜDEKİ konumudur; R114 "1 kamyon": görüntüde koordinatta etiketsiz 1 araç."""
    c = _status(ctx, "R114", ClaimType.COUNT)
    assert c.status == S.PARTIAL and c.observed["observed"] == 0


def test_gold_labels_layer1():
    from backend.engine.eval.gold import evaluate
    assert evaluate()["l1_acc"] >= 0.95
