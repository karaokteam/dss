"""Bellekte indeksli, salt okunur veri deposu. Diğer modüller veriye yalnızca buradan erişir."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from functools import lru_cache

from backend.config import Paths, settings
from backend.engine.data.loaders import load_dataset, load_raw_predictions
from backend.engine.models import (
    Base, Dataset, Detection, ImageMeta, RawPrediction, Report, Source, Track, TrackPoint, Zone,
)


class Repository:
    def __init__(self, dataset: Dataset, raw_predictions_path=None):
        self._raw_path = raw_predictions_path
        self._raw: dict[str, tuple[RawPrediction, ...]] | None = None
        self.dataset = dataset
        self.base: Base = dataset.base
        self.zones: tuple[Zone, ...] = dataset.zones
        self.warnings = dataset.warnings

        self._images = {i.id: i for i in dataset.images}
        self._detections = {d.id: d for d in dataset.detections}
        self._tracks = {t.id: t for t in dataset.tracks}
        self._reports = {r.id: r for r in dataset.reports}

        self._dets_by_image: dict[str, list[Detection]] = defaultdict(list)
        for d in dataset.detections:
            self._dets_by_image[d.image_id].append(d)

        self._tracks_by_end: dict[int, list[Track]] = defaultdict(list)
        self._tracks_by_image: dict[str, list[Track]] = defaultdict(list)
        for t in dataset.tracks:
            self._tracks_by_end[t.end_min].append(t)
            if t.image_id:
                self._tracks_by_image[t.image_id].append(t)

        self._reports_sorted = sorted(dataset.reports, key=lambda r: (r.t, r.index))
        self._report_times = [r.t for r in self._reports_sorted]

    # ------------------------------------------------------------ görüntüler
    def images(self) -> list[ImageMeta]:
        return list(self.dataset.images)

    def image(self, image_id: str) -> ImageMeta:
        return self._get(self._images, image_id, "görüntü")

    def detections_for(self, image_id: str) -> list[Detection]:
        self.image(image_id)
        return list(self._dets_by_image.get(image_id, []))

    def detection(self, detection_id: str) -> Detection:
        return self._get(self._detections, detection_id, "tespit")

    def raw_predictions(self, image_id: str) -> tuple[RawPrediction, ...]:
        """Eşik altı ham tahminler (tembel yüklenir; dosya yoksa boş)."""
        self.image(image_id)
        if self._raw is None:
            self._raw = load_raw_predictions(self._raw_path) if self._raw_path else {}
        return self._raw.get(image_id, ())

    # ------------------------------------------------------------ track'ler
    def tracks(self) -> list[Track]:
        return list(self.dataset.tracks)

    def track(self, track_id: str) -> Track:
        return self._get(self._tracks, track_id, "track")

    def tracks_for_image(self, image_id: str) -> list[Track]:
        self.image(image_id)
        return list(self._tracks_by_image.get(image_id, []))

    def tracks_ending_at(self, t: int) -> list[Track]:
        return list(self._tracks_by_end.get(t, []))

    def track_at(self, track_id: str, t: int) -> TrackPoint | None:
        """t anındaki konum. Izgara dışındaki anlarda doğrusal enterpolasyon; kayıt aralığı dışında None."""
        return self.track(track_id).position_at(t)

    def track_points_between(self, track_id: str, t0: int, t1: int) -> list[TrackPoint]:
        return [p for p in self.track(track_id).points if t0 <= p.t <= t1]

    def tracks_active_at(self, t: int) -> list[tuple[Track, TrackPoint]]:
        """t anında kaydı olan tüm track'ler ve o andaki konumları."""
        out = []
        for tr in self.dataset.tracks:
            p = self.track_at(tr.id, t)
            if p is not None:
                out.append((tr, p))
        return out

    # ------------------------------------------------------------ raporlar
    def reports(self) -> list[Report]:
        return list(self._reports_sorted)

    def report(self, report_id: str) -> Report:
        return self._get(self._reports, report_id, "rapor")

    def reports_between(self, t0: int, t1: int, source: Source | None = None) -> list[Report]:
        i = bisect_left(self._report_times, t0)
        out = []
        for r in self._reports_sorted[i:]:
            if r.t > t1:
                break
            if source is None or r.source == source:
                out.append(r)
        return out

    # ------------------------------------------------------------ yardımcı
    @staticmethod
    def _get(index: dict, key: str, kind: str):
        try:
            return index[key]
        except KeyError:
            raise KeyError(f"Bilinmeyen {kind}: {key}") from None


def load_repository(paths: Paths | None = None) -> Repository:
    paths = paths or settings.paths
    return Repository(load_dataset(paths), raw_predictions_path=paths.low_conf_predictions)


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    """Uygulama genelinde tek örnek (API ve CLI bunu kullanır)."""
    return load_repository()
