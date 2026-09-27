"""Rapor hükümlerini ekibin elle etiketlediği altın küme (eval/gold_reports.json, 23 etiket) ile ölçer.

İki katman ayrı ölçülür:
- Katman 1 (kural tabanı, LLM'siz): check_report → report_status.
- Agent: outputs/assessments/<image_id>.json içindeki report_notes hükmü (varsa).
Atıf: must_cite track'lerinin Katman 1 öznelerinde / kanıtlarında geçme oranı.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from backend.config import settings
from backend.engine.analysis.consistency import check_report, get_context, report_status

GOLD = Path(__file__).resolve().parents[3] / "eval" / "gold_reports.json"
L1 = {"verified": "DOGRULANDI", "partial": "KISMEN_DOGRULANDI", "contradicted": "CELISIYOR",
      "unverifiable": "DOGRULANAMADI"}
AGENT = {"reliable": "DOGRULANDI", "partly_reliable": "KISMEN_DOGRULANDI", "unreliable": "CELISIYOR",
         "unverifiable": "DOGRULANAMADI"}


def load_gold(path: Path = GOLD) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["labels"]


def _agent_verdict(image_id: str, report_id: str) -> str | None:
    f = settings.paths.outputs / "assessments" / f"{image_id}.json"
    if not f.exists():
        return None
    notes = json.loads(f.read_text(encoding="utf-8")).get("report_notes", [])
    return next((AGENT.get(n.get("verdict")) for n in notes if n.get("report_id") == report_id), None)


def evaluate(gold: list[dict] | None = None) -> dict:
    gold = gold or load_gold()
    ctx = get_context()
    rows, cite_hit, cite_total = [], 0, 0
    for g in gold:
        checks = check_report(ctx, ctx.repo.report(g["report_id"]))
        ok = {g["status"], *g.get("status_ok", [])}
        l1 = L1[report_status(checks).value]
        agent = _agent_verdict(g["image_id"], g["report_id"])
        cited = {s.track_id for c in checks for s in c.subjects if s.track_id}
        cited |= {e.split(":", 1)[1] for c in checks for e in c.evidence if e.startswith("track:")}
        need = set(g.get("must_cite", []))
        cite_total += len(need)
        cite_hit += len(need & cited)
        rows.append({"key": f"{g['image_id']}/{g['report_id']}", "category": g["category"], "gold": g["status"],
                     "l1": l1, "l1_ok": l1 in ok, "agent": agent, "agent_ok": agent in ok if agent else None,
                     "missing_cite": sorted(need - cited), "note": g["note"]})
    answered = [r for r in rows if r["agent"]]
    return {
        "labels": len(rows),
        "l1_acc": sum(r["l1_ok"] for r in rows) / len(rows),
        "agent_answered": len(answered),
        "agent_acc": sum(r["agent_ok"] for r in answered) / len(answered) if answered else None,
        "cite_recall": cite_hit / cite_total if cite_total else None,
        "l1_confusion": Counter((r["gold"], r["l1"]) for r in rows),
        "rows": rows,
    }
