# Treekipedia User System

**Status**: Ready to implement
**Priority**: High — prerequisite for credit system, saved analyses, research history
**Date**: 2026-04-17 (revised 2026-04-18)

## Problem

Treekipedia has no user table. When a Silvi user logs in (email OTP → Django JWT, or Google SSO → Django JWT), the Express backend knows their `user_id` and `token_type` from the JWT, but stores nothing locally. The credit system works around this by lazily creating a `credit_balances` row on first use, scattering "new user" logic across `getBalance()`, `deductCredits()`, and `grantSignupBonus()`. This is fragile and makes it impossible to answer basic questions like "how many users does Treekipedia have?"

## Goal

A `treekipedia_users` table that tracks every Silvi user who has authenticated with Treekipedia. One row per user, created once at login via an explicit endpoint, used as the anchor for credits, saved analyses, preferences, and future user-linked features.

## Current State

- `backend/middleware/userAuth.js`: `optionalAuth` (global) + `authenticateUser` decode Django HS256 JWTs → `req.user = { id, token_type }`. JWT contains `user_id` but NOT email/name.
- `backend/services/creditService.js`: lazy signup bonus in `getBalance` (line 23-30) and `deductCredits` (line 50-62). `credit_balances` and `credit_transactions` use bare `user_id INTEGER`, no FK.
- `database/11_user_analyses.sql`: `user_analyses` table exists with bare `user_id INTEGER`, no FK.
- `frontend/auth.ts`: NextAuth session contains `email`, `name`, `access`, `refresh`. Email comes from OTP form input or Google profile.
- No `/user/*` or `/profile/*` routes exist.
- Email OTP + Google SSO both live in production (2026-04-18).

## Design

**Guiding principle**: one explicit entry point for registration, not hidden upserts on every request.

### Phase 1: Database

`database/13_treekipedia_users.sql`:

```sql
CREATE TABLE treekipedia_users (
  id SERIAL PRIMARY KEY,
  silvi_user_id INTEGER UNIQUE NOT NULL,
  email VARCHAR(255),
  display_name VARCHAR(100),
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ DEFAULT NOW(),
  preferences JSONB DEFAULT '{}'
);

CREATE INDEX idx_tk_users_email ON treekipedia_users(email);
-- (silvi_user_id unique constraint already provides an index)
```

### Phase 2: User Service

`backend/services/userService.js` — one function does all the heavy lifting:

```js
async function ensureUser(userId, { email = null, displayName = null } = {}, client = null) {
  const db = client || pool;
  const { rows } = await db.query(`
    INSERT INTO treekipedia_users (silvi_user_id, email, display_name, last_seen_at)
    VALUES ($1, $2, $3, NOW())
    ON CONFLICT (silvi_user_id) DO UPDATE
      SET email = COALESCE(treekipedia_users.email, EXCLUDED.email),
          display_name = COALESCE(treekipedia_users.display_name, EXCLUDED.display_name),
          last_seen_at = NOW()
    RETURNING *, (xmax = 0) AS is_new
  `, [userId, email, displayName]);

  const user = rows[0];
  if (user.is_new) {
    await creditService.grantSignupBonus(userId, client);
  }
  return user;
}
```

- Accepts optional `client` so it can participate in a caller's transaction (used by the safety net in `deductCredits`)
- Uses `(xmax = 0)` Postgres trick to detect whether the row was inserted (new user) vs updated (existing)
- `COALESCE` in the UPDATE preserves existing email/display_name if row already had them — safe for idempotent calls

Other exports: `getProfile(userId)`, `updateProfile(userId, updates)`.

### Phase 3: User API

`backend/routes/user.js` (mounted at `/api/user`), all require `authenticateUser`:

```
POST /api/user/profile          — upsert via ensureUser(req.user.id, req.body); return {profile, credits}
GET  /api/user/profile          — read profile + credit balance
```

Request body for POST: `{ email, display_name? }`. Response: `{ profile, credits: { balance, lifetime_purchased, lifetime_spent } }`.

### Phase 4: Credit Service Cleanup

- `getBalance()`: if no row, return `{ balance: 0, lifetime_purchased: 0, lifetime_spent: 0 }` — NO lazy creation.
- `deductCredits()`: if `SELECT FOR UPDATE` returns no row, call `userService.ensureUser(userId, {}, client)` within the SAME transaction, then re-SELECT. This is the safety net — covers any flow that bypasses `POST /profile`.
- `grantSignupBonus()`: accepts optional `client`, otherwise gets one from pool. Called ONLY from `userService.ensureUser`.

Safety net keeps the system robust if the frontend POST is missed (API-only clients, network failures, future mobile app), but concentrates the "create + bonus" logic in userService instead of duplicating it across the credit service.

### Phase 5: Frontend Wiring

In `frontend/auth.ts`'s `signIn` callback, after successful auth (both OTP and Google):

```ts
fetch(`${TREEKIPEDIA_API_URL}/api/user/profile`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${access}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ email: profile?.email || user?.email, display_name: profile?.name || user?.name }),
}).catch((err) => console.error('Treekipedia profile sync failed:', err));
```

- Fire-and-forget — does NOT block login
- Runs once per login
- Errors are logged, but login still succeeds (safety net in deductCredits covers the gap)

### Phase 6: Future (not in this pass)

- Profile page at `/profile` — display name, credit balance, transaction history
- Navbar: show display name alongside `CreditBalance`
- FK constraints: `credit_balances.user_id` → `treekipedia_users.silvi_user_id`, same for `credit_transactions` and `user_analyses` (verify no orphans first)
- `user_research_history` table

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Registration trigger | Explicit `POST /api/user/profile` at login | One place, observable, doesn't add DB writes to every authed request |
| Rejected: middleware upsert | Too much work per request; can't capture email anyway (JWT lacks it) | Would still need a separate profile endpoint for email sync |
| Safety net location | `creditService.deductCredits` → `userService.ensureUser(client)` | Covers clients that skip the frontend POST, without scattering logic |
| `user_id` type | `silvi_user_id INTEGER` = Django `auth_user.id` | Same ID everywhere, no separate identity layer |
| Signup bonus moment | Inside `userService.ensureUser` on INSERT (is_new=true) | Atomic with user creation, not a separate step |
| Email source | Frontend POST body after login | JWT doesn't carry it; frontend has it from NextAuth session |
| Transaction participation | `ensureUser(..., client)` accepts optional client | Lets safety-net call participate in `deductCredits` transaction |

## Implementation Order

1. Write + apply `13_treekipedia_users.sql`
2. Create `services/userService.js` (ensureUser, getProfile, updateProfile)
3. Create `controllers/user.js` + `routes/user.js`, wire into `server.js`
4. Refactor `creditService.js`: strip lazy bonus, add safety-net call, make `grantSignupBonus` client-aware
5. Wire `POST /api/user/profile` into `frontend/auth.ts` signIn callback
6. Deploy (backend: push → PM2 restart; frontend: push → Vercel autodeploy)
7. Verify: fresh Google login → check `treekipedia_users` row created + 100-credit signup bonus granted

## Open Questions (Deferred)

- **FK constraints on existing tables**: Safe to add now if `credit_balances`/`credit_transactions`/`user_analyses` have 0 rows. If any rows exist, need to backfill `treekipedia_users` from those user_ids first. Verify row counts before Phase 6.
- **Do we need `display_name` now?** Column stays nullable. Frontend can send `profile.name` from Google, null from OTP. User-editable later.
- **Avatar URL**: Google returns `picture` in profile. Capture it in POST if we want, display in future profile page.
