from flask import Blueprint, jsonify, request

from ...extensions import db
from ...models import Child, Device, KioskVideo, PointTransaction, WatchSession

api_bp = Blueprint("api", __name__, url_prefix="/api")


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

    if child.points < child.video_cost:
        return jsonify({
            "ok": False,
            "reason": "not_enough_points",
            "message": "Nemáš dost bodů. Vydělej si je splněním úkolů!",
            "balance": child.points,
        })

    child.points -= child.video_cost

    tx = PointTransaction(
        child_id=child.id,
        delta=-child.video_cost,
        reason="Přehrání videa",
        actor="system",
    )
    ws = WatchSession(
        child_id=child.id,
        video_id=video_id or None,
        device_key=device_key or None,
        points_spent=child.video_cost,
    )
    db.session.add_all([tx, ws])
    db.session.commit()

    return jsonify({"ok": True, "new_balance": child.points})
