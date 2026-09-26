"""Ham veri dosyalarının tipleri. Step 0 (hazır)"""

from pydantic import BaseModel

from agent.schemas.common import LatLon


class Corners(BaseModel):
    top_left: LatLon
    top_right: LatLon
    bottom_left: LatLon
    bottom_right: LatLon


class ImageMeta(BaseModel):
    image_id: str
    width_px: int
    height_px: int
    capture_time: str
    corner_coordinates: Corners


class Zone(BaseModel):
    name: str
    center: LatLon


class Base(BaseModel):
    name: str
    lat: float
    lon: float


class ZonesFile(BaseModel):
    base: Base
    zones: list[Zone]


class TrackPoint(BaseModel):
    track_id: str
    time: str
    lat: float
    lon: float


class FieldReport(BaseModel):
    report_id: str  # dosyadaki sıra, loaders atar: "R000"
    time: str
    source: str  # "official" | "third_party" | ...
    text: str
