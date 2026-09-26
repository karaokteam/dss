"""Risk eşikleri — her step kendi bölümüne yazar, bölümler arasındaki boş satırları koruyun.

Açık konu: OI-RSK-1
"""

# SON-2 · skor → seviye alt sınırları (büyükten küçüğe kontrol edilir)
RISK_LEVELS = {"CRITICAL": 70, "HIGH": 45, "MEDIUM": 20, "LOW": 0}

# RSK-1 · konum
DISTANCE_CRITICAL_M = 1000

# RSK-2 · hareket
ETA_CRITICAL_MIN = 10

# RSK-3 · raporlar
