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
- Health check: `GET /`
- Migrations run automatically on startup (Alembic) when `DATABASE_URL` is set.
- Run tests: `cd backend && pytest`

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

- Create **two** services (or set the service **Root Directory**):
  - Backend service → Root Directory = `backend` (uses `backend/railway.toml` + `requirements.txt`).
  - Add a **PostgreSQL** plugin (sets `DATABASE_URL`).
- Set backend env vars from `backend/.env.example` (WhatsApp, Anthropic, dashboard creds).
- Build the dashboard once (`cd frontend && npm run build`) so the static files
  under `backend/app/static/dashboard` are deployed with the backend, or add a
  build step that runs it.
- Note your public URL: `https://xxxx.up.railway.app`.

### Meta app + webhook
- https://developers.facebook.com/apps → Create App → Business type → add WhatsApp.
- Copy the **temporary token** and **Phone Number ID** into backend env vars
  (swap for a permanent System User token before real clients).
- Webhook Callback URL: `https://xxxx.up.railway.app/webhook`
- Verify token: whatever you set as `WHATSAPP_VERIFY_TOKEN` → Verify & Save → subscribe to **messages**.

### Admin dashboard
- URL: `https://xxxx.up.railway.app/dashboard`
- Set `DASHBOARD_USER`, `DASHBOARD_PASSWORD`, `DASHBOARD_JWT_SECRET` (all three required).
- Without those vars the bot still runs; dashboard API returns 404.
- Without `DATABASE_URL` the dashboard API returns 503 (in-memory bot mode).

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
