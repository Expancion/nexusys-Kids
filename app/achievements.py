"""Achievement definitions and award logic."""
from datetime import date, timedelta

from .extensions import db
from .models import (Child, ChildAchievement, ChoreCompletion,
                     PointTransaction, WatchSession)

ACHIEVEMENTS = {
    "first_chore": {
        "name": "První krok",
        "desc": "Splnil/a první úkol",
        "icon": "🌟",
        "points": 5,
    },
    "chores_10": {
        "name": "Pilný pomocník",
        "desc": "10 splněných úkolů celkem",
        "icon": "💪",
        "points": 15,
    },
    "chores_50": {
        "name": "Mistr úkolů",
        "desc": "50 splněných úkolů celkem",
        "icon": "🎖️",
        "points": 50,
    },
    "streak_3": {
        "name": "Trojitý kombo",
        "desc": "3 dny v řadě se splněným úkolem",
        "icon": "🔥",
        "points": 10,
    },
    "streak_7": {
        "name": "Týdenní bojovník",
        "desc": "7 dní v řadě se splněným úkolem",
        "icon": "⚡",
        "points": 25,
    },
    "streak_30": {
        "name": "Neporazitelný",
        "desc": "30 dní v řadě se splněným úkolem",
        "icon": "🏆",
        "points": 100,
    },
    "points_50": {
        "name": "Střadatel",
        "desc": "Nasbíral/a 50 bodů najednou",
        "icon": "💰",
        "points": 0,
    },
    "points_200": {
        "name": "Boháč",
        "desc": "Nasbíral/a 200 bodů najednou",
        "icon": "💎",
        "points": 0,
    },
    "first_buy": {
        "name": "První nákup",
        "desc": "Koupil/a první odměnu v obchodě",
        "icon": "🛒",
        "points": 5,
    },
    "videos_5": {
        "name": "Divák",
        "desc": "Přehrál/a 5 videí",
        "icon": "🎬",
        "points": 5,
    },
    "videos_25": {
        "name": "Filmový nadšenec",
        "desc": "Přehrál/a 25 videí",
        "icon": "🎥",
        "points": 10,
    },
}


def _current_streak(child_id: int) -> int:
    d = date.today()
    streak = 0
    while streak < 366:
        if ChoreCompletion.query.filter_by(child_id=child_id, completed_date=d).first():
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak


def check_and_award(child_id: int) -> list[dict]:
    """Check all achievement conditions and award any not yet earned. Returns list of newly earned."""
    child = db.session.get(Child, child_id)
    if not child:
        return []

    already = {
        r.achievement_id
        for r in ChildAchievement.query.filter_by(child_id=child_id).all()
    }

    total_chores = ChoreCompletion.query.filter_by(child_id=child_id).count()
    total_videos = WatchSession.query.filter_by(child_id=child_id).count()
    streak       = _current_streak(child_id)
    shop_buys    = PointTransaction.query.filter_by(child_id=child_id, actor="shop").count()

    conditions = {
        "first_chore":  total_chores >= 1,
        "chores_10":    total_chores >= 10,
        "chores_50":    total_chores >= 50,
        "streak_3":     streak >= 3,
        "streak_7":     streak >= 7,
        "streak_30":    streak >= 30,
        "points_50":    child.points >= 50,
        "points_200":   child.points >= 200,
        "first_buy":    shop_buys >= 1,
        "videos_5":     total_videos >= 5,
        "videos_25":    total_videos >= 25,
    }

    newly_earned = []
    for ach_id, met in conditions.items():
        if met and ach_id not in already:
            defn = ACHIEVEMENTS[ach_id]
            db.session.add(ChildAchievement(child_id=child_id, achievement_id=ach_id))
            if defn["points"] > 0:
                child.points += defn["points"]
                db.session.add(PointTransaction(
                    child_id=child_id,
                    delta=defn["points"],
                    reason=f"Odznak: {defn['name']}",
                    actor="achievement",
                ))
            newly_earned.append({"id": ach_id, **defn})

    if newly_earned:
        db.session.commit()

    return newly_earned
