from flask import Blueprint, render_template

from ...extensions import db
from ...models import Child, KioskTile, KioskVideo, Note, VideoCategory

main_bp = Blueprint("main", __name__)

CATEGORIES = [
    {"key": "videa",      "name": "Videa",       "icon": "🎬"},
    {"key": "hry",        "name": "Hry",          "icon": "🎮"},
    {"key": "vzdelavani", "name": "Vzdělávání",   "icon": "📚"},
    {"key": "web",        "name": "Web",           "icon": "🌐"},
]

DEFAULT_TILES = [
    {"name": "Videa", "url": "/videos", "icon": "📺", "category": "videa",
     "color": "linear-gradient(135deg,#ef4444,#b91c1c)", "sort_order": 1},
]


def _seed_tiles():
    if KioskTile.query.count() == 0:
        for t in DEFAULT_TILES:
            db.session.add(KioskTile(**t))
        db.session.commit()


@main_bp.get("/")
def index():
    _seed_tiles()
    tiles = (
        KioskTile.query
        .filter_by(enabled=True)
        .order_by(KioskTile.sort_order, KioskTile.id)
        .all()
    )
    return render_template(
        "index.html",
        tiles=tiles,
        categories=CATEGORIES,
    )


@main_bp.get("/kiosk/<int:child_id>")
def child_kiosk(child_id):
    child = db.get_or_404(Child, child_id)
    cats = VideoCategory.query.order_by(VideoCategory.sort_order, VideoCategory.id).all()
    videos = (
        KioskVideo.query
        .filter_by(enabled=True)
        .order_by(KioskVideo.sort_order, KioskVideo.id)
        .all()
    )
    return render_template("kiosk/child.html", child=child, cats=cats, videos=videos)
