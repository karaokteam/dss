"""Birlikte hareket sınaması: verilen araçlar konvoy/koordineli grup mu, yoksa tesadüfen mi yan yana?

Neden tool: Hangi araçların birlikte değerlendirileceği bir hipotezdir (aynı görüntüde yan yana duran
kamyonlar, "3 araçlık konvoy" raporu, farklı bölgelerden aynı anda yaklaşan araçlar...). Agent hipotezini
kurar, hangi track'lerin karşılaştırılacağını seçer; tool 2 saatlik kayıt üzerinden sınar.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import combinations

from backend.config import settings
from backend.engine.agent.tools import tool
from backend.engine.analysis.consistency import get_context
from backend.engine.fusion.kinematics import move_steps, same_direction_sync, sync_chance_table
from backend.engine.geo.geometry import distance_m


def _moves(track) -> dict[int, float]:
    return move_steps(track, get_context().repo.base)


def _same_direction_sync(a: dict[int, float], b: dict[int, float]) -> int:
    return same_direction_sync(a, b)


@lru_cache(maxsize=1)
def _chance_table() -> dict[int, float]:
    repo = get_context().repo
    return sync_chance_table([repo.tracks_for_image(i.id) for i in repo.images()], repo.base)


@tool
def co_movement(track_ids: list[str]) -> dict:
    """Verilen araçların (track) 2 saatlik kayıtlarını karşılaştırır: ortak zamanlarda aralarındaki mesafe,
    aynı 5 dakikalık adımda birlikte hareket edip etmedikleri ve üsse göre aynı yöne gidip gitmedikleri.
    Konvoy, koordineli yaklaşma veya birlikte bekleyen grup hipotezini sınamak için kullan.

    Args:
        track_ids: Karşılaştırılacak track kimlikleri (2–6 adet), örn. ["T0019", "T0117"].
    """
    cfg = settings.agent
    ids = list(dict.fromkeys(track_ids))
    if not 2 <= len(ids) <= cfg.co_move_max_tracks:
        return {"error": f"2 ile {cfg.co_move_max_tracks} arasında farklı track verilmeli"}
    repo = get_context().repo
    tracks = {t: repo.track(t) for t in ids}
    moves = {t: _moves(tr) for t, tr in tracks.items()}

    pairs = []
    for a, b in combinations(ids, 2):
        ta, tb = tracks[a], tracks[b]
        common = sorted({p.t for p in ta.points} & {p.t for p in tb.points})
        if not common:
            pairs.append({"tracks": [a, b], "relation": "no_overlap", "detail": "ortak zaman yok"})
            continue
        dists = [distance_m(ta.position_at(t).lat, ta.position_at(t).lon,
                            tb.position_at(t).lat, tb.position_at(t).lon) for t in common]
        sync = [t for t in moves[a] if t in moves[b]]
        same_dir = _same_direction_sync(moves[a], moves[b])
        close_all = max(dists) <= cfg.co_move_radius_m
        if close_all and len(sync) >= cfg.co_move_min_sync:
            relation = "moving_together"
        elif close_all and not moves[a] and not moves[b]:
            relation = "waiting_together"
        elif dists[-1] <= cfg.co_move_radius_m and same_dir >= cfg.converge_min_sync:
            relation = "converged_in_step"      # ayrı yerlerden, aynı anlarda aynı yöne hareketle buluştular
        elif dists[-1] <= cfg.co_move_radius_m:
            relation = "met_at_end"             # sonunda yan yana, hareketleri bağımsız
        else:
            relation = "independent"
        pairs.append({
            "tracks": [a, b],
            "relation": relation,
            "common_window": f"{repo.track(a).position_at(common[0]).time}–{repo.track(a).position_at(common[-1]).time}",
            "dist_m": {"min": round(min(dists)), "max": round(max(dists)), "end": round(dists[-1])},
            "synchronous_moves": len(sync),
            "same_direction_moves": same_dir,
            "chance_rate": _chance_table().get(same_dir, 0.0),
        })

    per_track = {t: {"moves": len(m), "toward_base": sum(v < 0 for v in m.values()),
                     "move_times": [repo.track(t).position_at(x).time for x in sorted(m)]}
                 for t, m in moves.items()}
    return {
        "pairs": pairs,
        "chance_rate_note": ("chance_rate: aynı görüntüde biten rastgele iki araçta en az bu kadar aynı yönlü "
                             "eşzamanlı hareketin tesadüfen görülme oranı. DİKKAT: çok sayıda çift denendiğinde "
                             "düşük oranlar da tesadüfen çıkar (veride aynı görüntüdeki 580 çiftin ~%5'i ≥4 "
                             "eşzamanlı hareket gösterir). Koordinasyon iddiası için başka kanıtla (rapor, tip, "
                             "tutarlı yaklaşma, konvoy) desteklenmeli."),
        "tracks": per_track,
        "relations": {
            "moving_together": f"tüm ortak sürede ≤ {cfg.co_move_radius_m:.0f} m ve ≥ {cfg.co_move_min_sync} aynı anda hareket (konvoy)",
            "waiting_together": "hep yakın, ikisi de hiç hareket etmemiş",
            "converged_in_step": f"ayrı yerlerden en az {cfg.converge_min_sync} kez aynı anda aynı yöne hareketle sonunda buluşmuşlar",
            "met_at_end": "sonunda yakınlar ama hareketleri bağımsız",
            "independent": "ilişki yok",
        },
    }
