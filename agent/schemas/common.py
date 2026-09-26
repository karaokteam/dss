from typing import Literal

VehicleClass = Literal["car", "van", "truck", "bus"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
LatLon = tuple[float, float]


def hhmm_to_min(t: str) -> int:
    """'14:10' -> 850"""
    h, m = t.split(":")
    return int(h) * 60 + int(m)
