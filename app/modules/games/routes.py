from flask import Blueprint, render_template

games_bp = Blueprint("games", __name__, url_prefix="/games")


@games_bp.get("/letters")
def letters():
    return render_template("games/letters.html")
