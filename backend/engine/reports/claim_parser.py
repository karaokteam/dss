"""Raporları yapısal iddialara (`Claim`) çevirir.

İki parser vardır:
- rules: veri setindeki kalıpları kapsayan deterministik kurallar (LLM'siz, test edilebilir)
- llm:   `backend/prompts/claim_parser.md` ile GLM; bilinmeyen kalıplara genellenebilir

Varsayılan mod (config.reports.parser_mode = "llm"): LLM sonucu kullanılır, kurallarla çapraz kontrol edilir,
alan uyuşmazlıkları `parse_notes`'a yazılır. LLM yoksa ya da geçersiz yanıt verirse kurallara düşülür.
Koordinat, bölge ve kategori her iki modda da `extract` modülünden gelir.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from backend.config import settings
from backend.engine.models import (
    CARGO, MOTIONS, VEHICLE_TYPES, ZONE_STATUSES, Claim, ClaimType, Report, Zone,
)
from backend.engine.reports.extract import Extracted, color_in, count_in, extract, vehicle_type_in

# ---------------------------------------------------------------- kural tabanlı parser

_NOISE = ("hava acik", "gorus mesafesi", "lojistik konvoyu", "tatbikat")
_ZONE_STATUS = (
    ("olagandisi bir durum bildirmedi", "normal"),
    ("kayda deger bir hareketlilik bulunmuyor", "normal"),
    ("trafik akisi normal", "normal"),
    ("agir arac hareketi yok", "no_heavy"),
    ("dogrulanmamis bir ihbar", "unverified_tip"),
    ("dogrulanamadi", "unverified_tip"),
    ("telsiz baglantisi", "comms_lost"),
)
_FRIENDLY = ("dost", "bize bagli", "planli ikmal", "kimlik teyidi", "teyitli")
_MOTION = (
    (r"usse dogru ilerle|usse gelen|usse yaklas", "approaching_base"),
    (r"uzaklasiyor", "leaving_area"),
    (r"transit", "transit"),
    (r"hareketleri olagan", "normal_activity"),
    (r"ilerliyor", "moving"),
)
_STATIONARY = ("hareketsiz", "park halinde", "beklemede", "bekliyor", "durdugu", "yerinden ayrilmadi")
_DENSITY = ("olagandan yogun", "beklenmedik bir yogunluk")
_HEDGE = ("ihbar", "bir kaynak", "bildirildi", "dogrulanmamis")   # "bildirilmistir" (önceden bildirildi) çekince değil
# Tekil araç anlatımı: "bir kamyon", "otomobil ... ilerleyen", "mavi arac" (çoğul "-lar/-ler" değil)
_SINGULAR = re.compile(r"\b(?:kamyon|otomobil|panelvan|otobus|arac)(?!lar|ler|lik)\w*")


def parse_rules(report: Report, ex: Extracted) -> Claim:
    t = ex.normalized
    common = dict(report_id=report.id, category=ex.category, lat=ex.lat, lon=ex.lon,
                  coord_precision_m=ex.coord_precision_m, zone=ex.zones[0] if ex.zones else None,
                  hedged=any(h in t for h in _HEDGE), parser="rules")

    if ex.category != "coordinate":
        status = next((s for pat, s in _ZONE_STATUS if pat in t), None)
        blanket = "dost unsur" in t
        if status and ex.category == "zone":
            heavy_absent = status == "no_heavy"
            return Claim(**common, claim_types=(ClaimType.ZONE_STATUS,), zone_status=status,
                         vehicle_type="heavy" if heavy_absent else vehicle_type_in(t),
                         count=0 if heavy_absent else None)
        if blanket or any(n in t for n in _NOISE):
            return Claim(**common, claim_types=(ClaimType.NOISE,), blanket_friendly=blanket)
        return Claim(**common, claim_types=(ClaimType.UNKNOWN,))

    friendly = any(f in t for f in _FRIENDLY)
    motion = next((m for pat, m in _MOTION if re.search(pat, t)), None)
    stationary = any(s in t for s in _STATIONARY)
    density = any(d in t for d in _DENSITY)
    explicit_count = None if density else count_in(t)
    count = explicit_count
    if count is None and not density and _SINGULAR.search(t):
        count = 1
    normal_count = None
    if density:
        m = re.search(r"(?:genellikle|olagan trafik)\s+(\d+)", t)
        normal_count = int(m[1]) if m else None
    cargo = ("covered" if "uzeri ortulu" in t else "loaded" if "yuklu" in t
             else "unknown" if "yukleri tespit edilemedi" in t else None)

    # Öncelik: kimlik > açık sayım > hareket > durağanlık > yoğunluk
    types: list[ClaimType] = []
    if friendly:
        types.append(ClaimType.IDENTITY)
    if explicit_count is not None:
        types.append(ClaimType.COUNT)
    if motion:
        types.append(ClaimType.MOTION)
    if stationary:
        types.append(ClaimType.STATIONARY)
    if density:
        types.append(ClaimType.DENSITY)
    if not types and count == 1:
        types.append(ClaimType.COUNT)   # "... kırmızı bir kamyon olduğu bildirildi" → varlık iddiası

    return Claim(
        **common,
        claim_types=tuple(types) or (ClaimType.UNKNOWN,),
        vehicle_type=vehicle_type_in(t),
        count=count,
        motion=motion or ("stationary" if stationary else None),
        stationary_min=settings.reports.stationary_claim_default_min if "bir saatten uzun" in t else None,
        friendly=friendly,
        color=color_in(t),
        cargo=cargo,
        normal_count=normal_count,
    )


# ---------------------------------------------------------------- LLM parser

_COMPARED = ("vehicle_type", "count", "motion", "friendly", "zone_status", "normal_count", "stationary_min")


class ParseError(ValueError):
    pass


def _enum(value, allowed: tuple[str, ...], field_name: str):
    if value is None:
        return None
    if value not in allowed:
        raise ParseError(f"{field_name}: geçersiz değer {value!r}")
    return value


def _int_or_none(value, field_name: str):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value or value < 0:
        raise ParseError(f"{field_name}: tam sayı değil {value!r}")
    return int(value)


def claim_from_llm_json(data: dict, report: Report, ex: Extracted) -> Claim:
    if not isinstance(data, dict):
        raise ParseError("JSON nesnesi değil")
    try:
        types = tuple(ClaimType(t) for t in data.get("claim_types") or [])
    except ValueError as e:
        raise ParseError(str(e)) from None
    if not types:
        raise ParseError("claim_types boş")
    return Claim(
        report_id=report.id, category=ex.category, claim_types=types,
        lat=ex.lat, lon=ex.lon, coord_precision_m=ex.coord_precision_m,
        zone=ex.zones[0] if ex.zones else None,
        vehicle_type=_enum(data.get("vehicle_type"), VEHICLE_TYPES, "vehicle_type"),
        count=_int_or_none(data.get("count"), "count"),
        motion=_enum(data.get("motion"), MOTIONS, "motion"),
        stationary_min=_int_or_none(data.get("stationary_min"), "stationary_min"),
        friendly=bool(data.get("friendly", False)),
        blanket_friendly=bool(data.get("blanket_friendly", False)),
        color=(data.get("color") or None),
        cargo=_enum(data.get("cargo"), CARGO, "cargo"),
        normal_count=_int_or_none(data.get("normal_count"), "normal_count"),
        zone_status=_enum(data.get("zone_status"), ZONE_STATUSES, "zone_status"),
        hedged=bool(data.get("hedged", False)),
        parser="llm",
    )


def parse_llm(report: Report, ex: Extracted, client) -> Claim:
    from backend.engine.llm.prompt_loader import render

    prompt = render("claim_parser")
    result = client.chat(
        [{"role": "system", "content": prompt.text},
         {"role": "user", "content": f"Rapor: {report.text}"}],
        response_format={"type": "json_object"},
        reasoning_effort=settings.agent.parser_reasoning_effort,
        max_tokens=2000, purpose=f"claim_parser:{report.id}",
    )
    try:
        data = result.json()
    except json.JSONDecodeError as e:
        raise ParseError(f"JSON ayrıştırılamadı: {e}") from None
    return claim_from_llm_json(data, report, ex)


def compare(llm: Claim, rules: Claim) -> tuple[str, ...]:
    """Kurallar kalıbı tanıdıysa LLM ile alan alan karşılaştırır."""
    if rules.claim_types == (ClaimType.UNKNOWN,):
        return ("rules: kalıp tanınmadı, yalnızca LLM",)
    notes = []
    if llm.claim_types[0] != rules.claim_types[0]:
        notes.append(f"claim_type: llm={llm.claim_types[0].value} rules={rules.claim_types[0].value}")
    for f in _COMPARED:
        a, b = getattr(llm, f), getattr(rules, f)
        if a != b:
            notes.append(f"{f}: llm={a} rules={b}")
    return tuple(notes)


# ---------------------------------------------------------------- dış arayüz

def parse_report(report: Report, zones: tuple[Zone, ...], mode: str | None = None, client=None) -> Claim:
    mode = mode or settings.reports.parser_mode
    ex = extract(report.text, zones)
    rules = parse_rules(report, ex)
    if mode == "rules":
        return rules
    if client is None:
        from backend.engine.llm.client import LLMUnavailable, get_client
        try:
            client = get_client()
        except LLMUnavailable:
            return replace(rules, parse_notes=("LLM yok: kural parser kullanıldı",))
    try:
        llm = parse_llm(report, ex, client)
    except ParseError as e:
        return replace(rules, parse_notes=(f"LLM yanıtı geçersiz ({e}): kural parser kullanıldı",))
    return replace(llm, parse_notes=compare(llm, rules))


def parse_all(reports: list[Report], zones: tuple[Zone, ...], mode: str | None = None,
              client=None, workers: int | None = None) -> dict[str, Claim]:
    workers = workers or settings.llm.max_concurrency
    with ThreadPoolExecutor(max_workers=workers) as pool:
        claims = list(pool.map(lambda r: parse_report(r, zones, mode, client), reports))
    return {c.report_id: c for c in claims}


# ---------------------------------------------------------------- claims.json

def claim_from_dict(d: dict) -> Claim:
    d = dict(d)
    d["claim_types"] = tuple(ClaimType(t) for t in d["claim_types"])
    d["parse_notes"] = tuple(d.get("parse_notes", ()))
    return Claim(**d)


def save_claims(claims: dict[str, Claim], meta: dict | None = None, path=None) -> None:
    path = path or settings.paths.claims
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta or {}, "claims": {k: c.to_dict() for k, c in sorted(claims.items())}}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def load_claims(path=None) -> dict[str, Claim] | None:
    path = path or settings.paths.claims
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {k: claim_from_dict(v) for k, v in payload["claims"].items()}
