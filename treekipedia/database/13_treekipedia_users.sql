-- Treekipedia Users: anchor table for every Silvi user who authenticates with Treekipedia
-- Migration: 13_treekipedia_users.sql
--
-- One row per user, created once via POST /api/user/profile at login.
-- silvi_user_id matches Django auth_user.id (the user_id embedded in Django JWTs).
-- Signup bonus (100 credits) is granted atomically on first INSERT by userService.ensureUser.

CREATE TABLE IF NOT EXISTS treekipedia_users (
  id SERIAL PRIMARY KEY,
  silvi_user_id INTEGER UNIQUE NOT NULL,
  email VARCHAR(255),
  display_name VARCHAR(100),
  avatar_url TEXT,
  preferences JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tk_users_email ON treekipedia_users(email);
