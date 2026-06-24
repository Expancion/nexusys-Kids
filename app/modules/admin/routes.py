import json as json_mod
import re
import urllib.parse
import urllib.request
from datetime import date as date_cls, timedelta
from functools import wraps

from flask import (
    Blueprint, current_app, redirect, render_template,
    request, session, url_for,
)
from flask_babel import gettext as _
from sqlalchemy import func

from werkzeug.security import check_password_hash

from ...extensions import db
from ...models import (Child, ChildSchedule, ChoreCompletion, DailyChore, Device,
                       KioskMessage, KioskTile, KioskVideo, PointTransaction, RewardTask,
                       ShopReward, SystemConfig, VideoCategory, VideoPriceRule,
                       WatchSession, extract_youtube_id)

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
    ("videa",       "Videos"),
    ("hry",         "Games"),
    ("vzdelavani",  "Education"),
    ("web",         "Web"),
]


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if SystemConfig.get("setup_complete") != "1":
            return redirect("/setup")
        if not session.get("admin_ok"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.get("/")
def index():
    if not session.get("admin_ok"):
        return redirect(url_for("admin.login"))

    today = date_cls.today()
    children = Child.query.order_by(Child.name).all()

    child_stats = []
    for c in children:
        done_today = ChoreCompletion.query.filter_by(child_id=c.id, completed_date=today).count()
        total_chores = DailyChore.query.filter_by(child_id=c.id, active=True).count()
        watches_today = WatchSession.query.filter(
            WatchSession.child_id == c.id,
            func.date(WatchSession.started_at) == today,
        ).count()
        child_stats.append({
            "child": c,
            "done_today": done_today,
            "total_chores": total_chores,
            "watches_today": watches_today,
        })

    recent_tx = (
        PointTransaction.query
        .order_by(PointTransaction.created_at.desc())
        .limit(12)
        .all()
    )

    video_count   = KioskVideo.query.filter_by(enabled=True).count()
    reward_count  = ShopReward.query.filter_by(active=True).count()

    return render_template(
        "admin/dashboard.html",
        child_stats=child_stats,
        recent_tx=recent_tx,
        video_count=video_count,
        reward_count=reward_count,
        today=today,
    )


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if SystemConfig.get("setup_complete") != "1":
        return redirect("/setup")
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        pw_hash = SystemConfig.get("admin_password_hash")
        ok = check_password_hash(pw_hash, pw) if pw_hash else (pw == current_app.config["KIOSK_ADMIN_PASSWORD"])
        if ok:
            session["admin_ok"] = True
            return redirect(url_for("admin.tiles"))
        error = _("Wrong password, try again.")
    return render_template("admin/login.html", error=error)


@admin_bp.post("/logout")
def logout():
    session.pop("admin_ok", None)
    return redirect(url_for("admin.login"))


@admin_bp.get("/help")
@admin_required
def help():
    return render_template("admin/help.html")


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
            name_en=request.form.get("name_en", "").strip() or None,
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
        tile.name_en = request.form.get("name_en", "").strip() or None
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

@admin_bp.post("/videos/import-playlist")
@admin_required
def import_playlist():
    playlist_url  = request.form.get("playlist_url", "").strip()
    category_id   = request.form.get("category_id", type=int)
    price_raw     = request.form.get("default_price", "").strip()
    default_price = int(price_raw) if price_raw else None

    if not playlist_url or not category_id:
        return redirect(url_for("admin.videos"))

    api_key = current_app.config.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return redirect(url_for("admin.videos") + "?import_error=no_key")

    playlist_id = _extract_playlist_id(playlist_url)
    if not playlist_id:
        return redirect(url_for("admin.videos") + "?import_error=bad_url")

    try:
        yt_items = _fetch_yt_playlist(playlist_id, api_key)
    except Exception:
        return redirect(url_for("admin.videos") + "?import_error=api")

    imported = skipped = 0
    for item in yt_items:
        yt_id = item["id"]
        if KioskVideo.query.filter_by(youtube_id=yt_id).first():
            skipped += 1
            continue
        db.session.add(KioskVideo(
            title=item["title"][:120],
            youtube_id=yt_id,
            category_id=category_id,
            channel_name=item["channel"][:120] if item["channel"] else None,
            enabled=True,
            sort_order=0,
            price=default_price,
        ))
        imported += 1
    db.session.commit()

    return redirect(
        url_for("admin.videos") + f"?imported={imported}&skipped={skipped}"
    )


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
            price_raw    = request.form.get("price", "").strip()
            channel_raw  = request.form.get("channel_name", "").strip()
            video = KioskVideo(
                title=request.form["title"].strip(),
                youtube_id=yt_id,
                category_id=int(request.form["category_id"]),
                channel_name=channel_raw or None,
                enabled=True,
                sort_order=int(request.form.get("sort_order") or 0),
                price=int(price_raw) if price_raw else None,
            )
            db.session.add(video)
            db.session.commit()
            _save_price_rules(video)
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
            price_raw   = request.form.get("price", "").strip()
            channel_raw = request.form.get("channel_name", "").strip()
            video.title        = request.form["title"].strip()
            video.youtube_id   = yt_id
            video.category_id  = int(request.form["category_id"])
            video.channel_name = channel_raw or None
            video.sort_order   = int(request.form.get("sort_order") or 0)
            video.price        = int(price_raw) if price_raw else None
            _save_price_rules(video)
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
    task_count = RewardTask.query.filter_by(active=True).count()
    return render_template("admin/children.html", children=kids, task_count=task_count)


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
    from ...models import ChildGoal
    child = db.get_or_404(Child, child_id)
    tasks = RewardTask.query.filter_by(active=True).order_by(RewardTask.sort_order, RewardTask.id).all()
    devices = child.devices.order_by(Device.name).all()
    txs = child.transactions.order_by(PointTransaction.created_at.desc()).limit(20).all()
    chores = child.chores.order_by(DailyChore.weekday).all()
    schedules = child.schedules.order_by(ChildSchedule.weekday, ChildSchedule.locked_from).all()
    child_goals = ChildGoal.query.filter_by(child_id=child_id).order_by(ChildGoal.created_at.desc()).all()
    rewards = ShopReward.query.filter_by(active=True).order_by(ShopReward.sort_order).all()
    return render_template("admin/child_detail.html",
                           child=child, tasks=tasks, devices=devices, txs=txs,
                           chores=chores, schedules=schedules, child_goals=child_goals,
                           rewards=rewards, weekdays_short=WEEKDAYS_SHORT)


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


@admin_bp.get("/devices/<int:device_id>/nixos-config")
@admin_required
def device_nixos_config(device_id):
    from flask import Response
    device = db.get_or_404(Device, device_id)
    base_url = (
        current_app.config.get("PUBLIC_URL")
        or request.host_url.rstrip("/")
    )
    default_lang = SystemConfig.get("default_lang", "cs")
    chromium_lang = "cs-CZ" if default_lang == "cs" else "en-US"
    hostname = device.device_key
    child_id = device.child_id

    nix = _render_nixos_config(hostname, device.device_key, base_url, child_id, chromium_lang)

    return Response(
        nix,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{hostname}.nix"'},
    )


def _render_nixos_config(hostname: str, device_id: str, base_url: str,
                          child_id: int, chromium_lang: str) -> str:
    return f"""{{ config, pkgs, ... }}:

{{
  imports = [
    ./hardware-configuration.nix
  ];

  # Bootloader
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  boot.loader.systemd-boot.configurationLimit = 3;
  boot.loader.timeout = 1;

  # Network
  networking.hostName = "{hostname}";
  networking.networkmanager.enable = true;
  networking.networkmanager.wifi.powersave = false;

  networking.firewall.enable = true;
  networking.firewall.allowedTCPPorts = [ 22 ];

  # Locale / Time
  time.timeZone = "Europe/Prague";
  i18n.defaultLocale = "en_US.UTF-8";

  i18n.extraLocaleSettings = {{
    LC_ADDRESS = "cs_CZ.UTF-8";
    LC_IDENTIFICATION = "cs_CZ.UTF-8";
    LC_MEASUREMENT = "cs_CZ.UTF-8";
    LC_MONETARY = "cs_CZ.UTF-8";
    LC_NAME = "cs_CZ.UTF-8";
    LC_NUMERIC = "cs_CZ.UTF-8";
    LC_PAPER = "cs_CZ.UTF-8";
    LC_TELEPHONE = "cs_CZ.UTF-8";
    LC_TIME = "cs_CZ.UTF-8";
  }};

  # Desktop / Kiosk Session
  services.xserver.enable = true;
  services.displayManager.sddm.enable = true;
  services.desktopManager.plasma6.enable = true;
  services.displayManager.defaultSession = "plasmax11";

  services.displayManager.autoLogin.enable = true;
  services.displayManager.autoLogin.user = "kid";

  services.xserver.xkb = {{
    layout = "us";
    variant = "";
  }};

  # Disable KDE Wallet
  environment.etc."xdg/kwalletrc".text = '''
    [Wallet]
    Enabled=false
  ''';

  # Disable KDE screen lock
  environment.etc."xdg/kscreenlockerrc".text = '''
    [Daemon]
    Autolock=false
    LockOnResume=false
    Timeout=0
  ''';

  # Empty Plasma session restore
  environment.etc."xdg/ksmserverrc".text = '''
    [General]
    loginMode=emptySession
  ''';

  # Power behavior: do not suspend/logout
  services.logind.settings.Login = {{
    IdleAction = "ignore";
    HandleLidSwitch = "ignore";
    HandleLidSwitchExternalPower = "ignore";
    HandlePowerKey = "ignore";
    HandleSuspendKey = "ignore";
    HandleHibernateKey = "ignore";
  }};

  # Audio
  services.pulseaudio.enable = false;
  security.rtkit.enable = true;

  services.pipewire = {{
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
  }};

  # Users
  users.users.parent = {{
    isNormalUser = true;
    description = "Parent";
    extraGroups = [
      "networkmanager"
      "wheel"
    ];
  }};

  users.users.kid = {{
    isNormalUser = true;
    description = "Kid Kiosk User";
  }};

  # Local Caddy / internal CA trust
  security.pki.certificates = [
    (builtins.readFile /etc/nixos/caddy-ca.crt)
  ];

  nixpkgs.config.allowUnfree = true;

  environment.systemPackages = with pkgs; [
    bash
    curl
    jq
    chromium
    vim
    git
    networkmanager
    procps
  ];

  # SSH for parent/admin access
  services.openssh.enable = true;

  services.openssh.settings = {{
    PasswordAuthentication = true;
    PermitRootLogin = "no";
  }};

  # Chromium managed policy
  environment.etc."chromium/policies/managed/nexus-kiosk.json".text = '''
    {{
      "TranslateEnabled": false,
      "DefaultBrowserSettingEnabled": false,
      "PasswordManagerEnabled": false,
      "AutofillAddressEnabled": false,
      "AutofillCreditCardEnabled": false
    }}
  ''';

  # Nexus Kiosk Agent
  environment.etc."nexus-kiosk/agent.sh" = {{
    mode = "0755";
    text = '''
#!${{pkgs.bash}}/bin/bash
set -euo pipefail

BASE_URL="{base_url}"
DEVICE_ID="{device_id}"
POLICY_URL="$BASE_URL/api/device-policy?deviceId=$DEVICE_ID"
PROFILE_DIR="/tmp/nexus-kiosk-chromium"

CURRENT_STATE=""

log() {{
  echo "[nexus-agent] $*"
}}

start_chromium() {{
  local url="$1"

  ${{pkgs.procps}}/bin/pkill -u kid chromium >/dev/null 2>&1 || true
  ${{pkgs.procps}}/bin/pkill -u kid plasmashell >/dev/null 2>&1 || true

  rm -rf "$PROFILE_DIR"
  mkdir -p "$PROFILE_DIR"

  ${{pkgs.chromium}}/bin/chromium \\
    --kiosk \\
    --user-data-dir="$PROFILE_DIR" \\
    --no-first-run \\
    --no-default-browser-check \\
    --disable-infobars \\
    --disable-session-crashed-bubble \\
    --disable-restore-session-state \\
    --disable-features=Translate,TranslateUI \\
    --disable-translate \\
    --lang={chromium_lang} \\
    --incognito \\
    "$url" &

  log "Browser switched to: $url"
}}

log "Starting Nexus Agent"
log "Device: $DEVICE_ID"

sleep 8

while true; do
  POLICY="$(${{pkgs.curl}}/bin/curl -fsS "$POLICY_URL" 2>/dev/null || true)"

  ALLOWED="$(echo "$POLICY" | ${{pkgs.jq}}/bin/jq -r '.allowed // false' 2>/dev/null || echo false)"
  KIOSK_URL="$(echo "$POLICY" | ${{pkgs.jq}}/bin/jq -r '.kioskUrl // "/kiosk/{child_id}"' 2>/dev/null || echo "/kiosk/{child_id}")"
  MESSAGE="$(echo "$POLICY" | ${{pkgs.jq}}/bin/jq -r '.message // "Zařízení je momentálně uzamčeno"' 2>/dev/null || echo "Zařízení je momentálně uzamčeno")"

  if [ "$ALLOWED" = "true" ]; then
    case "$KIOSK_URL" in
      http://*|https://*) TARGET_URL="$KIOSK_URL" ;;
      *) TARGET_URL="$BASE_URL$KIOSK_URL" ;;
    esac

    NEW_STATE="allowed:$TARGET_URL"
  else
    cat > /tmp/nexus-lock.html <<HTML
<!doctype html>
<html lang="cs" translate="no">
<head>
<meta charset="utf-8">
<meta name="google" content="notranslate">
</head>
<body style="margin:0;height:100vh;background:#080b16;color:white;font-family:sans-serif;display:flex;align-items:center;justify-content:center;text-align:center">
<div>
<h1 style="font-size:64px">🔒 Nexus Junior</h1>
<p style="font-size:28px;opacity:.8">$MESSAGE</p>
</div>
</body>
</html>
HTML

    TARGET_URL="file:///tmp/nexus-lock.html"
    NEW_STATE="locked:$MESSAGE"
  fi

  if [ "$NEW_STATE" != "$CURRENT_STATE" ]; then
    log "State changed: $CURRENT_STATE -> $NEW_STATE"
    CURRENT_STATE="$NEW_STATE"
    start_chromium "$TARGET_URL"
  fi

  sleep 15
done
    ''';
  }};

  # Cleanup old KDE autostart and force empty KDE session
  system.activationScripts.nexusKioskCleanup.text = '''
    rm -f /home/kid/.config/autostart/nexus-junior.desktop
    mkdir -p /home/kid/.config

    cat > /home/kid/.config/ksmserverrc <<'KSM'
[General]
loginMode=emptySession
KSM

    chown -R kid:users /home/kid/.config
  ''';

  # User service runs inside graphical kid session
  systemd.user.services.nexus-kiosk-agent = {{
    description = "Nexus Kiosk Agent";

    wantedBy = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];

    serviceConfig = {{
      ExecStart = "/etc/nexus-kiosk/agent.sh";
      Restart = "always";
      RestartSec = 5;
    }};
  }};

  system.stateVersion = "26.05";
}}
"""


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


# ── Daily Chores ──────────────────────────────────────────────────────────────

WEEKDAYS_CS = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"]
WEEKDAYS_SHORT = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]


@admin_bp.route("/children/<int:child_id>/chores/new", methods=["GET", "POST"])
@admin_required
def chore_new(child_id):
    child = db.get_or_404(Child, child_id)
    error = None
    if request.method == "POST":
        db.session.add(DailyChore(
            child_id=child.id,
            weekday=int(request.form["weekday"]),
            chore_name=request.form["chore_name"].strip(),
            chore_icon=request.form.get("chore_icon", "✅").strip() or "✅",
            points_reward=int(request.form.get("points_reward", 5) or 5),
            active=True,
        ))
        db.session.commit()
        return redirect(url_for("admin.child_detail", child_id=child_id))
    return render_template("admin/chore_form.html", child=child, chore=None,
                           weekdays=WEEKDAYS_CS, error=error)


@admin_bp.route("/chores/<int:chore_id>/edit", methods=["GET", "POST"])
@admin_required
def chore_edit(chore_id):
    chore = db.get_or_404(DailyChore, chore_id)
    error = None
    if request.method == "POST":
        chore.weekday = int(request.form["weekday"])
        chore.chore_name = request.form["chore_name"].strip()
        chore.chore_icon = request.form.get("chore_icon", chore.chore_icon).strip() or chore.chore_icon
        chore.points_reward = int(request.form.get("points_reward", 5) or 5)
        db.session.commit()
        return redirect(url_for("admin.child_detail", child_id=chore.child_id))
    return render_template("admin/chore_form.html", child=chore.child, chore=chore,
                           weekdays=WEEKDAYS_CS, error=error)


@admin_bp.post("/chores/<int:chore_id>/delete")
@admin_required
def chore_delete(chore_id):
    chore = db.get_or_404(DailyChore, chore_id)
    child_id = chore.child_id
    db.session.delete(chore)
    db.session.commit()
    return redirect(url_for("admin.child_detail", child_id=child_id))


# ── Child Schedule ────────────────────────────────────────────────────────────

@admin_bp.route("/children/<int:child_id>/schedules/new", methods=["GET", "POST"])
@admin_required
def schedule_new(child_id):
    child = db.get_or_404(Child, child_id)
    error = None
    if request.method == "POST":
        from datetime import time as time_cls
        def parse_time(val):
            h, m = val.strip().split(":")
            return time_cls(int(h), int(m))
        weekday_raw = request.form.get("weekday", "").strip()
        db.session.add(ChildSchedule(
            child_id=child.id,
            weekday=int(weekday_raw) if weekday_raw != "" else None,
            locked_from=parse_time(request.form["locked_from"]),
            locked_to=parse_time(request.form["locked_to"]),
            message=request.form.get("message", "Kiosek je teď nedostupný.").strip()
                    or "Kiosek je teď nedostupný.",
        ))
        db.session.commit()
        return redirect(url_for("admin.child_detail", child_id=child_id))
    return render_template("admin/schedule_form.html", child=child, schedule=None,
                           weekdays=WEEKDAYS_CS, error=error)


@admin_bp.post("/schedules/<int:schedule_id>/delete")
@admin_required
def schedule_delete(schedule_id):
    s = db.get_or_404(ChildSchedule, schedule_id)
    child_id = s.child_id
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("admin.child_detail", child_id=child_id))


# ── Shop Rewards ──────────────────────────────────────────────────────────────

@admin_bp.get("/rewards")
@admin_required
def rewards():
    all_rewards = ShopReward.query.order_by(ShopReward.sort_order, ShopReward.id).all()
    return render_template("admin/rewards.html", rewards=all_rewards)


@admin_bp.route("/rewards/new", methods=["GET", "POST"])
@admin_required
def reward_new():
    if request.method == "POST":
        db.session.add(ShopReward(
            name=request.form["name"].strip(),
            description=request.form.get("description", "").strip() or None,
            icon=request.form.get("icon", "🎁").strip() or "🎁",
            cost_points=int(request.form.get("cost_points", 50) or 50),
            active=True,
            sort_order=int(request.form.get("sort_order", 0) or 0),
        ))
        db.session.commit()
        return redirect(url_for("admin.rewards"))
    return render_template("admin/reward_form.html", reward=None)


@admin_bp.route("/rewards/<int:reward_id>/edit", methods=["GET", "POST"])
@admin_required
def reward_edit(reward_id):
    reward = db.get_or_404(ShopReward, reward_id)
    if request.method == "POST":
        reward.name        = request.form["name"].strip()
        reward.description = request.form.get("description", "").strip() or None
        reward.icon        = request.form.get("icon", reward.icon).strip() or reward.icon
        reward.cost_points = int(request.form.get("cost_points", 50) or 50)
        reward.sort_order  = int(request.form.get("sort_order", 0) or 0)
        db.session.commit()
        return redirect(url_for("admin.rewards"))
    return render_template("admin/reward_form.html", reward=reward)


@admin_bp.post("/rewards/<int:reward_id>/toggle")
@admin_required
def reward_toggle(reward_id):
    reward = db.get_or_404(ShopReward, reward_id)
    reward.active = not reward.active
    db.session.commit()
    return redirect(url_for("admin.rewards"))


@admin_bp.post("/rewards/<int:reward_id>/delete")
@admin_required
def reward_delete(reward_id):
    reward = db.get_or_404(ShopReward, reward_id)
    db.session.delete(reward)
    db.session.commit()
    return redirect(url_for("admin.rewards"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_playlist_id(raw: str) -> str | None:
    parsed = urllib.parse.urlparse(raw)
    if "youtube" in parsed.netloc:
        qs = urllib.parse.parse_qs(parsed.query)
        if "list" in qs:
            return qs["list"][0]
    if re.match(r'^[A-Za-z0-9_-]{10,}$', raw.strip()):
        return raw.strip()
    return None


def _fetch_yt_playlist(playlist_id: str, api_key: str) -> list[dict]:
    base = "https://www.googleapis.com/youtube/v3/playlistItems"
    items = []
    page_token = None

    while True:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        url = base + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json_mod.loads(resp.read())

        if "error" in data:
            raise ValueError(data["error"].get("message", "API error"))

        for entry in data.get("items", []):
            sn     = entry.get("snippet", {})
            vid_id = sn.get("resourceId", {}).get("videoId", "")
            title  = sn.get("title", "")
            if not vid_id or title in ("Deleted video", "Private video"):
                continue
            items.append({
                "id":      vid_id,
                "title":   title,
                "channel": sn.get("videoOwnerChannelTitle", "") or "",
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return items


# ── Goals ─────────────────────────────────────────────────────────────────────

@admin_bp.post("/children/<int:child_id>/goal")
@admin_required
def set_goal(child_id):
    child = db.get_or_404(Child, child_id)
    from ...models import ChildGoal
    reward_id    = request.form.get("reward_id", type=int)
    name         = request.form.get("name", "").strip()
    icon         = request.form.get("icon", "🎯").strip() or "🎯"
    target_points = request.form.get("target_points", type=int)

    if name and target_points and target_points > 0:
        ChildGoal.query.filter_by(child_id=child.id, active=True).update({"active": False})
        reward = db.session.get(ShopReward, reward_id) if reward_id else None
        db.session.add(ChildGoal(
            child_id=child.id,
            reward_id=reward.id if reward else None,
            name=name,
            icon=icon,
            target_points=target_points,
        ))
        db.session.commit()
    return redirect(request.referrer or url_for("admin.child_detail", child_id=child.id))


@admin_bp.post("/children/<int:child_id>/goal/clear")
@admin_required
def clear_goal(child_id):
    from ...models import ChildGoal
    ChildGoal.query.filter_by(child_id=child_id, active=True).update({"active": False})
    db.session.commit()
    return redirect(request.referrer or url_for("admin.child_detail", child_id=child_id))


# ── Messages ──────────────────────────────────────────────────────────────────

@admin_bp.post("/children/<int:child_id>/send-message")
@admin_required
def send_message(child_id):
    child = db.get_or_404(Child, child_id)
    text = request.form.get("text", "").strip()
    icon = request.form.get("icon", "💬").strip() or "💬"
    if text:
        db.session.add(KioskMessage(child_id=child.id, text=text, icon=icon))
        db.session.commit()
    return redirect(request.referrer or url_for("admin.index"))


# ── Statistics ────────────────────────────────────────────────────────────────

@admin_bp.get("/stats")
@admin_required
def stats():
    DAYS = 14
    children = Child.query.order_by(Child.name).all()
    child_id = request.args.get("child_id", type=int)
    child = None
    if child_id:
        child = db.get_or_404(Child, child_id)
    elif children:
        child = children[0]
        child_id = child.id

    since = date_cls.today() - timedelta(days=DAYS - 1)
    day_range = [since + timedelta(days=i) for i in range(DAYS)]
    labels = [d.strftime("%-d.%-m.") for d in day_range]

    def fill(rows, days):
        m = {str(r[0]): int(r[1] or 0) for r in rows}
        return [m.get(str(d), 0) for d in days]

    if child:
        earned_rows = db.session.query(
            func.date(PointTransaction.created_at),
            func.sum(PointTransaction.delta),
        ).filter(
            PointTransaction.child_id == child_id,
            PointTransaction.delta > 0,
            PointTransaction.created_at >= since,
        ).group_by(func.date(PointTransaction.created_at)).all()

        spent_rows = db.session.query(
            func.date(PointTransaction.created_at),
            func.sum(-PointTransaction.delta),
        ).filter(
            PointTransaction.child_id == child_id,
            PointTransaction.delta < 0,
            PointTransaction.created_at >= since,
        ).group_by(func.date(PointTransaction.created_at)).all()

        watch_rows = db.session.query(
            func.date(WatchSession.started_at),
            func.count(WatchSession.id),
        ).filter(
            WatchSession.child_id == child_id,
            WatchSession.started_at >= since,
        ).group_by(func.date(WatchSession.started_at)).all()

        chore_rows = db.session.query(
            ChoreCompletion.completed_date,
            func.count(ChoreCompletion.id),
        ).filter(
            ChoreCompletion.child_id == child_id,
            ChoreCompletion.completed_date >= since,
        ).group_by(ChoreCompletion.completed_date).all()

        income_actor_rows = db.session.query(
            PointTransaction.actor,
            func.sum(PointTransaction.delta),
        ).filter(
            PointTransaction.child_id == child_id,
            PointTransaction.delta > 0,
        ).group_by(PointTransaction.actor).all()

        earned_s = fill(earned_rows, day_range)
        spent_s  = fill(spent_rows,  day_range)
        watch_s  = fill(watch_rows,  day_range)
        chore_s  = fill(chore_rows,  day_range)

        total_earned  = sum(earned_s)
        total_spent   = sum(spent_s)
        total_watches = sum(watch_s)
        total_chores  = sum(chore_s)

        actor_map = {'game': 'Hry', 'kiosk': 'Úkoly', 'parent': 'Rodič',
                     'system': 'Systém', 'shop': 'Obchod'}
        actor_labels = [actor_map.get(r[0], r[0]) for r in income_actor_rows]
        actor_values = [int(r[1] or 0) for r in income_actor_rows]
    else:
        earned_s = spent_s = watch_s = chore_s = []
        total_earned = total_spent = total_watches = total_chores = 0
        actor_labels = actor_values = []

    return render_template(
        "admin/stats.html",
        children=children,
        child=child,
        labels=labels,
        earned_s=earned_s,
        spent_s=spent_s,
        watch_s=watch_s,
        chore_s=chore_s,
        total_earned=total_earned,
        total_spent=total_spent,
        total_watches=total_watches,
        total_chores=total_chores,
        actor_labels=actor_labels,
        actor_values=actor_values,
    )


def _save_price_rules(video):
    """Rebuild time-based price rules from posted form data."""
    video.price_rules.delete()
    froms = request.form.getlist("rule_from[]")
    tos = request.form.getlist("rule_to[]")
    prices = request.form.getlist("rule_price[]")
    from datetime import time as time_cls
    for f, t, p in zip(froms, tos, prices):
        f, t, p = f.strip(), t.strip(), p.strip()
        if not (f and t and p):
            continue
        try:
            fh, fm = f.split(":")
            th, tm = t.split(":")
            db.session.add(VideoPriceRule(
                video_id=video.id,
                time_from=time_cls(int(fh), int(fm)),
                time_to=time_cls(int(th), int(tm)),
                price=int(p),
            ))
        except (ValueError, AttributeError):
            pass
    db.session.commit()
