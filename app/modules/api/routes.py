from datetime import date as date_cls, datetime as dt_cls

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import or_

from ...extensions import db
from ...models import (Child, ChildSchedule, ChoreCompletion, DailyChore,
                       Device, KioskVideo, PointTransaction, VideoPriceRule,
                       WatchSession)

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/")
def api_docs():
    children = Child.query.order_by(Child.name).all()
    first_key = "nixos-kuba-01"
    for child in children:
        dev = child.devices.first()
        if dev:
            first_key = dev.device_key
            break
    return render_template("api/docs.html", children=children, first_device_key=first_key)


@api_bp.get("/health")
def health():
    return {"status": "ok", "service": "nexus-junior"}


@api_bp.get("/device-policy")
def device_policy():
    device_key = request.args.get("deviceId", "").strip()
    if not device_key:
        return jsonify({"allowed": False, "message": "Chybí parametr deviceId."}), 400

    device = Device.query.filter_by(device_key=device_key).first()
    if not device:
        return jsonify({"allowed": False, "message": "Zařízení nebylo nalezeno."}), 404

    child = device.child

    if not device.allowed:
        msg = device.locked_message or "Přístup je dočasně zablokován."
        return jsonify({"allowed": False, "childName": child.name, "message": msg})

    locked, lock_msg = _is_schedule_locked(child.id)
    if locked:
        return jsonify({
            "allowed": False,
            "childName": child.name,
            "message": lock_msg or "Kiosek je teď zamčený.",
            "schedule_locked": True,
        })

    max_videos = child.points // child.video_cost if child.video_cost > 0 else 0

    return jsonify({
        "allowed": True,
        "childId": child.id,
        "childName": child.name,
        "points": child.points,
        "videoCost": child.video_cost,
        "maxVideos": max_videos,
        "dailyLimit": child.daily_video_limit,
        "message": f"Máš {child.points} bodů ({max_videos} videí).",
        "kioskUrl": f"/kiosk/{child.id}",
    })


@api_bp.post("/kiosk/watch")
def kiosk_watch():
    data = request.get_json(silent=True) or {}
    child_id = data.get("child_id")
    video_id = data.get("video_id")
    device_key = data.get("device_key", "")

    if not child_id:
        return jsonify({"ok": False, "reason": "missing_child_id"}), 400

    child = db.get_or_404(Child, child_id)

    locked, lock_msg = _is_schedule_locked(child_id)
    if locked:
        return jsonify({
            "ok": False,
            "reason": "schedule_locked",
            "message": lock_msg or "Kiosek je teď zamčený.",
        }), 403

    cost = _resolve_video_cost(video_id, child.video_cost)

    if child.points < cost:
        return jsonify({
            "ok": False,
            "reason": "not_enough_points",
            "message": "Nemáš dost bodů. Vydělej si je splněním úkolů!",
            "balance": child.points,
        })

    child.points -= cost
    db.session.add_all([
        PointTransaction(child_id=child.id, delta=-cost, reason="Přehrání videa", actor="system"),
        WatchSession(child_id=child.id, video_id=video_id or None,
                     device_key=device_key or None, points_spent=cost),
    ])
    db.session.commit()

    return jsonify({"ok": True, "new_balance": child.points})


@api_bp.post("/kiosk/chore/complete")
def kiosk_chore_complete():
    data = request.get_json(silent=True) or {}
    child_id = data.get("child_id")
    chore_id = data.get("chore_id")

    if not child_id or not chore_id:
        return jsonify({"ok": False, "reason": "missing_params"}), 400

    child = db.get_or_404(Child, child_id)
    chore = db.get_or_404(DailyChore, chore_id)

    if chore.child_id != child.id:
        return jsonify({"ok": False, "reason": "not_your_chore"}), 403

    today = date_cls.today()
    if ChoreCompletion.query.filter_by(chore_id=chore_id, child_id=child_id, completed_date=today).first():
        return jsonify({
            "ok": False,
            "reason": "already_done",
            "message": f"Úkol '{chore.chore_name}' jsi dnes už splnil! 🎉",
        })

    child.points += chore.points_reward
    db.session.add_all([
        ChoreCompletion(chore_id=chore_id, child_id=child_id,
                        completed_date=today, awarded_points=chore.points_reward),
        PointTransaction(child_id=child.id, delta=chore.points_reward,
                         reason=f"Úkol: {chore.chore_name}", actor="kiosk"),
    ])
    db.session.commit()

    return jsonify({"ok": True, "awarded": chore.points_reward,
                    "new_balance": child.points, "chore_name": chore.chore_name})


def _is_schedule_locked(child_id: int) -> tuple[bool, str | None]:
    """Return (is_locked, message). Checks all ChildSchedule rows for child."""
    now = dt_cls.now()
    today_wd = now.weekday()  # 0=Mon, 6=Sun
    now_t = now.time()

    schedules = ChildSchedule.query.filter(
        ChildSchedule.child_id == child_id,
        or_(ChildSchedule.weekday.is_(None), ChildSchedule.weekday == today_wd)
    ).all()

    for s in schedules:
        t_from, t_to = s.locked_from, s.locked_to
        if t_from <= t_to:
            in_window = t_from <= now_t <= t_to
        else:
            # spans midnight
            in_window = now_t >= t_from or now_t <= t_to
        if in_window:
            return True, s.message

    return False, None


def _resolve_video_cost(video_id, default_cost: int) -> int:
    if not video_id:
        return default_cost
    video = db.session.get(KioskVideo, video_id)
    if not video:
        return default_cost

    now_time = dt_cls.now().time()
    for rule in video.price_rules.all():
        in_window = (
            rule.time_from <= now_time <= rule.time_to
            if rule.time_from <= rule.time_to
            else now_time >= rule.time_from or now_time <= rule.time_to
        )
        if in_window:
            return rule.price

    return video.price if video.price is not None else default_cost
