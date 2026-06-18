import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from .extensions import db


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=True)


class KioskTile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(10), nullable=False, default="🌐")
    category = db.Column(db.String(40), nullable=False, default="web")
    color = db.Column(db.String(120), nullable=False, default="linear-gradient(135deg,#3b82f6,#2563eb)")
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class VideoCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(10), nullable=False, default="🎬")
    color = db.Column(db.String(120), nullable=False, default="linear-gradient(135deg,#ef4444,#b91c1c)")
    sort_order = db.Column(db.Integer, default=0)
    videos = db.relationship("KioskVideo", backref="category", lazy="dynamic",
                             cascade="all, delete-orphan")


class KioskVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    youtube_id = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("video_category.id"), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    price = db.Column(db.Integer, nullable=True)  # None = use child.video_cost

    price_rules = db.relationship("VideoPriceRule", backref="video", lazy="dynamic",
                                  cascade="all, delete-orphan")

    @property
    def embed_url(self):
        return f"https://www.youtube.com/embed/{self.youtube_id}?rel=0&modestbranding=1&autoplay=1"

    @property
    def thumb_url(self):
        return f"https://img.youtube.com/vi/{self.youtube_id}/mqdefault.jpg"


class VideoPriceRule(db.Model):
    """Time-based price override for a video (e.g. fairy tale is free 19:00–20:30)."""
    __tablename__ = "video_price_rule"
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey("kiosk_video.id", ondelete="CASCADE"), nullable=False)
    time_from = db.Column(db.Time, nullable=False)
    time_to = db.Column(db.Time, nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)


class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    avatar_icon = db.Column(db.String(10), nullable=False, default="🧒")
    avatar_color = db.Column(db.String(120), nullable=False,
                             default="linear-gradient(135deg,#3b82f6,#1d4ed8)")
    points = db.Column(db.Integer, nullable=False, default=0)
    video_cost = db.Column(db.Integer, nullable=False, default=10)
    daily_video_limit = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    devices = db.relationship("Device", backref="child", lazy="dynamic",
                              cascade="all, delete-orphan")
    transactions = db.relationship("PointTransaction", backref="child", lazy="dynamic",
                                   cascade="all, delete-orphan")
    watch_sessions = db.relationship("WatchSession", backref="child", lazy="dynamic",
                                     cascade="all, delete-orphan")
    chores = db.relationship("DailyChore", backref="child", lazy="dynamic",
                             cascade="all, delete-orphan")
    schedules = db.relationship("ChildSchedule", backref="child", lazy="dynamic",
                                cascade="all, delete-orphan")


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    device_key = db.Column(db.String(80), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    allowed = db.Column(db.Boolean, default=True, nullable=False)
    locked_message = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RewardTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(10), nullable=False, default="⭐")
    points_value = db.Column(db.Integer, nullable=False, default=10)
    active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class PointTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    delta = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    actor = db.Column(db.String(80), nullable=False, default="parent")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WatchSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("kiosk_video.id"), nullable=True)
    device_key = db.Column(db.String(80), nullable=True)
    points_spent = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)


class DailyChore(db.Model):
    """Weekly repeating chore assigned to a child for a specific weekday (0=Mon, 6=Sun)."""
    __tablename__ = "daily_chore"
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id", ondelete="CASCADE"), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0=Mon, 6=Sun
    chore_name = db.Column(db.String(100), nullable=False)
    chore_icon = db.Column(db.String(10), nullable=False, default="✅")
    points_reward = db.Column(db.Integer, nullable=False, default=5)
    active = db.Column(db.Boolean, nullable=False, default=True)

    completions = db.relationship("ChoreCompletion", backref="chore", lazy="dynamic",
                                  cascade="all, delete-orphan")


class ChoreCompletion(db.Model):
    """Records that a child completed a chore on a specific date."""
    __tablename__ = "chore_completion"
    id = db.Column(db.Integer, primary_key=True)
    chore_id = db.Column(db.Integer, db.ForeignKey("daily_chore.id", ondelete="CASCADE"), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id", ondelete="CASCADE"), nullable=False)
    completed_date = db.Column(db.Date, nullable=False)
    awarded_points = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChildSchedule(db.Model):
    """Time window during which the kiosk is locked for a child."""
    __tablename__ = "child_schedule"
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id", ondelete="CASCADE"), nullable=False)
    weekday = db.Column(db.Integer, nullable=True)  # None = every day
    locked_from = db.Column(db.Time, nullable=False)
    locked_to = db.Column(db.Time, nullable=False)
    message = db.Column(db.String(200), nullable=False, default="Kiosek je teď nedostupný.")


def extract_youtube_id(raw: str) -> str | None:
    raw = raw.strip()
    m = re.match(r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})", raw)
    if m:
        return m.group(1)
    parsed = urlparse(raw)
    if "youtube" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        m = re.match(r"/(?:embed|shorts)/([a-zA-Z0-9_-]{11})", parsed.path)
        if m:
            return m.group(1)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", raw):
        return raw
    return None
