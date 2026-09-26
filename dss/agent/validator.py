"""LLM kararını kanıt paketine karşı denetler. Hata listesi boşsa karar kabul edilir;
değilse hatalar modele geri gönderilip bir kez yeniden denenir."""
from dss.schemas import LEVEL_ORDER, Decision, EvidencePack


def validate(dec: Decision, pack: EvidencePack) -> list[str]:
    errs = []
    known = ({d.det_id for d in pack.detections} | {m.track_id for m in pack.motions}
             | {r.report_id for r in pack.reports + pack.context_reports}
             | {f.flag_id for f in pack.hard_flags})

    if dec.image_id != pack.image.image_id:
        errs.append("image_id paketle uyuşmuyor")

    # 1) Alt sınır: sert bayrakların altına inilemez
    if LEVEL_ORDER.index(dec.attention_level) < LEVEL_ORDER.index(pack.rule_floor):
        errs.append(f"attention_level {dec.attention_level}, kural alt sınırı {pack.rule_floor} "
                    f"altında. Bayraklar: {[f.flag_id for f in pack.hard_flags]}")
    if LEVEL_ORDER.index(dec.attention_level) > LEVEL_ORDER.index(pack.rule_floor) \
            and not dec.deviation_from_rules:
        errs.append("Seviye kural tabanından yüksek; deviation_from_rules gerekçesi zorunlu")

    # 2) Her karar verilecek rapora bir hüküm
    missing = {r.report_id for r in pack.reports} - {v.report_id for v in dec.report_verdicts}
    if missing:
        errs.append(f"Hükümsüz raporlar: {sorted(missing)}")

    # 3) Uydurma kimlik yok
    cited = {e for v in dec.report_verdicts for e in v.evidence} | \
            {e for v in dec.vehicles for e in v.evidence} | \
            {v.report_id for v in dec.report_verdicts}
    ghost = cited - known
    if ghost:
        errs.append(f"Pakette olmayan kimlikler: {sorted(ghost)}")

    # 4) Politika: doğrulanmamış dost/kimlik iddiası riski azaltamaz
    for v in dec.report_verdicts:
        if v.category == "dost_kimlik" and v.risk_effect == "azaltir" and v.status != "DOGRULANDI":
            errs.append(f"{v.report_id}: doğrulanmamış kimlik iddiası riski azaltamaz")
        if v.status in ("DOGRULANDI", "CELISIYOR", "KISMEN_DOGRULANDI") and not v.evidence:
            errs.append(f"{v.report_id}: {v.status} hükmü kanıt atfı olmadan verilemez")

    if dec.attention_required != (dec.attention_level != "DUSUK"):
        errs.append("attention_required ile attention_level tutarsız")
    return errs
