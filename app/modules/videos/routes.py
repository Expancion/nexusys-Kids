from flask import Blueprint, abort, render_template

from ...extensions import db
from ...models import KioskVideo, VideoCategory

videos_bp = Blueprint("videos", __name__, url_prefix="/videos")

DEFAULT_CATEGORIES = [
    {"name": "Pohádky",   "icon": "🧚", "color": "linear-gradient(135deg,#a855f7,#7e22ce)", "sort_order": 1},
    {"name": "Minecraft", "icon": "⛏️", "color": "linear-gradient(135deg,#22c55e,#15803d)", "sort_order": 2},
    {"name": "Příroda",   "icon": "🌿", "color": "linear-gradient(135deg,#14b8a6,#0f766e)", "sort_order": 3},
    {"name": "Hudba",     "icon": "🎵", "color": "linear-gradient(135deg,#f97316,#c2410c)", "sort_order": 4},
]


def _seed_categories():
    if VideoCategory.query.count() == 0:
        for c in DEFAULT_CATEGORIES:
            db.session.add(VideoCategory(**c))
        db.session.commit()


@videos_bp.get("/")
def index():
    _seed_categories()
    cats = VideoCategory.query.order_by(VideoCategory.sort_order, VideoCategory.id).all()
    return render_template("videos/index.html", categories=cats)


@videos_bp.get("/<int:cat_id>")
def category(cat_id):
    cat = db.get_or_404(VideoCategory, cat_id)
    videos = (
        KioskVideo.query
        .filter_by(category_id=cat_id, enabled=True)
        .order_by(KioskVideo.sort_order, KioskVideo.id)
        .all()
    )
    return render_template("videos/category.html", cat=cat, videos=videos)
