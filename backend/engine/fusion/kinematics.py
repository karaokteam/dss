"""Track'ten hareket özellikleri.

Veri düzeni: araçlar bir noktada bekler (ardışık nokta titremesi < 20 m), sonra 5 dakikada 1–3 km sıçrar.
Bu yüzden her 5 dakikalık adım "hareket" ya da "bekleme" olarak sınıflanır; hız ve yön tek adımdan değil
pencereden okunur (PDF: "Hız ve yönü tek bir adımdan değil, kaydın tamamından okuyun").
Tüm mesafeler kuş uçuşudur.
"""

from __future__ import annotations

from backend.config import KinematicsConfig, settings
from backend.engine.geo.geometry import angle_diff_deg, bearing_deg, dist_to_base_m, distance_m
from backend.engine.models import Base, Kinematics, Segment, Track, TrackPoint, fmt_hhmm


def compute_kinematics(track: Track, base: Base, at: int | None = None,
                       cfg: KinematicsConfig | None = None) -> Kinematics | None:
    """Track'in `at` anındaki (varsayılan: son nokta) hareket özeti. `at` kayıt dışındaysa None.

    Rapor doğrulamada rapor saatindeki durumu almak için `at=rapor_saati` verilir;
    o andan sonraki noktalar hesaba katılmaz.
    """
    cfg = cfg or settings.kinematics
    at = track.end_min if at is None else at
    pts = track.points_until(at)
    if not pts or pts[-1].t != at:
        return None

    end = pts[-1]
    dist_base = [dist_to_base_m(base, p.lat, p.lon) for p in pts]
    steps = [distance_m(a.lat, a.lon, b.lat, b.lon) for a, b in zip(pts, pts[1:])]
    is_move = [s > cfg.move_step_m for s in steps]

    # ---- hareket sayıları
    radial_steps = [dist_base[i + 1] - dist_base[i] for i in range(len(steps))]
    move_idx = [i for i, m in enumerate(is_move) if m]
    approach_moves = sum(radial_steps[i] < 0 for i in move_idx)
    recede_moves = sum(radial_steps[i] > 0 for i in move_idx)

    # ---- mevcut duruş: sondan geriye, hareket adımına kadar
    stationary_min = 0
    for i in range(len(steps) - 1, -1, -1):
        if is_move[i]:
            break
        stationary_min += pts[i + 1].t - pts[i].t
    total_stationary_min = sum(pts[i + 1].t - pts[i].t for i, m in enumerate(is_move) if not m)

    # ---- hız penceresi
    w_start = _point_at_or_before(pts, at - cfg.speed_window_min)
    w_idx = pts.index(w_start)
    window_min = at - w_start.t
    window_path = sum(steps[w_idx:])
    speed = window_path / (window_min * 60) if window_min else 0.0
    disp_speed = (distance_m(w_start.lat, w_start.lon, end.lat, end.lon) / (window_min * 60)
                  if window_min else 0.0)

    # ---- radyal pencere (pencere tam dolmuyorsa yaklaşma iddiası kurulmaz)
    r_start = track.position_at(at - cfg.radial_window_min)
    if r_start is not None:
        dist_ago = dist_to_base_m(base, r_start.lat, r_start.lon)
        radial_change = dist_base[-1] - dist_ago
        radial_speed = radial_change / (cfg.radial_window_min * 60)
    else:
        radial_change = radial_speed = dist_ago = None

    motion = _motion(radial_change, stationary_min, at - pts[0].t, cfg)

    # ETA yalnızca hâlâ hareket ediyorsa anlamlı; uzun süredir duran araç için ortalama hız yanıltır
    eta = None
    if motion == "approaching" and stationary_min < cfg.speed_window_min:
        eta = round(dist_base[-1] / -radial_speed / 60, 1)

    # ---- son hareketin yönü
    heading = heading_diff = None
    if move_idx:
        i = move_idx[-1]
        a, b = pts[i], pts[i + 1]
        heading = bearing_deg(a.lat, a.lon, b.lat, b.lon)
        heading_diff = angle_diff_deg(heading, bearing_deg(a.lat, a.lon, base.lat, base.lon))

    path = sum(steps)
    net = distance_m(pts[0].lat, pts[0].lon, end.lat, end.lon)
    tortuosity = round(path / net, 2) if move_idx and net > cfg.stationary_radius_m else None

    return Kinematics(
        track_id=track.id, at=fmt_hhmm(at), lat=end.lat, lon=end.lon,
        state="moving" if is_move and is_move[-1] else "stationary",
        motion=motion,
        dist_to_base_m=round(dist_base[-1], 1),
        dist_to_base_window_ago_m=_r(dist_ago),
        dist_to_base_start_m=round(dist_base[0], 1),
        min_dist_to_base_m=round(min(dist_base), 1),
        radial_change_window_m=_r(radial_change),
        radial_speed_mps=_r(radial_speed, 2),
        speed_mps=round(speed, 2),
        displacement_speed_mps=round(disp_speed, 2),
        eta_min=eta,
        stationary_min=stationary_min,
        total_stationary_min=total_stationary_min,
        heading_deg=_r(heading),
        heading_to_base_diff_deg=_r(heading_diff),
        moves=len(move_idx),
        approach_moves=approach_moves,
        recede_moves=recede_moves,
        consistent_approach=(len(move_idx) >= cfg.consistent_approach_min_moves and recede_moves == 0),
        path_length_m=round(path, 1),
        net_displacement_m=round(net, 1),
        tortuosity=tortuosity,
        observed_min=at - pts[0].t,
        segments=_segments(pts, is_move, dist_base, steps),
    )


def track_state_at(track: Track, base: Base, t: int) -> Kinematics | None:
    """Rapor doğrulama için: aracın `t` anındaki durumu (yalnızca o ana kadarki kayıtla)."""
    return compute_kinematics(track, base, at=t)


# ---------------------------------------------------------------- yardımcılar

def _motion(radial_change: float | None, stationary_min: int, observed_min: int,
            cfg: KinematicsConfig) -> str:
    if stationary_min >= min(cfg.radial_window_min, observed_min):
        return "stationary"
    if radial_change is None:
        return "lateral"
    if radial_change <= -cfg.approach_net_m:
        return "approaching"
    if radial_change >= cfg.approach_net_m:
        return "receding"
    return "lateral"


def _segments(pts: tuple[TrackPoint, ...], is_move: list[bool], dist_base: list[float],
              steps: list[float]) -> tuple[Segment, ...]:
    """Ardışık aynı tip adımları birleştirip bekle/hareket bölümleri çıkarır."""
    segs: list[Segment] = []
    i = 0
    while i < len(is_move):
        j = i
        while j + 1 < len(is_move) and is_move[j + 1] == is_move[i]:
            j += 1
        kind = "move" if is_move[i] else "stop"
        segs.append(Segment(
            kind=kind, start=fmt_hhmm(pts[i].t), end=fmt_hhmm(pts[j + 1].t),
            duration_min=pts[j + 1].t - pts[i].t,
            distance_m=round(sum(steps[i:j + 1]), 1) if kind == "move" else 0.0,
            radial_change_m=round(dist_base[j + 1] - dist_base[i], 1),
        ))
        i = j + 1
    return tuple(segs)


def _point_at_or_before(pts: tuple[TrackPoint, ...], t: int) -> TrackPoint:
    """t anındaki ya da ondan önceki en geç nokta; kayıt t'den sonra başlıyorsa ilk nokta."""
    candidates = [p for p in pts if p.t <= t]
    return candidates[-1] if candidates else pts[0]


def _r(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


# ---------------------------------------------------------------- eşzamanlı hareket (koordinasyon)

def move_steps(track: Track, base: Base, cfg: KinematicsConfig | None = None) -> dict[int, float]:
    """Hareket adımlarının bitiş anı → o adımdaki üsse uzaklık değişimi (negatif = yaklaştı)."""
    cfg = cfg or settings.kinematics
    out = {}
    for a, b in zip(track.points, track.points[1:]):
        if distance_m(a.lat, a.lon, b.lat, b.lon) > cfg.move_step_m:
            out[b.t] = dist_to_base_m(base, b.lat, b.lon) - dist_to_base_m(base, a.lat, a.lon)
    return out


def same_direction_sync(a: dict[int, float], b: dict[int, float]) -> int:
    """İki aracın aynı 5 dakikalık adımda, üsse göre aynı yöne yaptığı hareket sayısı."""
    return sum(1 for t in a if t in b and a[t] * b[t] > 0)


def sync_chance_table(tracks_by_image: list[list[Track]], base: Base) -> dict[int, float]:
    """Tesadüf referansı: aynı görüntüde biten tüm track çiftlerinde "≥k aynı yönlü eşzamanlı hareket" oranı."""
    from itertools import combinations
    counts = []
    for tracks in tracks_by_image:
        moves = {t.id: move_steps(t, base) for t in tracks}
        counts += [same_direction_sync(moves[a.id], moves[b.id]) for a, b in combinations(tracks, 2)]
    n = len(counts) or 1
    return {k: round(sum(c >= k for c in counts) / n, 3) for k in range(0, 25)}
