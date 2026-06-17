from functools import wraps

from flask import (
    Blueprint, current_app, redirect, render_template,
    request, session, url_for,
)

from ...extensions import db
from ...models import (Child, Device, KioskTile, KioskVideo, PointTransaction,
                       RewardTask, VideoCategory, extract_youtube_id)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

GRADIENTS = [
    ("Červená",   "linear-gradient(135deg,#ef4444,#b91c1c)"),
    ("Oranžová",  "linear-gradient(135deg,#f97316,#c2410c)"),
    ("Žlutá",     "linear-gradient(135deg,#eab308,#a16207)"),
    ("Zelená",    "linear-gradient(135deg,#22c55e,#15803d)"),
    ("Tyrkys",    "linear-gradient(135deg,#14b8a6,#0f766e)"),
    ("Cyan",      "linear-gradient(135deg,#06b6d4,#0e7490)"),
    ("Modrá",     "linear-gradient(135deg,#3b82f6,#1d4ed8)"),
    ("Indigo",    "linear-gradient(135deg,#6366f1,#4338ca)"),
    ("Fialová",   "linear-gradient(135deg,#a855f7,#7e22ce)"),
    ("Růžová",    "linear-gradient(135deg,#ec4899,#be185d)"),
    ("Vínová",    "linear-gradient(135deg,#f43f5e,#be123c)"),
    ("Šedá",      "linear-gradient(135deg,#6b7280,#374151)"),
]

CATEGORIES = [
    ("videa",       "Videa"),
    ("hry",         "Hry"),
    ("vzdelavani",  "Vzdělávání"),
    ("web",         "Web"),
]


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_ok"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.get("/")
def index():
    if session.get("admin_ok"):
        return redirect(url_for("admin.tiles"))
    return redirect(url_for("admin.login"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == current_app.config["KIOSK_ADMIN_PASSWORD"]:
            session["admin_ok"] = True
            return redirect(url_for("admin.tiles"))
        error = "Špatné heslo, zkus to znovu."
    return render_template("admin/login.html", error=error)


@admin_bp.post("/logout")
def logout():
    session.pop("admin_ok", None)
    return redirect(url_for("admin.login"))


@admin_bp.get("/tiles")
@admin_required
def tiles():
    all_tiles = KioskTile.query.order_by(KioskTile.sort_order, KioskTile.id).all()
    return render_template("admin/tiles.html", tiles=all_tiles, categories=dict(CATEGORIES))


@admin_bp.route("/tiles/new", methods=["GET", "POST"])
@admin_required
def tile_new():
    if request.method == "POST":
        tile = KioskTile(
            name=request.form["name"].strip(),
            url=request.form["url"].strip(),
            icon=request.form.get("icon", "🌐").strip() or "🌐",
            category=request.form["category"],
            color=request.form["color"],
            enabled=True,
            sort_order=int(request.form.get("sort_order") or 0),
        )
        db.session.add(tile)
        db.session.commit()
        return redirect(url_for("admin.tiles"))
    return render_template("admin/tile_form.html",
                           tile=None, gradients=GRADIENTS, categories=CATEGORIES)


@admin_bp.route("/tiles/<int:tile_id>/edit", methods=["GET", "POST"])
@admin_required
def tile_edit(tile_id):
    tile = db.get_or_404(KioskTile, tile_id)
    if request.method == "POST":
        tile.name = request.form["name"].strip()
        tile.url = request.form["url"].strip()
        tile.icon = request.form.get("icon", tile.icon).strip() or tile.icon
        tile.category = request.form["category"]
        tile.color = request.form["color"]
        tile.sort_order = int(request.form.get("sort_order") or 0)
        db.session.commit()
        return redirect(url_for("admin.tiles"))
    return render_template("admin/tile_form.html",
                           tile=tile, gradients=GRADIENTS, categories=CATEGORIES)


@admin_bp.post("/tiles/<int:tile_id>/toggle")
@admin_required
def tile_toggle(tile_id):
    tile = db.get_or_404(KioskTile, tile_id)
    tile.enabled = not tile.enabled
    db.session.commit()
    return redirect(url_for("admin.tiles"))


@admin_bp.post("/tiles/<int:tile_id>/delete")
@admin_required
def tile_delete(tile_id):
    tile = db.get_or_404(KioskTile, tile_id)
    db.session.delete(tile)
    db.session.commit()
    return redirect(url_for("admin.tiles"))


# ── Video categories ──────────────────────────────────────────────────────────

@admin_bp.get("/videos")
@admin_required
def videos():
    cats = VideoCategory.query.order_by(VideoCategory.sort_order, VideoCategory.id).all()
    return render_template("admin/videos.html", cats=cats, gradients=GRADIENTS)


@admin_bp.route("/videos/cats/new", methods=["GET", "POST"])
@admin_required
def video_cat_new():
    error = None
    if request.method == "POST":
        cat = VideoCategory(
            name=request.form["name"].strip(),
            icon=request.form.get("icon", "🎬").strip() or "🎬",
            color=request.form["color"],
            sort_order=int(request.form.get("sort_order") or 0),
        )
        db.session.add(cat)
        db.session.commit()
        return redirect(url_for("admin.videos"))
    return render_template("admin/video_cat_form.html",
                           cat=None, gradients=GRADIENTS, error=error)


@admin_bp.route("/videos/cats/<int:cat_id>/edit", methods=["GET", "POST"])
@admin_required
def video_cat_edit(cat_id):
    cat = db.get_or_404(VideoCategory, cat_id)
    if request.method == "POST":
        cat.name = request.form["name"].strip()
        cat.icon = request.form.get("icon", cat.icon).strip() or cat.icon
        cat.color = request.form["color"]
        cat.sort_order = int(request.form.get("sort_order") or 0)
        db.session.commit()
        return redirect(url_for("admin.videos"))
    return render_template("admin/video_cat_form.html", cat=cat, gradients=GRADIENTS, error=None)


@admin_bp.post("/videos/cats/<int:cat_id>/delete")
@admin_required
def video_cat_delete(cat_id):
    cat = db.get_or_404(VideoCategory, cat_id)
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for("admin.videos"))


# ── Videos ────────────────────────────────────────────────────────────────────

@admin_bp.route("/videos/new", methods=["GET", "POST"])
@admin_required
def video_new():
    cats = VideoCategory.query.order_by(VideoCategory.sort_order).all()
    error = None
    if request.method == "POST":
        yt_id = extract_youtube_id(request.form.get("url", ""))
        if not yt_id:
            error = "Nepodařilo se rozpoznat YouTube URL nebo ID. Zkus přímý odkaz na video."
        else:
            video = KioskVideo(
                title=request.form["title"].strip(),
                youtube_id=yt_id,
                category_id=int(request.form["category_id"]),
                enabled=True,
                sort_order=int(request.form.get("sort_order") or 0),
            )
            db.session.add(video)
            db.session.commit()
            return redirect(url_for("admin.videos"))
    preselect = request.args.get("cat", type=int)
    return render_template("admin/video_form.html",
                           video=None, cats=cats, preselect=preselect, error=error)


@admin_bp.route("/videos/<int:vid_id>/edit", methods=["GET", "POST"])
@admin_required
def video_edit(vid_id):
    video = db.get_or_404(KioskVideo, vid_id)
    cats = VideoCategory.query.order_by(VideoCategory.sort_order).all()
    error = None
    if request.method == "POST":
        yt_id = extract_youtube_id(request.form.get("url", ""))
        if not yt_id:
            error = "Nepodařilo se rozpoznat YouTube URL nebo ID."
        else:
            video.title = request.form["title"].strip()
            video.youtube_id = yt_id
            video.category_id = int(request.form["category_id"])
            video.sort_order = int(request.form.get("sort_order") or 0)
            db.session.commit()
            return redirect(url_for("admin.videos"))
    return render_template("admin/video_form.html",
                           video=video, cats=cats, preselect=None, error=error)


@admin_bp.post("/videos/<int:vid_id>/toggle")
@admin_required
def video_toggle(vid_id):
    video = db.get_or_404(KioskVideo, vid_id)
    video.enabled = not video.enabled
    db.session.commit()
    return redirect(url_for("admin.videos"))


@admin_bp.post("/videos/<int:vid_id>/delete")
@admin_required
def video_delete(vid_id):
    video = db.get_or_404(KioskVideo, vid_id)
    db.session.delete(video)
    db.session.commit()
    return redirect(url_for("admin.videos"))


# ── Children ──────────────────────────────────────────────────────────────────

@admin_bp.get("/children")
@admin_required
def children():
    kids = Child.query.order_by(Child.name).all()
    return render_template("admin/children.html", children=kids)


@admin_bp.route("/children/new", methods=["GET", "POST"])
@admin_required
def child_new():
    error = None
    if request.method == "POST":
        child = Child(
            name=request.form["name"].strip(),
            avatar_icon=request.form.get("avatar_icon", "🧒").strip() or "🧒",
            avatar_color=request.form["avatar_color"],
            points=int(request.form.get("points", 0) or 0),
            video_cost=int(request.form.get("video_cost", 10) or 10),
            daily_video_limit=int(request.form.get("daily_video_limit", 0) or 0),
        )
        db.session.add(child)
        db.session.commit()
        return redirect(url_for("admin.children"))
    return render_template("admin/child_form.html", child=None, gradients=GRADIENTS, error=error)


@admin_bp.route("/children/<int:child_id>/edit", methods=["GET", "POST"])
@admin_required
def child_edit(child_id):
    child = db.get_or_404(Child, child_id)
    error = None
    if request.method == "POST":
        child.name = request.form["name"].strip()
        child.avatar_icon = request.form.get("avatar_icon", child.avatar_icon).strip() or child.avatar_icon
        child.avatar_color = request.form["avatar_color"]
        child.video_cost = int(request.form.get("video_cost", 10) or 10)
        child.daily_video_limit = int(request.form.get("daily_video_limit", 0) or 0)
        db.session.commit()
        return redirect(url_for("admin.child_detail", child_id=child.id))
    return render_template("admin/child_form.html", child=child, gradients=GRADIENTS, error=error)


@admin_bp.post("/children/<int:child_id>/delete")
@admin_required
def child_delete(child_id):
    child = db.get_or_404(Child, child_id)
    db.session.delete(child)
    db.session.commit()
    return redirect(url_for("admin.children"))


@admin_bp.get("/children/<int:child_id>")
@admin_required
def child_detail(child_id):
    child = db.get_or_404(Child, child_id)
    tasks = RewardTask.query.filter_by(active=True).order_by(RewardTask.sort_order, RewardTask.id).all()
    devices = child.devices.order_by(Device.name).all()
    txs = child.transactions.order_by(PointTransaction.created_at.desc()).limit(20).all()
    return render_template("admin/child_detail.html",
                           child=child, tasks=tasks, devices=devices, txs=txs)


@admin_bp.post("/children/<int:child_id>/award")
@admin_required
def child_award(child_id):
    child = db.get_or_404(Child, child_id)
    task_id = request.form.get("task_id", type=int)

    if task_id:
        task = db.get_or_404(RewardTask, task_id)
        points = task.points_value
        reason = task.name
    else:
        points = int(request.form.get("points", 0) or 0)
        reason = request.form.get("reason", "").strip() or "Manuální odměna"

    if points > 0:
        child.points += points
        db.session.add(PointTransaction(
            child_id=child.id, delta=points, reason=reason, actor="parent"))
        db.session.commit()

    return redirect(url_for("admin.child_detail", child_id=child_id))


# ── Devices ───────────────────────────────────────────────────────────────────

@admin_bp.route("/children/<int:child_id>/devices/new", methods=["GET", "POST"])
@admin_required
def device_new(child_id):
    child = db.get_or_404(Child, child_id)
    error = None
    if request.method == "POST":
        key = request.form["device_key"].strip()
        if Device.query.filter_by(device_key=key).first():
            error = f'Klic "{key}" je jiz pouzit jinym zarizenim.'
        else:
            device = Device(
                child_id=child.id,
                device_key=key,
                name=request.form["name"].strip(),
                allowed="allowed" in request.form,
                locked_message=request.form.get("locked_message", "").strip() or None,
            )
            db.session.add(device)
            db.session.commit()
            return redirect(url_for("admin.child_detail", child_id=child_id))
    return render_template("admin/device_form.html", child=child, device=None, error=error)


@admin_bp.route("/devices/<int:device_id>/edit", methods=["GET", "POST"])
@admin_required
def device_edit(device_id):
    device = db.get_or_404(Device, device_id)
    error = None
    if request.method == "POST":
        key = request.form["device_key"].strip()
        conflict = Device.query.filter(
            Device.device_key == key, Device.id != device_id).first()
        if conflict:
            error = f'Klic "{key}" je jiz pouzit jinym zarizenim.'
        else:
            device.device_key = key
            device.name = request.form["name"].strip()
            device.allowed = "allowed" in request.form
            device.locked_message = request.form.get("locked_message", "").strip() or None
            db.session.commit()
            return redirect(url_for("admin.child_detail", child_id=device.child_id))
    return render_template("admin/device_form.html",
                           child=device.child, device=device, error=error)


@admin_bp.post("/devices/<int:device_id>/toggle")
@admin_required
def device_toggle(device_id):
    device = db.get_or_404(Device, device_id)
    device.allowed = not device.allowed
    db.session.commit()
    return redirect(url_for("admin.child_detail", child_id=device.child_id))


@admin_bp.post("/devices/<int:device_id>/delete")
@admin_required
def device_delete(device_id):
    device = db.get_or_404(Device, device_id)
    child_id = device.child_id
    db.session.delete(device)
    db.session.commit()
    return redirect(url_for("admin.child_detail", child_id=child_id))


# ── Reward Tasks ──────────────────────────────────────────────────────────────

@admin_bp.get("/tasks")
@admin_required
def tasks():
    all_tasks = RewardTask.query.order_by(RewardTask.sort_order, RewardTask.id).all()
    return render_template("admin/tasks.html", tasks=all_tasks)


@admin_bp.route("/tasks/new", methods=["GET", "POST"])
@admin_required
def task_new():
    if request.method == "POST":
        db.session.add(RewardTask(
            name=request.form["name"].strip(),
            icon=request.form.get("icon", "⭐").strip() or "⭐",
            points_value=int(request.form.get("points_value", 10) or 10),
            active=True,
            sort_order=int(request.form.get("sort_order", 0) or 0),
        ))
        db.session.commit()
        return redirect(url_for("admin.tasks"))
    return render_template("admin/task_form.html", task=None)


@admin_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@admin_required
def task_edit(task_id):
    task = db.get_or_404(RewardTask, task_id)
    if request.method == "POST":
        task.name = request.form["name"].strip()
        task.icon = request.form.get("icon", task.icon).strip() or task.icon
        task.points_value = int(request.form.get("points_value", 10) or 10)
        task.sort_order = int(request.form.get("sort_order", 0) or 0)
        db.session.commit()
        return redirect(url_for("admin.tasks"))
    return render_template("admin/task_form.html", task=task)


@admin_bp.post("/tasks/<int:task_id>/toggle")
@admin_required
def task_toggle(task_id):
    task = db.get_or_404(RewardTask, task_id)
    task.active = not task.active
    db.session.commit()
    return redirect(url_for("admin.tasks"))


@admin_bp.post("/tasks/<int:task_id>/delete")
@admin_required
def task_delete(task_id):
    task = db.get_or_404(RewardTask, task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("admin.tasks"))
