"""GLM ayarları. Görev: LLM-1 · Kaynak: data/raw/gorev_tanimi.pdf · Açık konu: OI-LLM-2

Tek model var (glm-5.3-flash). "Hızlı / derin" ayrımı reasoning_effort ile yapılır.
Anahtar .env'den okunur, takıma ayrıca iletilecek.
"""

import os

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_BASE_URL = os.getenv(
    "GLM_BASE_URL", "https://berriailitellm-databasev1826rc3-production-d691.up.railway.app/v1"
)
GLM_MODEL = os.getenv("GLM_MODEL", "glm-5.3-flash")

LLM_EFFORT_FAST = "low"  # rapor çıkarımı, kısa işler (~10-15 sn)
LLM_EFFORT_SMART = "high"  # brief, sohbet
LLM_MAX_TOKENS = 4000  # düşünme de buna dahil; düşük verilirse content boş döner
LLM_TIMEOUT_S = 60
LLM_MAX_RETRIES = 5  # 429 / 5xx
LLM_MAX_CONCURRENCY = 4  # gateway sınırı: aynı anda 4 istek, 60 istek/dk
LLM_MAX_TOOL_TURNS = 10  # sohbet döngüsü üst sınırı, bütçeyi korur
LLM_USE_CACHE = True
