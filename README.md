# WhatsApp Order Bot

FastAPI + Meta Cloud API + Claude Haiku. Multi-tenant WhatsApp bots with
optional Postgres persistence and an admin dashboard at `/dashboard`.

The repo is split into two independent projects:

```
whatsapp-order-bot/
├── backend/     # Python / FastAPI API + bot + Alembic migrations
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── menu.json
│   ├── requirements.txt
│   ├── Procfile
│   ├── railway.toml
│   └── .env            # backend secrets (not committed)
└── frontend/    # React + Vite admin dashboard
    ├── src/
    ├── package.json
    └── .env            # frontend config (not committed)
```

Each project has its own `.env` and runs on its own. The frontend's
`npm run build` emits static files into `backend/app/static/dashboard`,
which FastAPI serves at `/dashboard` in production.

---

## Backend (`backend/`)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in your secrets
uvicorn app.main:app --reload --port 8000
```

- API + webhook: `http://127.0.0.1:8000`
- **Health:** `GET /health` (full system state) · `GET /healthz` (liveness) · `GET /readyz` (DB readiness)
- Legacy alias: `GET /` returns the same JSON as `/health`
- Migrations run automatically on startup (Alembic) when `DATABASE_URL` is set.
- Run tests from repo root: `python3 -m pytest backend/tests`
- Lint: `cd backend && ruff check .`

## Frontend (`frontend/`)

```bash
cd frontend
npm install
cp .env.example .env          # optional; defaults to backend on :8000
npm run dev                   # Vite dev server on http://127.0.0.1:5173
```

- Dev server proxies `/api/*` to the backend (`VITE_API_TARGET`, default `http://127.0.0.1:8000`).
- Production build: `npm run build` → outputs to `backend/app/static/dashboard`.
- Preview a built bundle: `npm run preview`.

Run both together (two terminals): start the backend, then the frontend.

---

## Deploy (Railway)

Railway should use **Root Directory = `backend`**. The repo root is not a valid Python package root.

### 1. Create the service

1. New project → **Deploy from GitHub** (this repo).
2. Service settings → **Root Directory** = `backend`.
3. Add **PostgreSQL** plugin → Railway injects `DATABASE_URL` (the app normalises `postgres://` → `postgresql+asyncpg://`).

### 2. Required environment variables

Copy from `backend/.env.example` into the Railway service:

| Variable | Required |
|----------|----------|
| `WHATSAPP_VERIFY_TOKEN` | Yes |
| `WHATSAPP_ACCESS_TOKEN` | Yes |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes (single-tenant fallback; multi-tenant uses DB) |
| `ANTHROPIC_API_KEY` | Yes |
| `DASHBOARD_USER` | Yes for dashboard |
| `DASHBOARD_PASSWORD` | Yes for dashboard |
| `DASHBOARD_JWT_SECRET` | Yes for dashboard |
| `DATABASE_URL` | Yes for dashboard + persistence (from Postgres plugin) |
| `OWNER_WHATSAPP`, `FLOW_MODE`, … | As needed per tenant / seed |

Without all three `DASHBOARD_*` vars, the bot still runs; dashboard **API** routes return 404.  
Without `DATABASE_URL`, the bot uses in-memory sessions; dashboard API returns 503.

### 3. Build the dashboard static files

The backend serves the React app from `backend/app/static/dashboard/`.  
**Commit the built assets** or add a build step before deploy:

```bash
cd frontend
npm ci
npm run build    # writes to ../backend/app/static/dashboard
```

If `index.html` is missing, `/dashboard` returns 503 (API and webhook still work).

### 4. Start command

Default (from `backend/railway.toml` / `Procfile`):

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

On boot the app:

1. Runs Alembic migrations to `head` (Postgres advisory lock; waits, does not skip).
2. Seeds admin user if `DASHBOARD_*` set and no users exist.
3. Syncs env/registry tenants into DB when `DATABASE_URL` is set.
4. Mounts `/dashboard` when static files exist.

### 5. Verify after deploy

```bash
curl -s https://YOUR-APP.up.railway.app/health | jq
curl -s -o /dev/null -w "%{http_code}\n" https://YOUR-APP.up.railway.app/dashboard/
curl -s https://YOUR-APP.up.railway.app/readyz
```

`/health` should show `database.connected: true`, `migrations_at_head: true`, `dashboard.mounted: true`, and your tenant list when DB is populated.

### 6. Meta webhook

- Callback URL: `https://YOUR-APP.up.railway.app/webhook`
- Verify token: same as `WHATSAPP_VERIFY_TOKEN` → Verify & Save → subscribe to **messages**.

### Admin dashboard

- URL: `https://YOUR-APP.up.railway.app/dashboard`
- Login with `DASHBOARD_USER` / `DASHBOARD_PASSWORD`.

---

## Deploy (local production smoke)

```bash
cd frontend && npm run build
cd ../backend
export WHATSAPP_VERIFY_TOKEN=... WHATSAPP_ACCESS_TOKEN=... ANTHROPIC_API_KEY=...
# optional: export DATABASE_URL=...
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/health` and `http://localhost:8000/dashboard/`.

---

## Commands customers can use
- `menu` — bot shows the menu (via Claude)
- `reset` / `restart` / `naya order` — clears the conversation

## Per-client onboarding checklist (after first sale)
1. Copy repo → new Railway service.
2. Edit `backend/menu.json` (shop name, items, prices, delivery fee/area).
3. Fresh SIM → register on Cloud API under client's or your WABA.
4. Set `OWNER_WHATSAPP` to shop owner's personal number.
5. Start Meta Business verification (runs in background).
6. Print counter sticker with the ordering number.

## Known v1 limits (fine for pilot)
- Without `DATABASE_URL`, sessions are in-memory (restart clears them).
- Text messages only (images/voice get a polite redirect).
- Order slip goes to owner via WhatsApp free-window — works only if the
  owner has messaged the bot number once (do this during setup).
- Webhook POST is not HMAC-validated (see `STATUS.md`).
- Single `WHATSAPP_ACCESS_TOKEN` shared across all tenants.

For a full feature/test map see [STATUS.md](STATUS.md).
