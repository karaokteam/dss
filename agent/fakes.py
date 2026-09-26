"""Sahte veri üreticileri — HAZIR (Step 0).

Başka step'in kodu hazır olmadan kendi işini geliştirip test etmek için:
    from agent.fakes import make_geo, fake_assessment, fake_events
Varsayılanlar img_000860 civarı; istediğin alanı keyword ile ez. Testler ve UI geliştirme modu kullanır.
"""

from collections.abc import Iterator

from agent.schemas import (
    Brief,
    ClaimVerdict,
    Corners,
    Detection,
    GeoDetection,
    ImageAssessment,
    ImageMeta,
    MotionProfile,
    PipelineEvent,
    ReportClaim,
    RiskFactor,
    TrackPoint,
    VehicleFinding,
)


def make_meta(**kw) -> ImageMeta:
    d = dict(
        image_id="img_000860",
        width_px=960,
        height_px=540,
        capture_time="14:10",
        corner_coordinates=Corners(
            top_left=(39.925651, 32.870729),
            top_right=(39.925651, 32.872131),
            bottom_left=(39.925045, 32.870729),
            bottom_right=(39.925045, 32.872131),
        ),
    )
    return ImageMeta(**(d | kw))


def make_detection(**kw) -> Detection:
    d = dict(image_id="img_000860", cls="truck", confidence=0.9, x=726, y=281, w=60, h=40)
    return Detection(**(d | kw))


def make_geo(**kw) -> GeoDetection:
    d = dict(
        detection=make_detection(),
        lat=39.92531,
        lon=32.87183,
        distance_to_base_m=1600.0,
        nearest_zone="Dogu Yolu",
    )
    return GeoDetection(**(d | kw))


def make_motion(**kw) -> MotionProfile:
    d = dict(
        track_id="T0122",
        speed_mps=8.0,
        heading_deg=270.0,
        approaching_base=True,
        closing_speed_mps=7.5,
        stopped_minutes=0,
        eta_min=3.5,
    )
    return MotionProfile(**(d | kw))


def make_track(
    track_id: str = "T0122", points: list[tuple[str, float, float]] | None = None
) -> list[TrackPoint]:
    points = points or [
        ("14:00", 39.9260, 32.8740),
        ("14:05", 39.9257, 32.8729),
        ("14:10", 39.92531, 32.87183),
    ]
    return [TrackPoint(track_id=track_id, time=t, lat=la, lon=lo) for t, la, lo in points]


def make_claim(**kw) -> ReportClaim:
    d = dict(
        report_id="R000",
        time="13:05",
        source="official",
        vehicle_class="truck",
        count=1,
        location=(39.9374, 32.8483),
    )
    return ReportClaim(**(d | kw))


def make_verdict(**kw) -> ClaimVerdict:
    d = dict(claim=make_claim(), status="unverifiable", evidence="Rapor konumunda o saatte track yok.")
    return ClaimVerdict(**(d | kw))


def make_finding(**kw) -> VehicleFinding:
    factors = [
        RiskFactor(name="proximity.near_base", points=25, reason="Üsse 1,6 km"),
        RiskFactor(name="motion.approaching_base", points=35, reason="7,5 m/s yaklaşıyor, ETA 3,5 dk"),
    ]
    d = dict(
        geo=make_geo(),
        track_id="T0122",
        motion=make_motion(),
        verdicts=[make_verdict()],
        score=60,
        level="HIGH",
        factors=factors,
    )
    return VehicleFinding(**(d | kw))


def fake_assessment(image_id: str = "img_000860") -> ImageAssessment:
    f = make_finding()
    return ImageAssessment(
        image_id=image_id,
        meta=make_meta(image_id=image_id),
        findings=[f],
        overall_level=f.level,
        report_verdicts=f.verdicts,
        brief=Brief(
            image_id=image_id, level=f.level, text="[SAHTE] T0122 kamyon üsse yaklaşıyor.", model=None
        ),
    )


def fake_events(image_id: str = "img_000860") -> Iterator[PipelineEvent]:
    """pipeline.run_events ile aynı biçimde sahte akış — UI geliştirmesi için."""
    names = ["load", "detect", "locate", "match", "motion", "extract", "verify", "brief"]
    for step, name in enumerate(names, start=1):
        yield PipelineEvent(step=step, name=name, status="start")
        payload = {"assessment": fake_assessment(image_id)} if name == "brief" else {}
        yield PipelineEvent(step=step, name=name, status="done", payload=payload)
