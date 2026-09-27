"""Flask uygulaması.  Çalıştırma:  .venv/bin/flask --app backend.api.app run --port 5000"""

from __future__ import annotations

import threading

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException


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

    if warm:
        threading.Thread(target=_warm_up, daemon=True).start()
    return app


app = create_app()
