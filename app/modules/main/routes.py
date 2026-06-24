import json
from datetime import date as date_cls, datetime as dt_cls, timedelta

from flask import Blueprint, make_response, redirect, render_template, request
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from ...extensions import db
from ...achievements import ACHIEVEMENTS
from ...models import (Child, ChildAchievement, ChildGoal, ChildSchedule,
                       ChoreCompletion, DailyChore, KioskTile, KioskVideo,
                       Note, PointTransaction, ShopReward, SystemConfig,
                       VideoCategory, WatchSession)

main_bp = Blueprint("main", __name__)

CATEGORIES = [
    {"key": "videa",      "name": "Videa",       "icon": "🎬"},
    {"key": "hry",        "name": "Hry",          "icon": "🎮"},
    {"key": "vzdelavani", "name": "Vzdělávání",   "icon": "📚"},
    {"key": "web",        "name": "Web",           "icon": "🌐"},
]

DEFAULT_TILES = [
    {"name": "Videa",    "url": "/videos",        "icon": "📺", "category": "videa",
     "color": "linear-gradient(135deg,#ef4444,#b91c1c)", "sort_order": 1},
    {"name": "Písmenka", "url": "/games/letters", "icon": "✏️", "category": "hry",
     "color": "linear-gradient(135deg,#8b5cf6,#6d28d9)", "sort_order": 10},
    {"name": "Čísla",    "url": "/games/numbers", "icon": "🔢", "category": "hry",
     "color": "linear-gradient(135deg,#f59e0b,#d97706)", "sort_order": 11},
]


def _compute_streak(child_id: int) -> int:
    d = date_cls.today()
    streak = 0
    while streak < 366:
        if ChoreCompletion.query.filter_by(child_id=child_id, completed_date=d).first():
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak


def _seed_tiles():
    changed = False
    for t in DEFAULT_TILES:
        if not KioskTile.query.filter_by(url=t["url"]).first():
            db.session.add(KioskTile(**t))
            changed = True
    if changed:
        db.session.commit()


@main_bp.route("/setup", methods=["GET", "POST"])
def setup():
    if SystemConfig.get("setup_complete") == "1":
        return redirect("/")
    error = None
    if request.method == "POST":
        lang = request.form.get("lang", "cs")
        if lang not in ("cs", "en"):
            lang = "cs"
        pw = request.form.get("password", "").strip()
        pw2 = request.form.get("password2", "").strip()
        if len(pw) < 6:
            error = {"cs": "Heslo musí mít alespoň 6 znaků.", "en": "Password must be at least 6 characters."}[lang]
        elif pw != pw2:
            error = {"cs": "Hesla se neshodují.", "en": "Passwords do not match."}[lang]
        else:
            SystemConfig.set("admin_password_hash", generate_password_hash(pw))
            SystemConfig.set("default_lang", lang)
            SystemConfig.set("setup_complete", "1")
            resp = make_response(redirect("/admin"))
            resp.set_cookie("lang", lang, max_age=365 * 24 * 3600, samesite="Lax")
            return resp
    return render_template("setup.html", error=error)


@main_bp.get("/lang/<code>")
def set_lang(code):
    if code not in ('cs', 'en'):
        code = 'cs'
    resp = make_response(redirect(request.referrer or '/'))
    resp.set_cookie('lang', code, max_age=365 * 24 * 3600, samesite='Lax')
    return resp


@main_bp.get("/")
def index():
    _seed_tiles()
    children = Child.query.order_by(Child.name).all()
    return render_template("index.html", children=children)


@main_bp.get("/kiosk/<int:child_id>")
def child_kiosk(child_id):
    _seed_tiles()
    child = db.get_or_404(Child, child_id)

    cats = VideoCategory.query.order_by(VideoCategory.sort_order, VideoCategory.id).all()
    videos = (
        KioskVideo.query
        .filter_by(enabled=True)
        .order_by(KioskVideo.sort_order, KioskVideo.id)
        .all()
    )

    # ── Chores ───────────────────────────────────────────────────────
    today = date_cls.today()
    today_wd = today.weekday()  # 0=Mon, 6=Sun

    chores = (
        DailyChore.query
        .filter_by(child_id=child_id, active=True)
        .order_by(DailyChore.weekday)
        .all()
    )
    done_today_ids = {
        c.chore_id
        for c in ChoreCompletion.query.filter_by(child_id=child_id, completed_date=today).all()
    }

    chores_by_wd: dict[str, list] = {}
    for c in chores:
        key = str(c.weekday)
        chores_by_wd.setdefault(key, []).append({
            "id": c.id,
            "icon": c.chore_icon,
            "name": c.chore_name,
            "points": c.points_reward,
            "done": c.id in done_today_ids,
        })

    # ── Schedule lock check ──────────────────────────────────────────
    now_time = dt_cls.now().time()
    all_schedules = ChildSchedule.query.filter(
        ChildSchedule.child_id == child_id,
        or_(ChildSchedule.weekday.is_(None), ChildSchedule.weekday == today_wd)
    ).all()

    locked_msg = None
    for s in all_schedules:
        if _time_in_window(now_time, s.locked_from, s.locked_to):
            locked_msg = s.message
            break

    schedules_js = [
        {
            "weekday": s.weekday,
            "from": s.locked_from.strftime("%H:%M"),
            "to": s.locked_to.strftime("%H:%M"),
            "message": s.message,
        }
        for s in ChildSchedule.query.filter_by(child_id=child_id).all()
    ]

    extra_tiles = (
        KioskTile.query
        .filter(KioskTile.enabled == True, KioskTile.category != 'videa')
        .order_by(KioskTile.sort_order, KioskTile.id)
        .all()
    )

    channel_names = [
        row[0] for row in
        db.session.query(KioskVideo.channel_name)
        .filter(KioskVideo.enabled == True, KioskVideo.channel_name.isnot(None))
        .distinct()
        .order_by(KioskVideo.channel_name)
        .all()
    ]

    shop_rewards = (
        ShopReward.query
        .filter_by(active=True)
        .order_by(ShopReward.sort_order, ShopReward.id)
        .all()
    )

    transactions = (
        PointTransaction.query
        .filter_by(child_id=child_id)
        .order_by(PointTransaction.created_at.desc())
        .limit(30)
        .all()
    )

    active_goal = ChildGoal.query.filter_by(child_id=child_id, active=True).first()
    streak = _compute_streak(child_id)

    earned_ids = {
        r.achievement_id
        for r in ChildAchievement.query.filter_by(child_id=child_id).all()
    }
    achievements_all = [
        {"id": k, **v, "earned": k in earned_ids}
        for k, v in ACHIEVEMENTS.items()
    ]

    watches_today = WatchSession.query.filter(
        WatchSession.child_id == child_id,
        func.date(WatchSession.started_at) == today,
    ).count()

    return render_template(
        "kiosk/child.html",
        child=child,
        cats=cats,
        videos=videos,
        extra_tiles=extra_tiles,
        channel_names=channel_names,
        shop_rewards=shop_rewards,
        transactions=transactions,
        streak=streak,
        watches_today=watches_today,
        achievements=achievements_all,
        active_goal=active_goal,
        chores_json=json.dumps(chores_by_wd),
        done_today_json=json.dumps(list(done_today_ids)),
        schedules_json=json.dumps(schedules_js),
        locked_msg=locked_msg,
        today_wd=today_wd,
    )


def _time_in_window(t, t_from, t_to):
    """Returns True if t is within [t_from, t_to], handling midnight crossing."""
    if t_from <= t_to:
        return t_from <= t <= t_to
    # spans midnight: e.g. 20:30 → 07:30
    return t >= t_from or t <= t_to
