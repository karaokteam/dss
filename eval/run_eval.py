"""
Sahibi : Kişi 4 + Kişi 5
Görev  : gold_reports.json ile rapor hükümlerinin doğruluğunu ölçer; her prompt değişikliğinde çalıştırılır

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    python -m eval.run_eval                          # cache/decisions/<image_id>.json kararları
    python -m eval.run_eval --decisions KLASÖR
    python -m eval.run_eval --baseline               # kural tabanı (LLM'siz referans çizgi)

Ölçülenler: hüküm doğruluğu, kategori doğruluğu, kritik kanıta atıf (must_cite), politika ihlali
(doğrulanmamış dost iddiasıyla risk azaltma), hüküm karışıklık tablosu, tek tek hatalar.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from dss.schemas import Decision, ReportVerdict

ROOT = Path(__file__).parents[1]
GOLD = ROOT / "eval" / "gold_reports.json"
STATUSES = ["DOGRULANDI", "KISMEN_DOGRULANDI", "CELISIYOR", "DOGRULANAMADI", "ILGISIZ"]


def load_gold(path: Path = GOLD) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["labels"]


def load_detections(image_id: str) -> list[dict]:
    """Kişi 1'in cache'i (cache/det_<id>.json) varsa onu, yoksa data/image_box_and_reports/detections.json'u okur."""
    cache = ROOT / "cache" / f"det_{image_id}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    box = ROOT / "data" / "image_box_and_reports" / "detections.json"
    for img in json.loads(box.read_text(encoding="utf-8"))["images"]:
        if img["image_id"] == image_id:
            return [{"label": d["label"], "conf": d["confidence"], "lat": d["lat"], "lon": d["lon"]}
                    for d in img["detections"]]
    return []


def baseline_decisions(image_ids: set[str]) -> dict[str, list[ReportVerdict]]:
    from dss.evidence.builder import Data, build_pack
    from eval.baseline import baseline_verdicts
    D = Data(ROOT / "data")
    return {i: baseline_verdicts(build_pack(D, i, load_detections(i)), D) for i in sorted(image_ids)}


def file_decisions(folder: Path, image_ids: set[str]) -> dict[str, list[ReportVerdict]]:
    out = {}
    for i in image_ids:
        f = folder / f"{i}.json"
        if f.exists():
            out[i] = Decision.model_validate_json(f.read_text(encoding="utf-8")).report_verdicts
    return out


def evaluate(gold: list[dict], decisions: dict[str, list[ReportVerdict]]) -> dict:
    rows, confusion, cite_hit, cite_total, policy = [], Counter(), 0, 0, []
    for g in gold:
        verdicts = {v.report_id: v for v in decisions.get(g["image_id"], [])}
        v = verdicts.get(g["report_id"])
        ok_status = {g["status"], *g.get("status_ok", [])}
        row = {"key": f'{g["image_id"]}/{g["report_id"]}', "gold": g["status"], "got": v.status if v else None,
               "status_ok": bool(v and v.status in ok_status), "category_ok": bool(v and v.category == g["category"])}
        if v:
            confusion[(g["status"], v.status)] += 1
            need = set(g.get("must_cite", []))
            cite_total += len(need)
            cite_hit += len(need & set(v.evidence))
            if v.category == "dost_kimlik" and v.risk_effect == "azaltir" and v.status != "DOGRULANDI":
                policy.append(row["key"])
        rows.append(row)
    answered = [r for r in rows if r["got"]]
    n = len(answered) or 1
    return {
        "labels": len(gold), "answered": len(answered),
        "status_acc": sum(r["status_ok"] for r in answered) / n,
        "category_acc": sum(r["category_ok"] for r in answered) / n,
        "cite_recall": cite_hit / cite_total if cite_total else None,
        "policy_violations": policy, "confusion": confusion, "rows": rows,
    }


def report(res: dict, title: str) -> None:
    print(f"\n== {title} ==")
    print(f"Etiket: {res['labels']} · cevaplanan: {res['answered']}")
    if not res["answered"]:
        print("Değerlendirilecek karar yok.")
        return
    print(f"Hüküm doğruluğu  : {res['status_acc']:.0%}")
    print(f"Kategori doğruluğu: {res['category_acc']:.0%}")
    if res["cite_recall"] is not None:
        print(f"Kritik kanıta atıf: {res['cite_recall']:.0%}")
    print(f"Politika ihlali  : {len(res['policy_violations'])} {res['policy_violations'] or ''}")
    short = dict(zip(STATUSES, ["DOGRU", "KISMEN", "CELISK", "DGRLNMZ", "ILGISIZ"], strict=True))
    print("\nKarışıklık (satır: altın, sütun: tahmin)")
    print(" " * 18 + "".join(f"{short[s]:>8}" for s in STATUSES))
    for g in STATUSES:
        print(f"{g:18}" + "".join(f"{res['confusion'].get((g, p), 0):>8}" for p in STATUSES))
    misses = [r for r in res["rows"] if r["got"] and not r["status_ok"]]
    missing = [r["key"] for r in res["rows"] if not r["got"]]
    if misses:
        print("\nYanlış hükümler:")
        for r in misses:
            print(f"  {r['key']}: altın {r['gold']} · tahmin {r['got']}")
    if missing:
        print(f"\nKararı olmayan: {missing}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--decisions", type=Path, default=ROOT / "cache" / "decisions")
    ap.add_argument("--baseline", action="store_true", help="LLM yerine kural tabanı hükümlerini değerlendir")
    args = ap.parse_args()
    gold = load_gold()
    ids = {g["image_id"] for g in gold}
    if args.baseline:
        report(evaluate(gold, baseline_decisions(ids)), "Kural tabanı (LLM'siz)")
    else:
        report(evaluate(gold, file_decisions(args.decisions, ids)), f"Kararlar: {args.decisions}")


if __name__ == "__main__":
    main()
