"""Komut satırı: API'den bağımsız debug ve toplu çalıştırma.

    python -m backend.cli ping [--no-cache]
    python -m backend.cli budget
    python -m backend.cli parse-reports [--mode llm|rules]
    python -m backend.cli dossier <image_id|all> [--top N]
    python -m backend.cli assess <image_id|all> [--force] [--effort low|high] [--verbose]
    python -m backend.cli eval [--errors]

Sonraki step'lerde yeni komutlar eklenir (parse-reports, dossier, assess).
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.config import settings
from backend.engine.llm.client import BudgetExceeded, LLMUnavailable, get_client


def _gateway_spend(client) -> float | None:
    """Gateway'deki gerçek toplam harcama. Yanıt header'ındaki istek maliyeti gerçeğin ~1/3'ü
    kadar düşük raporlanıyor; bu yüzden çalıştırma maliyeti bu farktan hesaplanır."""
    try:
        return client.key_info()["spend_usd"]
    except Exception:
        return None


def _print_run_cost(client, spend_before: float | None) -> None:
    after = _gateway_spend(client)
    if spend_before is not None and after is not None:
        print(f"maliyet   : {after - spend_before:.4f} USD (gateway, bu çalıştırma) | toplam {after:.4f} / 15 USD")
    else:
        print(f"maliyet   : ~{client.session_cost_usd:.4f} USD (header; gerçek harcama ~3 katı olabilir)")


def cmd_ping(args: argparse.Namespace) -> int:
    client = get_client()
    result = client.chat(
        [{"role": "user", "content": "Merhaba! Tek kelimeyle cevap ver."}],
        reasoning_effort="low", max_tokens=1000, purpose="ping", use_cache=not args.no_cache,
    )
    print(f"yanıt     : {result.content!r}")
    print(f"önbellek  : {'evet' if result.cached else 'hayır'}")
    print(f"süre      : {result.latency_s:.2f} s")
    print(f"token     : girdi {result.prompt_tokens}, çıktı {result.completion_tokens} "
          f"(düşünme {result.reasoning_tokens})")
    print(f"maliyet   : {result.cost_usd:.6f} USD")
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    print(json.dumps(get_client().key_info(), indent=2, ensure_ascii=False))
    return 0


def cmd_parse_reports(args: argparse.Namespace) -> int:
    from collections import Counter

    from backend.engine.data.repository import get_repository
    from backend.engine.llm.prompt_loader import render
    from backend.engine.reports.claim_parser import parse_all, save_claims

    repo = get_repository()
    mode = args.mode
    client = get_client() if mode == "llm" else None
    before = _gateway_spend(client) if client else None
    claims = parse_all(repo.reports(), repo.zones, mode=mode, client=client)
    save_claims(claims, meta={"mode": mode, "prompt_version": render("claim_parser").version})

    parsers = Counter(c.parser for c in claims.values())
    types = Counter(c.claim_types[0].value for c in claims.values())
    noted = {k: c.parse_notes for k, c in claims.items() if c.parse_notes}
    print(f"rapor     : {len(claims)}  (parser: {dict(parsers)})")
    print(f"tipler    : {dict(types.most_common())}")
    if mode == "llm":
        agree = len(claims) - len(noted)
        print(f"LLM↔kural : {agree}/{len(claims)} rapor tam uyumlu")
        for rid, notes in sorted(noted.items()):
            print(f"  {rid} [{repo.report(rid).text[:60]}]")
            for n in notes:
                print(f"      - {n}")
        _print_run_cost(client, before)
    print(f"kaydedildi: {settings.paths.claims}")
    return 0


def cmd_dossier(args: argparse.Namespace) -> int:
    from collections import Counter

    from backend.engine.analysis.consistency import get_context
    from backend.engine.analysis.dossier import build_all, build_dossier, save_dossier

    ctx = get_context()
    if args.image == "all":
        dossiers = list(build_all(ctx).values())
    else:
        dossiers = [build_dossier(args.image, ctx)]
    for d in dossiers:
        save_dossier(d)

    levels = Counter(v.baseline_risk.level.value for d in dossiers for v in d.vehicles)
    print(f"dossier   : {len(dossiers)} → {settings.paths.dossiers}")
    print(f"araçlar   : {dict(levels)}")
    ranked = sorted(dossiers, key=lambda d: -max((v.baseline_risk.score for v in d.vehicles), default=0))
    for d in ranked[:args.top]:
        print(f"\n{d.image_id} {d.capture_time} {d.zone} (üsse {d.dist_to_base_m:.0f} m) → {d.max_risk.value}")
        for v in d.vehicles[:3]:
            names = ", ".join(f.name for f in v.baseline_risk.factors)
            print(f"  {v.baseline_risk.score:3d} {v.vehicle_id:18s} {v.label or '?':6s} {v.track_id or '-':6s} {names}")
        for a in d.anomalies:
            print(f"  ! {a.type}: {a.detail[:110]}")
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    from collections import Counter

    from backend.engine import pipeline

    client = get_client()
    before = _gateway_spend(client)

    def on_event(e: dict) -> None:
        if not args.verbose:
            return
        who = e.get("image_id", "")
        if e["type"] == "tool_call":
            print(f"  [{who}] → {e['tool']}({e['args']})")
        elif e["type"] == "tool_result":
            print(f"  [{who}] ← {e['summary'][:160]}")
        elif e["type"] in ("repair", "fallback"):
            print(f"  [{who}] {e['type']}: {e.get('errors') or e.get('reason')}")

    ids = None if args.image == "all" else [args.image]
    results = pipeline.run_all(ids, force=args.force, on_event=on_event, reasoning_effort=args.effort)

    levels = Counter(r["overall_risk"] for r in results.values())
    fallbacks = [i for i, r in results.items() if r["trace"].get("fallback")]
    tools = Counter(t["tool"] for r in results.values() for t in r["trace"]["tool_calls"])
    overrides = [(i, v) for i, r in results.items() for v in r["vehicles"]
                 if v["source"] == "agent" and v["risk_level"] != v["baseline_level"]]
    order = ["critical", "high", "medium", "low"]
    print(f"görüntü   : {len(results)}  genel risk: {dict(sorted(levels.items(), key=lambda x: order.index(x[0])))}")
    print(f"tool      : {dict(tools) or 'yok'}   yedek sonuç: {fallbacks or 'yok'}")
    print(f"sapma     : {len(overrides)} araçta agent temel seviyeyi değiştirdi")
    _print_run_cost(client, before)
    ranked = sorted(results.values(), key=lambda r: order.index(r["overall_risk"]))
    for r in ranked[:args.top]:
        print(f"\n{r['image_id']} {r['capture_time']} {r['zone']} → {r['overall_risk'].upper()}")
        print(f"  {r['summary']}")
        for v in r["vehicles"][:3]:
            change = f" (temel {v['baseline_level']})" if v["risk_level"] != v["baseline_level"] else ""
            print(f"  - {v['vehicle_id']} {v['label'] or '?'} {v['risk_level']}{change}: {v['rationale'][:150]}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from backend.engine.eval.gold import evaluate
    r = evaluate()
    pct = lambda x: "-" if x is None else f"{x:.0%}"
    print(f"Altın küme: {r['labels']} etiket (eval/gold_reports.json)")
    print(f"  Katman 1 hüküm doğruluğu : {pct(r['l1_acc'])} ({sum(x['l1_ok'] for x in r['rows'])}/{r['labels']})")
    print(f"  Agent hüküm doğruluğu    : {pct(r['agent_acc'])} ({r['agent_answered']} etikette agent notu var)")
    print(f"  Kritik track atfı        : {pct(r['cite_recall'])}")
    for x in r["rows"]:
        bad = not x["l1_ok"] or x["agent_ok"] is False or x["missing_cite"]
        if args.errors and not bad:
            continue
        mark = "OK " if x["l1_ok"] else "XX "
        print(f"  {mark}{x['key']:<20} {x['category']:<14} altın {x['gold']:<18} K1 {x['l1']:<18} "
              f"agent {x['agent'] or '-'}" + (f"  eksik atıf {x['missing_cite']}" if x["missing_cite"] else ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m backend.cli", description="DSS motor komutları")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ping", help="LLM bağlantı testi")
    p.add_argument("--no-cache", action="store_true", help="önbelleği atla")
    p.set_defaults(func=cmd_ping)

    p = sub.add_parser("budget", help="harcanan / kalan bütçe")
    p.set_defaults(func=cmd_budget)

    p = sub.add_parser("parse-reports", help="raporları iddialara çevir → outputs/claims.json")
    p.add_argument("--mode", choices=("llm", "rules"), default=settings.reports.parser_mode)
    p.set_defaults(func=cmd_parse_reports)

    p = sub.add_parser("dossier", help="Katman 1 kanıt dosyası → outputs/dossiers/ (LLM'siz)")
    p.add_argument("image", help="görüntü id'si ya da 'all'")
    p.add_argument("--top", type=int, default=5, help="en riskli N görüntüyü özetle")
    p.set_defaults(func=cmd_dossier)

    p = sub.add_parser("assess", help="agent değerlendirmesi → outputs/assessments/")
    p.add_argument("image", help="görüntü id'si ya da 'all'")
    p.add_argument("--force", action="store_true", help="güncel sonuç olsa bile yeniden çalıştır")
    p.add_argument("--effort", choices=("low", "high", "max"), default=None, help="reasoning_effort")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--verbose", action="store_true", help="tool çağrılarını canlı göster")
    p.set_defaults(func=cmd_assess)

    p = sub.add_parser("eval", help="rapor hükümlerini elle etiketli altın kümeyle ölç")
    p.add_argument("--errors", action="store_true", help="yalnızca hatalı satırları göster")
    p.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except LLMUnavailable as e:
        print(f"HATA: {e}\n.env dosyasına LLM_API_KEY ekleyin (bkz. .env.example).", file=sys.stderr)
        return 2
    except BudgetExceeded as e:
        print(f"HATA: bütçe freni: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
