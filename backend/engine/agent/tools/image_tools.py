"""Görsel teyit: görüntünün bir bölümünü kırpıp vision modeline sorar.

Neden tool: Renk ("mavi araç dost devriye"), yük/örtü ("üzeri örtülü ağır araç"), tip şüphesi (alt etiketler)
ve kaçırılmış araç (tespitsiz track) soruları görsel yorum gerektirir; neyin sorulacağına ve hangi araca
bakılacağına agent karar verir. Her çağrı bir LLM isteğidir (önbellekli).
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from backend.config import settings
from backend.engine.agent.tools import tool
from backend.engine.analysis.consistency import get_context
from backend.engine.geo.geometry import latlon_to_pixel

_MIN_CROP_PX = 160      # hedef etrafında bırakılan en küçük bağlam
_CONTEXT_FACTOR = 4     # kırpma = kutu boyutu × bu katsayı
_MIN_SIDE_PX = 384      # vision için büyütme hedefi


def _target_box(image_id: str, vehicle_id: str | None, lat: float | None, lon: float | None):
    """(x, y, w, h) kutu ya da (x, y, 0, 0) nokta; açıklama metni."""
    ctx = get_context()
    repo = ctx.repo
    img = repo.image(image_id)
    if vehicle_id:
        if vehicle_id.startswith("track:"):
            from backend.engine.analysis.dossier import _missed_candidates
            tr = repo.track(vehicle_id.split(":", 1)[1])
            if tr.image_id != image_id:
                raise ValueError(f"{tr.id} bu görüntüde bitmiyor ({tr.image_id})")
            cands = _missed_candidates(ctx, image_id, tr.last.lat, tr.last.lon)
            if cands:
                return cands[0].bbox_xywh, f"{vehicle_id} (eşik altı aday kutusu)"
            x, y = latlon_to_pixel(img, tr.last.lat, tr.last.lon)
            return (x, y, 0.0, 0.0), f"{vehicle_id} son konumu"
        det = repo.detection(vehicle_id)
        if det.image_id != image_id:
            raise ValueError(f"{vehicle_id} bu görüntüye ait değil ({det.image_id})")
        return det.bbox_xywh, f"{vehicle_id} ({det.label}, güven {det.confidence:.2f})"
    if lat is None or lon is None:
        raise ValueError("vehicle_id ya da lat+lon verilmeli")
    x, y = latlon_to_pixel(img, lat, lon)
    return (x, y, 0.0, 0.0), f"nokta {lat:.5f}, {lon:.5f}"


def render_crop(image_id: str, box: tuple[float, float, float, float]) -> tuple[bytes, tuple[int, int, int, int]]:
    """Hedefi kırmızıyla işaretlenmiş, büyütülmüş JPEG kırpması ve kırpma sınırları."""
    img_meta = get_context().repo.image(image_id)
    image = Image.open(img_meta.file).convert("RGB")
    W, H = image.size
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    if not (0 <= cx <= W and 0 <= cy <= H):
        raise ValueError("hedef görüntünün dışında")
    half = max(_MIN_CROP_PX, _CONTEXT_FACTOR * max(w, h)) / 2
    x0, y0 = int(max(0, cx - half)), int(max(0, cy - half))
    x1, y1 = int(min(W, cx + half)), int(min(H, cy + half))

    draw = ImageDraw.Draw(image)
    if w and h:
        pad = 3
        draw.rectangle([x - pad, y - pad, x + w + pad, y + h + pad], outline=(255, 0, 0), width=2)
    else:
        r = 12
        draw.line([cx - r, cy, cx - 4, cy], fill=(255, 0, 0), width=2)
        draw.line([cx + 4, cy, cx + r, cy], fill=(255, 0, 0), width=2)
        draw.line([cx, cy - r, cx, cy - 4], fill=(255, 0, 0), width=2)
        draw.line([cx, cy + 4, cx, cy + r], fill=(255, 0, 0), width=2)

    crop = image.crop((x0, y0, x1, y1))
    scale = max(1.0, _MIN_SIDE_PX / min(crop.size))
    if scale > 1:
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=90)
    return buf.getvalue(), (x0, y0, x1, y1)


@tool
def inspect_image(image_id: str, question: str, vehicle_id: str | None = None,
                  lat: float | None = None, lon: float | None = None) -> dict:
    """Görüntünün hedef bölümünü kırpıp görsel olarak inceler ve soruyu yanıtlar (araç var mı, tipi,
    rengi, yükü/örtüsü). Renk veya yük içeren bir iddiayı, şüpheli bir tip etiketini ya da tespiti olmayan
    bir track'in (kaçırılmış araç) yerinde gerçekten araç olup olmadığını teyit etmek için kullan.
    Her çağrı bir görüntü analizi isteğidir; yalnızca sonucu kararını değiştirebilecekse çağır.

    Args:
        image_id: Görüntü kimliği, örn. "img_000267".
        question: Hedef hakkında kısa, somut soru, örn. "Bu araç mavi mi ve devriye aracına benziyor mu?".
        vehicle_id: Hedef araç: tespit kimliği ("img_000267_003") ya da tespitsiz track ("track:T0057").
        lat: vehicle_id yoksa hedef noktanın enlemi.
        lon: vehicle_id yoksa hedef noktanın boylamı.
    """
    from backend.engine.llm.client import LLMUnavailable, get_client, image_part
    from backend.engine.llm.prompt_loader import render

    box, target = _target_box(image_id, vehicle_id, lat, lon)
    data, crop = render_crop(image_id, box)
    try:
        client = get_client()
    except LLMUnavailable as e:
        return {"error": f"görsel analiz kullanılamıyor: {e}"}
    prompt = render("vision_inspect")
    result = client.chat(
        [{"role": "system", "content": prompt.text},
         {"role": "user", "content": [{"type": "text", "text": f"Hedef: {target}\nSoru: {question}"},
                                      image_part(data)]}],
        response_format={"type": "json_object"},
        reasoning_effort=settings.agent.vision_reasoning_effort, max_tokens=3000,
        purpose=f"vision:{image_id}:{vehicle_id or 'point'}",
    )
    try:
        answer = result.json()
    except ValueError:
        answer = {"answer": result.content.strip()[:500], "confidence": "low", "parse_error": True}
    return {"image_id": image_id, "target": target, "crop_px": list(crop), "result": answer}
