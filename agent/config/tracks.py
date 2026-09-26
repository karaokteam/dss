"""Eşleştirme ve hareket eşikleri. Görevler: TRK-1, TRK-2 · Açık konu: OI-TRK-2

Kaynak (gorev_tanimi.pdf): her track, ait olduğu görüntünün çekim anında biter → time == capture_time.
Tespit hataları birkaç metre sapma yaratır; referans örnekte eşleşme mesafesi ~2,5 m.
"""

# TRK-1 · eşleştirme
MATCH_MAX_DIST_M = 15.0
MATCH_TIME_TOLERANCE_MIN = 0

# TRK-2 · hareket
TRACK_STEP_MIN = 5  # tracks.csv 5 dakikalık adımlarla, her track 25 nokta (2 saat)
STOP_SPEED_MPS = 0.5
APPROACH_WINDOW_MIN = 30
