"""Komutan alarm kuralları: doğal dildeki kural → yapılandırılmış kural → tüm gün üzerinde geriye dönük test.

Kural kodla işletilir; sayılar (kaç araç, saat, mesafe) LLM'den gelmez. Amaç, bir kuralı devreye almadan önce
kaç kez tetikleneceğini (gürültü) ve fotoğraflardan kaç dakika önce uyarı vereceğini görmek.
Metin → kural çevirisini LLM yapar (backend/prompts/alert_rule.md; "öğleden sonra", "ağır vasıta" gibi serbest
ifadeler); LLM yoksa ya da çıktısı geçersizse kural ayrıştırıcı devreye girer. Sohbet asistanı aynı motoru
`test_alert_rule` tool'uyla çağırır.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import asdict, dataclass

from backend.engine.analysis.consistency import get_context
from backend.engine.geo.geometry import dist_to_base_m
from backend.engine.geo.zones import _TR_MAP, find_zones_in_text, nearest_zone, normalize_text, zone_by_name
from backend.engine.models import fmt_hhmm, parse_hhmm

VEHICLES = {"any": None, "car": {"car"}, "van": {"van"}, "truck": {"truck"}, "bus": {"bus"}, "heavy": {"truck", "bus"}}
VEHICLE_TR = {"any": "her araç", "car": "otomobil", "van": "panelvan", "truck": "kamyon", "bus": "otobüs",
              "heavy": "ağır araç (kamyon/otobüs)"}
DEFAULT_DIST_M = 1000.0

_VEHICLE_WORDS = [
    ("heavy", re.compile(r"\bagir (arac|vasita)")),
    ("truck", re.compile(r"\bkamyon(?!et)\w*|\btir(lar|lari|in|a|dan)?\b")),
    ("bus", re.compile(r"\botobus\w*")),
    ("van", re.compile(r"\b(panelvan|minibus|kamyonet)\w*")),
    ("car", re.compile(r"\b(otomobil|araba|binek)\w*")),
]
_CIRCLING = re.compile(r"\bdon(en|erse|uyor|du|me|mek|meye)\w*|\btur (at|atan|atarsa|atiyor)\w*|\betrafinda\w*")
# Türkçe ekler birime bitişik gelebilir ("800 metreden", "1 km'den"); tek başına "m" yalnızca kelime sonunda
_DIST = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kilometre[a-z]*|km(?![a-z])[a-z']*|metre[a-z]*|m(?![a-z]))")
_TIME = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")


@dataclass(frozen=True)
class AlertRule:
    vehicle: str = "any"                 # any | car | van | truck | bus | heavy
    max_dist_m: float | None = DEFAULT_DIST_M   # üsse bu mesafeden yakın (None: mesafe koşulu yok)
    zone: str | None = None              # yalnızca bu bölgede
    time_from: str | None = None         # "HH:MM"
    time_to: str | None = None
    circling_only: bool = False          # yalnızca üssün etrafında dönen araçlar

    def describe(self) -> str:
        parts = [VEHICLE_TR[self.vehicle]]
        if self.max_dist_m is not None:
            d = self.max_dist_m
            parts.append(f"üsse < {d / 1000:g} km" if d >= 1000 else f"üsse < {d:.0f} m")
        if self.circling_only:
            parts.append("üssün etrafında dönüyor")
        if self.zone:
            parts.append(f"bölge: {self.zone}")
        parts.append(f"saat {self.time_from or 'gün başı'}–{self.time_to or 'gün sonu'}"
                     if self.time_from or self.time_to else "tüm gün")
        return " · ".join(parts)


def rule_from_dict(d: dict) -> AlertRule:
    """API/tool girdisini doğrular."""
    vehicle = d.get("vehicle") or "any"
    if vehicle not in VEHICLES:
        raise ValueError(f"vehicle {list(VEHICLES)} içinden olmalı")
    zone = d.get("zone")
    if zone:
        z = zone_by_name(zone, get_context().repo.zones)
        if z is None:
            raise ValueError(f"bilinmeyen bölge: {zone}")
        zone = z.name
    for key in ("time_from", "time_to"):
        if d.get(key):
            parse_hhmm(d[key])
    dist = d.get("max_dist_m", DEFAULT_DIST_M)
    return AlertRule(vehicle=vehicle, max_dist_m=float(dist) if dist not in (None, "") else None, zone=zone or None,
                     time_from=d.get("time_from") or None, time_to=d.get("time_to") or None,
                     circling_only=bool(d.get("circling_only")))


def parse_rule(text: str) -> tuple[AlertRule, list[str]]:
    """Türkçe kural metni → AlertRule ve varsayım notları. Örn. "Bir kamyon üsse 1 km'den fazla yaklaşırsa uyar"."""
    raw = text.translate(_TR_MAP).lower()
    words = normalize_text(text)
    notes = []

    found = [v for v, rx in _VEHICLE_WORDS if rx.search(words)]
    if "heavy" in found or {"truck", "bus"} <= set(found):
        vehicle = "heavy"
    elif len(found) == 1:
        vehicle = found[0]
    else:
        vehicle = "any"
        if found:
            notes.append("birden fazla tip → her araç")
        elif not re.search(r"\bherhangi|\bher arac|\btum arac", words):
            notes.append("araç tipi yazılmadı → her araç")

    circling = bool(_CIRCLING.search(words))
    zones = find_zones_in_text(text, get_context().repo.zones)
    zone = zones[0].name if zones else None

    dist = None
    m = _DIST.search(raw)
    if m:
        value = float(m[1].replace(",", "."))
        dist = value * 1000 if m[2].startswith("k") else value
        raw = raw[:m.start()] + " " + raw[m.end():]      # sayıyı saat sanmamak için çıkar
    elif not circling and not zone:
        dist = DEFAULT_DIST_M
        notes.append("mesafe yazılmadı → 1 km varsayıldı")

    times = [f"{int(h):02d}:{mm}" for h, mm in _TIME.findall(raw) if int(h) < 24 and int(mm) < 60]
    t_from = t_to = None
    if len(times) >= 2:
        t_from, t_to = sorted(times[:2], key=parse_hhmm)
    elif len(times) == 1:
        if re.search(r"once|kadar", words):
            t_to = times[0]
        else:
            t_from = times[0]

    return AlertRule(vehicle=vehicle, max_dist_m=dist, zone=zone, time_from=t_from, time_to=t_to,
                     circling_only=circling), notes


def parse_rule_llm(text: str, client=None) -> tuple[AlertRule, list[str]]:
    """LLM ile çeviri: çıktı rule_from_dict ile doğrulanır (bilinmeyen tip/bölge/saat → hata)."""
    from backend.engine.llm.client import get_client
    from backend.engine.llm.prompt_loader import render

    prompt = render("alert_rule", zones=", ".join(z.name for z in get_context().repo.zones))
    result = (client or get_client()).chat(
        [{"role": "system", "content": prompt.text}, {"role": "user", "content": text}],
        response_format={"type": "json_object"}, reasoning_effort="low", max_tokens=2000, purpose="alert_rule")
    data = result.json()
    if not isinstance(data, dict):
        raise ValueError("LLM çıktısı JSON nesnesi değil")
    notes = [str(n) for n in data.get("notes") or [] if str(n).strip()][:3]
    return rule_from_dict(data), notes


def parse(text: str) -> tuple[AlertRule, list[str], str]:
    """Kural metni → (kural, notlar, "llm" | "kural"). LLM hatası akışı durdurmaz: kural ayrıştırıcıya düşer."""
    from backend.config import settings
    if settings.llm.enabled:
        try:
            rule, notes = parse_rule_llm(text)
            return rule, notes, "llm"
        except Exception as e:     # bütçe freni, ağ hatası, geçersiz çıktı...
            rule, notes = parse_rule(text)
            return rule, notes + [f"LLM çevirisi kullanılamadı ({type(e).__name__}); kural ayrıştırıcı kullanıldı"], "kural"
    rule, notes = parse_rule(text)
    return rule, notes, "kural"


def _window(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    a, b = re.split(r"\s*[–-]\s*", text)
    return parse_hhmm(a), parse_hhmm(b)


def backtest(rule: AlertRule, ctx=None) -> dict:
    """Kuralı tüm hareket kayıtları üzerinde işletir. Her araç için ilk tetiklenme anı, en yakın geçiş ve
    aracın ilk fotoğrafından kaç dakika önce uyarı verilebileceği."""
    ctx = ctx or get_context()
    repo, base = ctx.repo, ctx.repo.base
    t0 = parse_hhmm(rule.time_from) if rule.time_from else 0
    t1 = parse_hhmm(rule.time_to) if rule.time_to else 24 * 60
    want = VEHICLES[rule.vehicle]
    hits, any_total, unlabeled = [], 0, 0
    for tr in repo.tracks():
        k = ctx.kinematics[tr.id]
        win = _window(k.circling_window) if rule.circling_only else None
        if rule.circling_only and win is None:
            continue
        inside = []
        for p in tr.points:
            if not t0 <= p.t <= t1 or (win and not win[0] <= p.t <= win[1]):
                continue
            d = dist_to_base_m(base, p.lat, p.lon)
            if rule.max_dist_m is not None and d > rule.max_dist_m:
                continue
            if rule.zone and nearest_zone(p.lat, p.lon, repo.zones)[0].name != rule.zone:
                continue
            inside.append((p, d))
        if not inside:
            continue
        any_total += 1
        label = ctx.label_of_track(tr.id)
        if want is not None:
            if label is None:
                unlabeled += 1
                continue
            if label not in want:
                continue
        first, first_d = inside[0]
        near, near_d = min(inside, key=lambda x: x[1])
        last = tr.points[-1]
        hits.append({
            "track_id": tr.id, "label": label, "image_id": tr.image_id,
            "trigger_time": first.time, "trigger_dist_m": round(first_d),
            "min_dist_m": round(near_d), "min_time": near.time,
            "zone": nearest_zone(first.lat, first.lon, repo.zones)[0].name,
            "inside_min": 5 * len(inside),
            "photo_time": fmt_hhmm(tr.end_min), "photo_dist_m": round(dist_to_base_m(base, last.lat, last.lon)),
            "lead_min": tr.end_min - first.t,
            "circling": f"{k.circling_window}, ~{k.circling_radius_m:.0f} m" if k.circling else None,
            "consistent_approach": k.consistent_approach,
        })
    hits.sort(key=lambda h: (h["trigger_time"], h["track_id"]))
    leads = [h["lead_min"] for h in hits if h["lead_min"] > 0]
    by_label: dict[str, int] = {}
    for h in hits:
        by_label[h["label"] or "etiketsiz"] = by_label.get(h["label"] or "etiketsiz", 0) + 1
    return {
        "rule": asdict(rule), "rule_text": rule.describe(),
        "total": len(hits), "any_vehicle_total": any_total, "unlabeled": unlabeled, "by_label": by_label,
        "median_lead_min": statistics.median(leads) if leads else None,
        "hits": hits,
    }
