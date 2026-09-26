"""LLM'e verilen tool tanımları (OpenAI function-calling formatı)."""
import copy
from dss.schemas import Decision


def inline_refs(schema: dict) -> dict:
    """Pydantic $defs/$ref'lerini açar. Bazı gateway/model kombinasyonları $ref'i
    desteklemez; düz şema en güvenli yol."""
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            return {k: walk(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(schema)


def fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


# ── Karar modu: tek araç, model kararı buradan teslim eder
SUBMIT_ASSESSMENT = {"type": "function", "function": {
    "name": "submit_assessment",
    "description": "Görüntü için nihai değerlendirmeyi teslim et. Her rapora hüküm ver, "
                   "her iddiaya kanıt kimliği ile atıf yap.",
    "parameters": inline_refs(Decision.model_json_schema())}}

INSPECT_VEHICLE = fn(
    "inspect_vehicle",
    "Tespit edilen aracın kırpılmış görüntüsüne bakıp görsel bir soruyu yanıtlar "
    "(renk, yük durumu, üzeri örtülü mü, truck/bus ayrımı). Yalnızca rapor görsel bir "
    "nitelik iddia ediyorsa veya sınıf belirsizse kullan.",
    {"det_id": {"type": "string"}, "question": {"type": "string"}}, ["det_id", "question"])

DECISION_TOOLS = [INSPECT_VEHICLE, SUBMIT_ASSESSMENT]

# ── Sohbet modu
CHAT_TOOLS = [
    fn("list_images", "Tüm görüntülerin id, çekim saati ve bölgesini listeler."),
    fn("get_assessment", "Bir görüntünün (cache'lenmiş) nihai değerlendirmesini döner.",
       {"image_id": {"type": "string"}}, ["image_id"]),
    fn("get_evidence", "Bir görüntünün kanıt paketini döner (tespit, hareket, rapor kontrolleri).",
       {"image_id": {"type": "string"}}, ["image_id"]),
    fn("track_motion", "Bir track'in 2 saatlik hareket özeti.",
       {"track_id": {"type": "string"}}, ["track_id"]),
    fn("search_reports", "Raporları bölge adı ve/veya saat aralığına göre arar.",
       {"zone": {"type": "string"}, "time_from": {"type": "string"},
        "time_to": {"type": "string"}}),
    fn("scan_all", "Tüm görüntüleri dikkat seviyesine göre sıralı özetler."),
    INSPECT_VEHICLE,
]
