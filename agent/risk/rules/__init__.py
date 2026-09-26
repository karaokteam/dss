"""Bu klasördeki her .py dosyası otomatik yüklenir; içindeki @rule fonksiyonları kaydolur."""

import importlib
import pkgutil

for _m in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_m.name}")
