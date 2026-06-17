from flask import Flask

from .config import Config
from .extensions import db, migrate
from .modules import register_modules


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    register_modules(app)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "nexusys_home"}

    return app
