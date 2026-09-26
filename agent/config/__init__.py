"""Ayarlar — alan başına bir dosya, her alanın sahibi sadece kendi dosyasını düzenler.

Kullanım: `from agent import config; config.MATCH_MAX_DIST_M`
Tüm isimler buraya düz olarak aktarılır → isimler dosyalar arasında benzersiz olmalı.
Eşik değerleri yer tutucudur; kalibrasyon kararları PROGRESS.md'de kayıtlı.
"""

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from agent.config.detection import *  # noqa: E402,F403
from agent.config.llm import *  # noqa: E402,F403
from agent.config.paths import *  # noqa: E402,F403
from agent.config.risk import *  # noqa: E402,F403
from agent.config.tracks import *  # noqa: E402,F403
