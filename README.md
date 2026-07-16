# WhatsApp Order Bot — Deploy Tonight

FastAPI + Meta Cloud API + Claude Haiku. Multi-tenant WhatsApp bots with
optional Postgres persistence and an admin dashboard at `/dashboard`.

## Deploy steps (45-60 min total)

### 1. Railway (10 min)
- Push this folder to a GitHub repo, connect to Railway
- Add a **PostgreSQL** plugin (sets `DATABASE_URL`)
- Set env vars from `.env.example` (WhatsApp, Anthropic, dashboard creds)
- Build runs `dashboard-ui` via `nixpacks.toml` → static files in `app/static/dashboard`
- Note your public URL: `https://xxxx.up.railway.app`

### 2. Meta app (15 min)
- https://developers.facebook.com/apps → Create App → Business type
- Add Product → WhatsApp → Set up
- Copy the **temporary token** and **Phone Number ID** into Railway env vars
  (swap for a permanent System User token before real clients)
- Add your own WhatsApp number as a test recipient, verify the code

### 3. Webhook (5 min)
- Meta dashboard → WhatsApp → Configuration
- Callback URL: `https://xxxx.up.railway.app/webhook`
- Verify token: whatever you set as WHATSAPP_VERIFY_TOKEN
- Click Verify and Save → subscribe to **messages** field

### 4. Admin dashboard
- URL: `https://xxxx.up.railway.app/dashboard`
- Set `DASHBOARD_USER`, `DASHBOARD_PASSWORD`, `DASHBOARD_JWT_SECRET` (all three required)
- Without those vars the bot still runs; dashboard API returns 404
- Without `DATABASE_URL` the dashboard API returns 503 (in-memory bot mode)

### Local dashboard UI build
```bash
cd dashboard-ui && npm ci && npm run build
# output → app/static/dashboard/  (served by FastAPI at /dashboard)
npm run dev   # Vite on :5173, proxies /api → :8000
```

### 5. Test (5 min)
- Message the test number from your phone: "menu"
- Order something, give an address, confirm
- Owner number (OWNER_WHATSAPP env var) receives the order slip

## Commands customers can use
- `menu` — bot shows the menu (via Claude)
- `reset` / `restart` / `naya order` — clears the conversation

## Per-client onboarding checklist (after first sale)
1. Copy repo → new Railway service
2. Edit `menu.json` (shop name, items, prices, delivery fee/area)
3. Fresh SIM → register on Cloud API under client's or your WABA
4. Set OWNER_WHATSAPP to shop owner's personal number
5. Start Meta Business verification (2 days–2 weeks, runs in background)
6. Print counter sticker with the ordering number

## Known v1 limits (fine for pilot)
- Without `DATABASE_URL`, sessions are in-memory (restart clears them)
- Text messages only (images/voice get a polite redirect)
- Order slip goes to owner via WhatsApp free-window — works only if
  owner has messaged the bot number once (do this during setup)

## Demo video for pitching (do this right after first successful test)
Screen-record: customer sends "menu" → orders 2 items → gives address →
confirms → cut to owner's phone receiving the order slip. 60 seconds.
That video IS the sales pitch.
