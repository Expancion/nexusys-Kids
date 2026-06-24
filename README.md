# 🚀 Nexusys Junior

A self-hosted, parent-controlled media kiosk for children. Kids earn stars by completing chores, spend them on videos and rewards. Parents manage everything from a clean admin panel.

Built with Flask + PostgreSQL + Docker. Runs on any home server or Raspberry Pi.

---

## ✨ Features

### For Kids (Kiosk)
- 🎬 **Video library** — YouTube videos organized by category and channel
- 🎮 **Educational games** — Letters and Numbers minigames
- ⭐ **Points system** — earn stars by completing daily chores
- 📋 **Weekly chore calendar** — tap to mark chores done
- 🛒 **Reward shop** — spend stars on real-world rewards
- 🏆 **Achievements** — unlock badges for milestones (streaks, chores, videos)
- 🎯 **Goals** — set a savings target, watch the progress bar fill up
- 📊 **History** — full transaction log of earned/spent stars
- 💬 **Parent messages** — popup notifications from parent ("Dinner in 5 min!")
- 🔥 **Streaks** — consecutive days with completed chores

### For Parents (Admin Panel)
- 📊 **Dashboard** — overview of all children, today's activity, recent events
- 👶 **Child profiles** — points, avatar, video cost, daily video limit
- 📺 **Video management** — add individual videos or import entire YouTube playlists
- 📥 **Playlist import** — bulk import via YouTube Data API v3
- 🧩 **Kiosk tiles** — customize which apps appear on the kiosk home screen, with bilingual names
- ⭐ **Reward tasks** — define quick-award tasks for easy point granting
- 📋 **Daily chores** — assign chores per weekday, set point rewards
- 🔒 **Schedule locks** — automatically lock the kiosk during homework/sleep hours
- 🛒 **Reward shop management** — create/edit redeemable rewards
- 🎯 **Goals** — set savings goals for each child
- 📊 **Statistics** — charts for points, videos, chores over the last 14 days
- 💬 **Send messages** — send popup notifications directly to the kiosk
- 🌐 **CZ/EN interface** — full Czech and English translation throughout
- 💻 **NixOS kiosk config** — one-click download of a pre-filled NixOS config per device
- 📖 **Built-in guide** — bilingual help page explaining every feature

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, Flask 3, SQLAlchemy 2, Flask-Migrate |
| i18n | Flask-Babel 4.x, gettext (.po/.mo) |
| Database | PostgreSQL 16 |
| Frontend | Tailwind CSS (CDN), vanilla JS |
| Reverse proxy | Caddy 2 (automatic HTTPS) |
| Container | Docker + Docker Compose |
| Kiosk OS | NixOS + KDE Plasma (locked Chromium kiosk mode) |

---

## 🚀 Quick Start

### Prerequisites
- Docker + Docker Compose
- A domain or local hostname (for Caddy HTTPS) — or run on `localhost`

### 1. Clone

```bash
git clone https://github.com/your-username/nexusys-junior.git
cd nexusys-junior
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
- `SECRET_KEY` — long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)
- `POSTGRES_PASSWORD` — database password (also update in `DATABASE_URL`)
- `NEXUSYS_PUBLIC_URL` — your server's public URL (used in generated NixOS configs)
- `YOUTUBE_API_KEY` — optional, needed for playlist import ([get one free](https://console.cloud.google.com/))

### 3. Start

```bash
docker compose up -d
```

### 4. First-run setup wizard

Open `http://localhost` in your browser. You will be redirected to `/setup` automatically.

1. **Choose language** — Czech 🇨🇿 or English 🇬🇧 (sets the default for all users)
2. **Set admin password** — stored as a scrypt hash in the database (minimum 6 characters)
3. Click **Complete setup** — you're taken straight to the admin panel

> The setup page only appears once. To reset: run `docker compose exec web python -c "from run import app; from app.models import SystemConfig; from app.extensions import db; app.app_context().push(); SystemConfig.set('setup_complete', '0')"` then revisit `/setup`.

### 5. Access

| URL | Description |
|-----|-------------|
| `http://localhost` | Kiosk home screen |
| `http://localhost/admin` | Parent admin panel |
| `http://localhost/kiosk/1` | Child kiosk (replace `1` with child ID) |
| `http://localhost/admin/help` | Built-in bilingual user guide |
| `http://localhost/api/` | API documentation |

---

## ⚙️ Configuration

All configuration is via environment variables in `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Flask session secret |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `POSTGRES_USER` | ✅ | DB username (for postgres service) |
| `POSTGRES_PASSWORD` | ✅ | DB password |
| `POSTGRES_DB` | ✅ | DB name |
| `NEXUSYS_PUBLIC_URL` | ✅ | Public server URL — embedded in generated NixOS kiosk configs |
| `YOUTUBE_API_KEY` | ❌ | Enables YouTube playlist import and auto title fetch |
| `APP_PORT` | ❌ | Internal app port (default: 8080) |

> **Admin password** is no longer set via env var. It is configured through the first-run setup wizard and stored as a scrypt hash in the database.

---

## 💻 NixOS Kiosk Setup

Each child device runs NixOS with a locked Chromium session managed by the Nexus Kiosk Agent.

### How it works

1. In **Admin → Children → [child] → Add device**, create a device with a unique key (e.g. `living-room-laptop`).
2. Click **↓ NixOS** next to the device to download a pre-filled `<device-key>.nix` configuration file.
3. On the laptop:

   ```bash
   # Copy the downloaded config
   cp living-room-laptop.nix /etc/nixos/configuration.nix
   # Export and place your Caddy internal CA certificate
   cp caddy-ca.crt /etc/nixos/caddy-ca.crt
   # Apply
   nixos-rebuild switch
   ```

4. The laptop boots into a locked KDE Plasma session. Chromium opens in kiosk mode.
5. The **Nexus Kiosk Agent** (systemd user service) polls `/api/device-policy?deviceId=…` every 15 seconds:
   - **Allowed** → opens the child's kiosk page
   - **Blocked** → shows a fullscreen lock page with your custom message

Toggle **Allowed / Blocked** from the admin panel to lock/unlock any device instantly.

---

## 🌐 Internationalisation

The interface supports **Czech** and **English** throughout — admin panel, kiosk, and setup wizard.

- Language is stored in a `lang` cookie (365-day TTL).
- The **CS / EN** toggle is available in the admin sidebar and on the kiosk home screen.
- The default language is chosen during the setup wizard and stored in the database.
- Translation files: `app/translations/cs/LC_MESSAGES/messages.po` and `.../en/...`
- After editing `.po` files, recompile: `docker compose exec web pybabel compile -d app/translations`

---

## 📁 Project Structure

```
nexusys-junior/
├── app/
│   ├── achievements.py         # Achievement definitions + award logic
│   ├── models.py               # SQLAlchemy models (incl. SystemConfig)
│   ├── extensions.py           # Flask extensions (db, migrate, babel)
│   ├── factory.py              # App factory, locale selector
│   ├── config.py               # App configuration
│   ├── translations/
│   │   ├── cs/LC_MESSAGES/     # Czech .po/.mo
│   │   └── en/LC_MESSAGES/     # English .po/.mo
│   ├── modules/
│   │   ├── admin/routes.py     # Admin panel routes
│   │   ├── api/routes.py       # REST API
│   │   ├── games/routes.py     # Educational games
│   │   └── main/routes.py      # Kiosk routes + setup wizard
│   └── templates/
│       ├── admin/              # Admin panel templates
│       ├── kiosk/              # Child kiosk templates
│       ├── setup.html          # First-run setup wizard
│       └── api/                # API docs template
├── migrations/                 # Alembic database migrations
├── caddy/                      # Caddy reverse proxy config
├── babel.cfg                   # pybabel extraction config
├── docker-compose.yml
├── dockerfile
├── entrypoint.sh               # DB migration + translation compile + gunicorn
├── requirements.txt
└── .env.example
```

---

## 🔌 REST API

The kiosk communicates with the backend via a simple REST API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/device-policy?deviceId=X` | Check if device is allowed |
| `POST` | `/api/kiosk/watch` | Watch a video (deducts points) |
| `POST` | `/api/kiosk/chore/complete` | Mark chore as done (awards points) |
| `GET` | `/api/child/:id/balance` | Get current point balance |
| `GET` | `/api/child/:id/inbox` | Fetch unread parent messages |
| `POST` | `/api/shop/buy` | Purchase a reward |
| `POST` | `/api/game/start` | Start a game session |
| `POST` | `/api/game/reward` | Award points for game performance |

Full interactive docs available at `/api/`.

---

## 🏆 Achievements

Achievements are earned automatically when conditions are met:

| Achievement | Condition | Bonus |
|-------------|-----------|-------|
| 🌟 First step | First chore completed | +5 ⭐ |
| 💪 Diligent helper | 10 chores total | +15 ⭐ |
| 🎖️ Task master | 50 chores total | +50 ⭐ |
| 🔥 Triple combo | 3-day streak | +10 ⭐ |
| ⚡ Weekly warrior | 7-day streak | +25 ⭐ |
| 🏆 Unbeatable | 30-day streak | +100 ⭐ |
| 💰 Saver | 50 points at once | — |
| 💎 Rich kid | 200 points at once | — |
| 🛒 First purchase | First shop purchase | +5 ⭐ |
| 🎬 Viewer | 5 videos watched | +5 ⭐ |
| 🎥 Film buff | 25 videos watched | +10 ⭐ |

To add custom achievements, edit `app/achievements.py`.

---

## 🔒 Security Notes

- Admin password is set via the **first-run setup wizard** and stored as a **scrypt hash** (werkzeug 3.x) in the database — never in plaintext
- The `.env` file is excluded from git via `.gitignore` — never commit it
- Use a strong random `SECRET_KEY` in production
- Caddy handles HTTPS automatically with internal CA for LAN deployments
- The kiosk `kid` user has no sudo access; the NixOS config disables wallet, screen lock, and power buttons

---

## 🐳 Development

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f web

# Run database migrations after model changes
docker compose exec web flask db migrate -m "description"
docker compose exec web flask db upgrade

# Recompile translations after editing .po files
docker compose exec web pybabel compile -d app/translations

# Restart app after Python changes
docker compose restart web

# Open a shell in the container
docker compose exec web bash
```

> **Note:** HTML templates reload automatically. Python code changes require `docker compose restart web`.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a Pull Request

### Roadmap / Ideas

- [ ] Favorite videos — bookmark system in kiosk
- [ ] Watch time tracking — measure minutes, not just count
- [ ] Weekly email report for parents
- [ ] Multiple kiosk themes per child
- [ ] Content age ratings

---

## 📄 License

MIT — see [LICENSE](LICENSE)
