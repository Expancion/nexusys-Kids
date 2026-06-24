from flask import Flask, request
from flask_babel import get_locale, get_timezone

from .config import Config
from .extensions import babel, db, migrate
from .modules import register_modules

SUPPORTED_LANGS = ('cs', 'en')


def _get_locale():
    lang = request.cookies.get('lang')
    if lang and lang in SUPPORTED_LANGS:
        return lang
    # Fall back to admin-chosen default (set during setup wizard)
    try:
        from .models import SystemConfig
        default = SystemConfig.get('default_lang', 'cs')
        return default if default in SUPPORTED_LANGS else 'cs'
    except Exception:
        return 'cs'


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config['BABEL_DEFAULT_LOCALE'] = 'cs'
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'

    db.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app, locale_selector=_get_locale)
    app.jinja_env.globals.update(get_locale=get_locale, get_timezone=get_timezone)
    register_modules(app)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "nexusys_home"}

    return app
