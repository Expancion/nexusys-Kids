from flask import Flask

from .admin.routes import admin_bp
from .api.routes import api_bp
from .games.routes import games_bp
from .main.routes import main_bp
from .videos.routes import videos_bp


def register_modules(app: Flask) -> None:
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(videos_bp)
    app.register_blueprint(games_bp)
    app.register_blueprint(api_bp)
