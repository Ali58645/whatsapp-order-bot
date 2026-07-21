# BahiDesk / WhatsApp Order Bot — Status Map

*Generated: stabilization pass. Honest inventory of what exists, what is tested, and what is stubbed.*

---

## Test & lint baseline

| Check | Result |
|-------|--------|
| **pytest** (`python3 -m pytest backend/tests` from repo root) | **214 passed**, 0 failed, 0 skipped |
| **ruff** (`cd backend && ruff check .`) | **All checks passed** |
| **Frontend tests** | None (no Jest/Vitest suite) |

### Warnings (not failures)

- `AsyncSession.close` never awaited — appears in several DB-heavy tests (async teardown noise).
- `Event loop is closed` — occasional aiosqlite thread warning in `test_tenant_mgmt`.
- Pending fire-and-forget tasks (`_db_save_order_state`) at pytest shutdown — tests still pass.

### Test coverage by area

| Area | Test file(s) | Notes |
|------|----------------|-------|
| Webhook + Claude fallback | `test_webhook.py` | |
| Multi-tenant routing | `test_multi_tenant.py` | Includes `GET /` tenant list |
| Lead gate / campaign | `test_gate_lead.py`, `test_entry_intent.py` | |
| Lead flow / interactive | `test_interactive.py`, `test_flow_integration.py` | |
| Order / menu v2 | `test_menu_v2.py` | |
| Google Sheets | `test_sheet.py` | Mocked I/O |
| Dashboard API | `test_dashboard.py`, `test_owner_dashboard.py` | |
| Tenant lifecycle | `test_tenant_mgmt.py` | pause/archive/delete |
| Onboarding wizard API | `test_onboarding.py` | draft/activate/verify |
| Templates | `test_templates.py` | |
| Persistence / DB store | `test_persistence.py` | |
| Conversations send | `test_conversation_send.py` | |
| Config validation | `test_tenant_config.py`, `test_flow_builder.py` | |
| Regression bugs | `test_bugs.py`, `test_business_name_and_bidi.py` | |

**Not covered by automated tests:** `/health` field-by-field assertions, `/readyz`, dashboard static serving, Railway boot with real Postgres, Meta webhook HMAC, live Graph/Anthropic/Sheets calls.

---

## Health & ops endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | **System snapshot** — DB enabled/connected, tenant count + statuses, dashboard mounted, `migrations_at_head` |
| `GET /` | Same payload as `/health` (legacy alias) |
| `GET /healthz` | Liveness — `{ "status": "ok" }` |
| `GET /readyz` | Readiness — DB `SELECT 1` when `DATABASE_URL` set; 503 if DB down |

When `DATABASE_URL` is set but unreachable, `/health` reports `status: degraded`, `database.connected: false`, and falls back to in-memory tenant registry for the `tenants` list.

---

## Features: tested / partial / stub

### WhatsApp bot (webhook)

| Feature | Status | Tests |
|---------|--------|-------|
| Webhook verify (GET) | **Works** | `test_webhook.py` |
| Webhook POST routing by `phone_number_id` | **Works** | `test_multi_tenant.py` |
| Lead flow (campaign, interactive, Claude) | **Works** | `test_gate_lead.py`, `test_interactive.py`, … |
| Order flow (legacy menu + Claude) | **Works** | `test_webhook.py`, `test_multi_tenant.py` |
| Order flow menu_v2 (interactive cart) | **Works** | `test_menu_v2.py` |
| Tenant status gating (draft/paused/archived → no reply) | **Works** | `test_tenant_mgmt.py` |
| Webhook **HMAC signature** validation | **Incomplete** | Not implemented — any POST to `/webhook` is accepted |
| Per-tenant Graph API tokens | **Incomplete** | Single `WHATSAPP_ACCESS_TOKEN` for all tenants |

### Persistence

| Feature | Status | Tests |
|---------|--------|-------|
| Postgres sessions / leads / orders / events | **Works** | `test_persistence.py`, dashboard tests |
| In-memory fallback (no `DATABASE_URL`) | **Works** | Most tests |
| Alembic migrations on startup | **Works** | Implicit in DB tests; `migrations_at_head` on `/health` |
| Fire-and-forget DB writes in webhook | **Works** | Errors logged, reply not blocked |

### Google Sheets

| Feature | Status | Tests |
|---------|--------|-------|
| Lead upsert (async, timeout, no raise) | **Works** | `test_sheet.py` |
| Onboarding sheet test API | **Works** | `test_onboarding.py` |
| Order flow → sheet | **N/A** | Orders go to owner WhatsApp, not sheet |

### Anthropic (Claude)

| Feature | Status | Tests |
|---------|--------|-------|
| Lead + order replies with fallback message | **Works** | `test_webhook.py` |
| FAQ semantic match via Claude | **Works** | Partial via lead tests; `faq.py` has try/except |
| API errors → fallback text, webhook still 200 | **Works** | `test_post_text_message_claude_error_returns_fallback` |

### Admin dashboard (API)

| Feature | Status | Tests |
|---------|--------|-------|
| JWT login | **Works** | `test_dashboard.py` |
| Businesses list + lifecycle (live/paused/archived/draft) | **Works** | `test_tenant_mgmt.py` |
| Onboarding draft + activate | **Works** | `test_onboarding.py` |
| WhatsApp verify + subscribe (Graph) | **Works** (API) | `test_onboarding.py` (mocked Graph) |
| Config save / menu publish / messages publish | **Works** | `test_menu_v2.py`, `test_owner_dashboard.py` |
| Templates apply | **Works** | `test_templates.py` |
| Team / users CRUD | **Works** | `test_owner_dashboard.py` |
| Access log | **Works** | `test_tenant_mgmt.py` (partial) |
| View-as owner (support mode) | **Works** | `test_owner_dashboard.py` |
| Billing API | **Stub** | Returns placeholder usage (`messages_sent: 0`, `placeholder: true`) — no metering backend |
| Overview metrics API | **Works** | Used by UI; light test via dashboard |

### Admin dashboard (UI)

| Page / flow | Status | Backend tests |
|-------------|--------|---------------|
| Login | **Works** | — |
| Businesses + onboarding wizard | **Works** | API tested |
| Settings (wiring, content, menu, flow) | **Works** | API tested |
| Team | **Works** | API tested |
| Access log | **Works** | API tested |
| Billing | **Stub UI** | Shows placeholder API data |
| `Overview.tsx` | **Incomplete** | Component exists but **no route** in `App.tsx` (metrics shown on Businesses / OwnerHome instead) |
| Settings: WhatsApp “Test connection” | **Incomplete** | Verify only in Businesses wizard, not Settings |

### Owner workspace

| Feature | Status | Tests |
|---------|--------|-------|
| Owner home metrics | **Works** | — |
| Customers → Leads or Orders | **Works** | API tested |
| My bot / menu settings | **Works** | `test_owner_dashboard.py` |
| Conversations + send | **Works** | `test_conversation_send.py` |
| Activity / events | **Works** | — |

---

## Error resilience (webhook path)

| External call | Guarded? | Behavior on failure |
|---------------|----------|---------------------|
| **Graph API** (`send_whatsapp_message`) | **Yes** | try/except → log, return `False`; caller continues |
| **Anthropic** (lead/order reply) | **Yes** | try/except → fallback message text |
| **Anthropic** (FAQ classify) | **Yes** | try/except → `None`, skip FAQ |
| **Google Sheets** (`upsert_lead`) | **Yes** | timeout + try/except, never raises |
| **DB** (session/lead/order/event saves) | **Yes** | `_db_*` helpers catch/log; fire-and-forget tasks |
| **DB** (`resolve_tenant`) | **Partial** | On DB error, falls back to env/registry tenant |
| **order_flow.py** | **Relies on send_fn** | Uncaught exceptions in flow logic itself could still 500 the webhook — no top-level try on `_handle_order_flow` / `_handle_lead_flow` |
| **Lead/order owner forward** | **Partial** | Retries via `send_fn`; depends on `send_whatsapp_message` not raising (now safe) |

### Unguarded / known gaps

1. **Webhook HMAC** — not validated; malicious POSTs possible if URL is known.
2. **Unhandled exceptions** in lead/order flow logic (bugs, bad payload shapes) — no outer `try/except` on `receive_message`; would return 500 to Meta.
3. **Shared WhatsApp token** — one bad token affects all tenants.
4. **Multi-worker in-memory cache** — `tenant_resolver` 60s TTL per process; config change propagation delay (documented limitation).

---

## Deploy checklist (Railway)

See [README.md](README.md#deploy-railway) for step-by-step commands.

Verified locally:

- `cd backend && uvicorn app.main:app` boots with required env vars.
- `GET /health` returns JSON system state.
- `GET /dashboard/` returns **200** when `backend/app/static/dashboard/index.html` exists (run `cd frontend && npm run build` first).
- Migrations run in FastAPI lifespan before accepting traffic.

---

## Migrations (Alembic)

| Revision | Description |
|----------|-------------|
| `0001` | Initial schema |
| `0002` | Tenant config, users, history |
| `0003` | Tenant status (draft/live/paused/archived) |
| `0004` | Access logs |

---

## Recommended follow-ups (out of scope for this pass)

- Add webhook signature verification.
- Top-level exception handler on `POST /webhook` → always 200 + log.
- Per-tenant WhatsApp tokens in DB.
- Billing metering or remove placeholder UI.
- Wire or delete dead `Overview.tsx` page.
- Add `/health` contract test.
- Frontend test runner (smoke).
