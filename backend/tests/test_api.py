"""API sözleşmesi (Flask test client, ağsız; analiz işleri sahte pipeline ile)."""

import json
import time

import pytest

from backend.api.app import create_app


@pytest.fixture(scope="module")
def client():
    return create_app(warm=False).test_client()


def _ok(client, url, status=200):
    r = client.get(url)
    assert r.status_code == status, (url, r.get_data(as_text=True)[:300])
    return r.get_json()


def test_meta(client):
    assert _ok(client, "/api/health")["status"] == "ok"
    z = _ok(client, "/api/zones")
    assert z["base"]["name"] == "Merkez Us" and len(z["zones"]) == 8
    o = _ok(client, "/api/overview")
    assert o["counts"]["images"] == 40 and set(o["risk_summary"]) == {"critical", "high", "medium", "low"}
    assert {"id", "capture_time", "zone", "max_risk", "assessed", "urls"} <= set(o["images"][0])
    assert "risk" in _ok(client, "/api/config")


def test_images(client):
    assert _ok(client, "/api/images")["total"] == 40
    assert _ok(client, "/api/images?time_from=10:00&time_to=10:30")["total"] > 0
    high = _ok(client, "/api/images?min_risk=high")["items"]
    assert all(i["max_risk"] in ("critical", "high") for i in high)
    d = _ok(client, "/api/images/img_000267")
    assert d["width_px"] == 1920 and len(d["detections"]) == 6
    truck = next(x for x in d["detections"] if x["id"] == "img_000267_003")
    assert truck["track_id"] == "T0045" and truck["bbox_xywh"] == [834, 164, 45, 49]
    assert _ok(client, "/api/images/img_000267/dossier")["image_id"] == "img_000267"
    r = client.get("/api/images/img_000267/file?variant=annotated")
    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    assert _ok(client, "/api/images/nope", 404)["error"]["code"] == "not_found"
    assert _ok(client, "/api/images/img_000267/file?variant=x", 400)["error"]["code"] == "bad_request"


def test_tracks(client):
    at = _ok(client, "/api/tracks?time=10:15")
    assert at["time"] == "10:15" and any(p["track_id"] == "T0045" for p in at["points"])
    t = _ok(client, "/api/tracks/T0045")
    assert len(t["points"]) == 25 and t["kinematics"]["state"] == "stationary" and t["label"] == "truck"
    assert len(_ok(client, "/api/tracks?image_id=img_000267")["items"]) == 5
    _ok(client, "/api/tracks", 400)
    _ok(client, "/api/tracks/T9999", 404)


def test_reports(client):
    assert _ok(client, "/api/reports")["total"] == 137
    linked = _ok(client, "/api/reports?image_id=img_000267")["items"]
    assert {r["id"] for r in linked if r["category"] == "coordinate"} == {"R053", "R083", "R094"}
    assert {r["id"] for r in linked if r["category"] == "zone"} == {"R013", "R070", "R081"}   # bağlam
    contradicted = _ok(client, "/api/reports?status=contradicted&category=coordinate")["items"]
    assert contradicted and all(r["status"] == "contradicted" for r in contradicted)
    r = _ok(client, "/api/reports/R053")
    assert r["status"] == "verified" and r["links"]["tracks"][0] == "T0045" and "links_detail" in r


def test_alerts_and_timeline(client):
    alerts = _ok(client, "/api/alerts?min_risk=high")["items"]
    assert alerts and all(a["risk_level"] in ("critical", "high") for a in alerts)
    ranks = [("critical", "high").index(a["risk_level"]) for a in alerts]
    assert ranks == sorted(ranks)
    _ok(client, "/api/alerts?min_risk=x", 400)
    ev = _ok(client, "/api/timeline")["events"]
    assert {e["kind"] for e in ev} >= {"report", "capture"}
    assert [e["time"] for e in ev] == sorted(e["time"] for e in ev)


def test_assess_job_and_sse(client, monkeypatch):
    from backend.engine import pipeline

    def fake_run_all(ids, force=False, on_event=None, reasoning_effort=None, **kw):
        for i in ids:
            on_event({"type": "start", "image_id": i})
            on_event({"type": "tool_call", "image_id": i, "tool": "co_movement", "args": "{}"})
            time.sleep(0.05)
            on_event({"type": "done", "image_id": i, "overall_risk": "high"})
        return {}

    monkeypatch.setattr(pipeline, "run_all", fake_run_all)
    r = client.post("/api/images/img_000267/assess", json={"reasoning_effort": "low"})
    assert r.status_code == 202
    job = r.get_json()
    assert job["job_id"].startswith("job_") and job["events_url"].endswith("/events")

    stream = client.get(job["events_url"])
    assert stream.mimetype == "text/event-stream"
    body = stream.get_data(as_text=True)
    types = [line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("event: ")]
    assert types[0] == "job_started" and "tool_call" in types and types[-1] == "job_finished"
    data = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert data[-1]["results"] == {"img_000267": "high"}

    final = _ok(client, f"/api/jobs/{job['job_id']}")
    assert final["status"] == "done" and final["progress"] == {"done": 1, "total": 1}
    assert any(j["job_id"] == job["job_id"] for j in _ok(client, "/api/jobs")["items"])
    # yeniden bağlanma: Last-Event-ID'den sonrası
    resumed = client.get(job["events_url"], headers={"Last-Event-ID": str(data[-2]["id"])}).get_data(as_text=True)
    assert resumed.count("event: ") == 1


def test_assess_validation(client):
    assert client.post("/api/images/nope/assess").status_code == 404
    assert client.post("/api/assess", json={"image_ids": "x"}).status_code == 400
    assert client.post("/api/assess", json={"reasoning_effort": "ultra"}).status_code == 400
    _ok(client, "/api/jobs/job_nope", 404)
