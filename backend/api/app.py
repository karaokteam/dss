"""Flask uygulaması.  Çalıştırma:  .venv/bin/flask --app backend.api.app run --port 5000

ui/dist derlenmişse arayüz de aynı porttan sunulur (tek konteyner dağıtımı: deploy/start.sh).
"""

from __future__ import annotations

import os
import threading

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, NotFound

from backend.config import ROOT_DIR


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def error(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def _warm_up() -> None:
    """Kanıt bağlamını ve 40 kanıt dosyasını arka planda hazırla (ilk istek hızlı olsun)."""
    from backend.engine import pipeline
    from backend.engine.analysis.consistency import get_context
    ctx = get_context()
    for img in ctx.repo.images():
        pipeline.build_dossier(img.id)


class _PathPrefix:
    """Yol tabanlı bağlantıda (Run:ai: /<proje>/<iş>/...) istek yolundaki öneki kaldırır; önek yoksa dokunmaz."""

    def __init__(self, wsgi, prefix: str):
        self.wsgi, self.prefix = wsgi, prefix

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix:          # sondaki "/" olmadan göreli yollar yanlış çözülür
            start_response("308 Permanent Redirect", [("Location", self.prefix + "/")])
            return [b""]
        if path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):]
        return self.wsgi(environ, start_response)


def _base_path() -> str:
    """BASE_PATH ya da Run:ai çalışma alanının /<proje>/<iş> adresi; ikisi de yoksa kök."""
    project, job = os.getenv("RUNAI_PROJECT"), os.getenv("RUNAI_JOB_NAME")
    path = os.getenv("BASE_PATH") or (f"{project}/{job}" if project and job else "")
    return "/" + path.strip("/") if path.strip("/") else ""


def _serve_ui(app: Flask) -> None:
    """Derlenmiş arayüzü (ui/dist) kökten sun; geliştirmede arayüzü Vite sunar."""
    dist = ROOT_DIR / "ui" / "dist"
    if not (dist / "index.html").is_file():
        return

    @app.get("/")
    @app.get("/<path:path>")
    def _ui(path: str = ""):
        if path.startswith("api/"):
            raise NotFound()
        return send_from_directory(dist, path if path and (dist / path).is_file() else "index.html")


def create_app(warm: bool = True) -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False
    app.json.ensure_ascii = False
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from backend.api.routes import analysis, images, meta, reports, tracks
    for bp in (meta.bp, images.bp, tracks.bp, reports.bp, analysis.bp):
        app.register_blueprint(bp, url_prefix="/api")

    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        return error(e.status, e.code, e.message)

    @app.errorhandler(KeyError)
    def _not_found(e: KeyError):
        return error(404, "not_found", str(e).strip("'\""))

    @app.errorhandler(ValueError)
    def _bad_request(e: ValueError):
        return error(400, "bad_request", str(e))

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        return error(e.code or 500, e.name.lower().replace(" ", "_"), e.description or e.name)

    @app.errorhandler(Exception)
    def _internal(e: Exception):
        app.logger.exception(e)
        return error(500, "internal_error", f"{type(e).__name__}: {e}")

    _serve_ui(app)
    if prefix := _base_path():
        app.wsgi_app = _PathPrefix(app.wsgi_app, prefix)

    if warm:
        threading.Thread(target=_warm_up, daemon=True).start()
    return app


app = create_app()
