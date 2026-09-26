"""Modüller arası sözleşmeler — alan başına bir dosya.

Kullanım: `from agent.schemas import Detection, VehicleFinding`
Koordinatlar her yerde (lat, lon); zamanlar "HH:MM" (tek gün, veri 08:00–15:30 arası).
Mevcut bir alanı değiştirmek/silmek sözleşme kırar → CONTRIBUTING §5.
Yeni alan (varsayılan değerli) veya yeni sınıf eklemek serbesttir.
"""

from agent.schemas.common import *  # noqa: F403
from agent.schemas.detection import *  # noqa: F403
from agent.schemas.geo import *  # noqa: F403
from agent.schemas.inputs import *  # noqa: F403
from agent.schemas.pipeline import *  # noqa: F403
from agent.schemas.reports import *  # noqa: F403
from agent.schemas.risk import *  # noqa: F403
from agent.schemas.tracks import *  # noqa: F403
