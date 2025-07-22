<!-- BEGIN TALKMATE BACKEND README -->

# 🗣️ TalkMate Backend

TalkMate Backend powers a futuristic **language exchange platform** with scalable APIs, real-time WebSockets, and secure subscription management. Built with **Django REST Framework**, it manages users, rooms, subscriptions, and real-time audio/video features.

---

## 🚀 Elevator Pitch
TalkMate is a **social language-learning platform** where people connect via **live audio/video rooms** to practice speaking. It offers:

- Real-time **group audio/video calls** (up to 6 users)
- **Premium features** like private rooms, subscriptions, and video calls
- **Admin dashboard** for user, content, and report management

---

## 🛠 Features
- **Real-time Communication:** WebSockets via Django Channels + Redis.
- **Group Calls:** Mesh-based WebRTC (upgrade path to MediaSoup SFU in roadmap).
- **Subscriptions:** Razorpay integration for payments & plan upgrades.
- **Admin APIs:** KPIs, user moderation, room reports, taxonomy management, subscription controls.
- **Authentication:** JWT-based API auth + Google OAuth login.
- **Scalable Backend:** PostgreSQL + Dockerized environment + ASGI (Daphne).
- **Cloud Media:** Cloudinary for user avatars & uploads.
- **Celery Ready (Planned):** Async tasks for email, analytics, cleanup (not yet wired).

---

## 📊 Project Status
**In active development (pre‑beta).** Deploy targets:
- **Frontend:** Vercel (planned).
- **Backend:** AWS (planned).
- **Realtime media scale:** Future migration from mesh WebRTC → MediaSoup.

---

## 🧰 Tech Stack

| Layer | Tech | Version (current/pinned) | Notes |
|---|---|---|---|
| Python | CPython | 3.12+ recommended | Use venv or Docker. |
| Django |  | 5.2.1 | Main web framework. |
| Django REST Framework |  | 3.16.0 | API layer. |
| Django Channels |  | *(latest via `channels` pkg)* | WebSockets signaling. |
| channels_redis |  | *(latest)* | Redis channel layer. |
| daphne |  | *(see requirements)* | ASGI server. |
| PostgreSQL |  | 16+ recommended | Persistent DB. |
| Redis |  | 7+ | Pub/Sub + Channels. |
| Cloudinary + django-cloudinary-storage |  | latest | User media. |
| Razorpay Python SDK |  | latest | Payments. |
| google-auth |  | latest | Social login. |
| Celery |  | planned | Background tasks. |

---

## 📁 Project Structure

```
TALKMATE-BACKEND/
├── adminapp/              # Admin APIs: KPIs, moderation, subscriptions
├── backend/               # Django project (settings, urls, asgi, wsgi)
├── rooms/                 # Room models, realtime logic, signaling hooks
├── users/                 # Auth, profiles, subscription linking
├── manage.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

> **Note:** Repo path is nested under `backend/backend/` in your current local structure. Adjust import paths in `docker-compose.yml` and deployment scripts if you restructure later.

---

## ⚡ Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Aswin1819/TALKMATE-BACKEND.git
cd TALKMATE-BACKEND
```

### 2. Copy environment file & configure
```bash
cp .env.example .env
```
Edit `.env` and fill the required keys (see **Environment Variables** below).

---

### 3. Run with Docker (recommended)
If this repo is part of a **parent Talkmate project** with a root `docker-compose.yml` that includes frontend + backend + db + redis, run from that root folder. Otherwise create a local `docker-compose.yml` (see template below).

```bash
docker compose up --build
```

This starts:
- `backend` (Django ASGI + Channels)
- `db` (PostgreSQL)
- `redis` (Channels backend)
- (optional) `frontend` service if defined in root compose

---

### 4. Manual local setup (no Docker)

```bash
python -m venv env
source env/bin/activate            # Windows: env\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Apply migrations:
```bash
python manage.py migrate
```

Create a superuser (for Django admin):
```bash
python manage.py createsuperuser
```

Run dev server (ASGI aware):
```bash
python manage.py runserver 0.0.0.0:8000
```

> **Redis required:** For WebSockets/Channels to work, start Redis locally or via Docker:  
> `docker run --name talkmate-redis -p 6379:6379 -d redis:7`

---

## 🔑 Key Endpoints

| Purpose | Endpoint | Auth? | Notes |
|---|---|---|---|
| Auth / JWT | `/api/auth/` | No/Yes | Login, refresh tokens. |
| Google OAuth callback | `/api/auth/google/` | No | Exchanges token. |
| Users | `/api/users/` | JWT | Profiles, status (active/banned/flagged). |
| Rooms | `/api/rooms/` | JWT | Create/join rooms; premium private rooms gated. |
| Subscriptions | `/api/subscriptions/` | JWT | Plans, upgrade, history. |
| Admin metrics | `/api/admin/dashboard/` | Staff | KPIs, charts. |

> **WebSocket signaling:**  
> `ws://localhost:8000/ws/rooms/<room_id>/`

<!-- TODO: Replace with actual endpoint paths as defined in your urls.py -->

---

## 🔑 Environment Variables

Below is a **complete example**. Copy this into `.env.example` in your repo (safe to commit — no real secrets). Then create `.env` locally with real values.

```dotenv
# =============================
# TalkMate Backend .env.example
# =============================

# --- Core Django ---
SECRET_KEY=change-me                # Django secret
DEBUG=True                          # False in production
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://localhost:5173
CORS_ALLOWED_ORIGINS=http://localhost:5173

# --- Database ---
# Use DATABASE_URL (preferred) OR individual DB_* vars.
DATABASE_URL=postgres://postgres:postgres@db:5432/talkmate
DB_NAME=talkmate
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# --- Redis / Channels ---
REDIS_URL=redis://redis:6379/0

# --- JWT / Auth ---
# If you use SimpleJWT defaults, some of these may be configured in settings.
JWT_SIGNING_KEY=${SECRET_KEY}
ACCESS_TOKEN_LIFETIME_MIN=5
REFRESH_TOKEN_LIFETIME_DAYS=7

# --- Google OAuth ---
GOOGLE_CLIENT_ID=todo.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=todo-secret
GOOGLE_REDIRECT_URI=http://localhost:5173/oauth/google/callback

# --- Email / OTP (optional) ---
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=app-password
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Talkmate <no-reply@talkmate.test>

# --- Razorpay Payments ---
RAZORPAY_KEY_ID=todo
RAZORPAY_KEY_SECRET=todo
RAZORPAY_WEBHOOK_SECRET=todo

# --- Cloudinary Media ---
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME

# --- Media / Realtime Upgrade Path ---
USE_MEDIASOUP=False
MEDIASOUP_SIGNAL_URL=http://localhost:4443  # future SFU

# --- Misc ---
TIME_ZONE=UTC
LOG_LEVEL=INFO
```

---

## 🧪 Tests
Automated tests are **coming soon**.

Planned:
- Django unit tests
- DRF API contract tests
- WebSocket signaling integration tests

Basic manual smoke test (until test suite lands):
```bash
# 1. Create 2 users (make one premium)
# 2. Create a room via API (public)
# 3. Join from 2 browsers
# 4. Confirm audio flows both ways
# 5. Toggle hand raise -> check remote update
```

---

## 🧹 Development Tips
**Run Django checks**
```bash
python manage.py check
```

**Make migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

**Lint (if you add tooling)**
```bash
ruff check .
black .
isort .
```
<!-- TODO: Add actual linters once configured -->

---

## 🚀 Deployment (Production)

<!-- TODO: Fill in once AWS infra is finalized -->

**Planned target:** AWS (EC2 / ECS / Elastic Beanstalk — choose one).  
**Production domain (placeholder):** `https://api.talkmate.app`

**Checklist before deploy:**
- `DEBUG=False`
- `ALLOWED_HOSTS=api.talkmate.app`
- Database: production Postgres (RDS or managed)
- Redis: Elasticache or Redis Cloud
- Secure secrets (AWS Secrets Manager / SSM Parameter Store)
- HTTPS termination (ALB / Nginx / CloudFront)
- Run `python manage.py collectstatic` if using static hosting
- Apply migrations on deploy
- Configure CORS to include production frontend domain (Vercel)

---

## 📡 Realtime / WebRTC Notes
Current:
- **Mesh peer‑to‑peer** WebRTC; signaling via Django Channels.
- **Max recommended participants:** ~6 before quality issues appear.
- **Audio for all users**; **video + private rooms gated to Premium**.
- TURN/STUN: <!-- TODO: Add Coturn / public STUN server config if used -->
- Roadmap: replace mesh w/ **MediaSoup SFU** Node server.

---

## 💳 Subscriptions & Payments (Razorpay)
- Free + Premium plan model.
- Premium unlocks video + private rooms.
- Subscription history tracked per user.
- Admin can create/edit plans.
- Upgrade flow: Razorpay order → backend verify → subscription recorded.

<!-- TODO: Add webhook endpoint name if implemented. -->

---

## 🧑‍💼 Admin & Moderation
- Django Admin (`/admin/`) for superusers.
- Custom admin dashboards (frontend) consume admin APIs: KPIs, premium counts, recent activity.
- Manage: users, rooms, reports, taxonomies, subscriptions.

---

## ❗ Known Issues
- Hand raise & audio toggle not consistently syncing across clients.
- Data “lost” after Docker rebuild if Postgres volume not persisted (check compose volumes).

> Please open an issue and include logs + reproduction steps.

---

## 🤝 Contributing
We welcome contributions!

**Workflow**
1. Fork the repo.
2. Create a branch: `feature/<short-name>` or `fix/<bug>`.
3. Add tests where possible.
4. Ensure migrations and lint pass.
5. Submit a Pull Request to `main` (or `dev` if created).

**Good first issues:** docs, env validation, admin endpoints, WebRTC debug logging.

---

## 📬 Contact
Questions / support / collaboration: **aswinachumathra@gmail.com**  
<!-- TODO: Add project domain email once available -->

---

## 📜 License
<!-- TODO: Choose license: MIT / Apache-2.0 / GPL-3.0 / Proprietary -->
_If unsure, MIT is a good permissive default._

---

<!-- END TALKMATE BACKEND README -->

