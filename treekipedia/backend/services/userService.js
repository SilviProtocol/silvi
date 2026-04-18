/**
 * User Service
 * Owns the treekipedia_users table. One explicit entry point for registration
 * (ensureUser) plus read/write helpers for profile data.
 *
 * ensureUser is the canonical "first touch" for any Silvi user arriving at
 * Treekipedia. It upserts the treekipedia_users row and grants the signup
 * bonus atomically on INSERT. Callers are:
 *   - POST /api/user/profile (primary path, triggered from frontend after login)
 *   - creditService.deductCredits safety net (covers clients that skip /profile)
 *
 * The signup bonus is granted inline (direct INSERT into credit_transactions
 * with a deterministic idempotency_key) rather than via creditService, to keep
 * this module self-contained and avoid require cycles.
 */

const { SIGNUP_BONUS } = require('../config/pricing');

module.exports = (pool) => {

  /**
   * Idempotent user registration. Upserts the treekipedia_users row and grants
   * a one-time signup bonus on INSERT. Safe to call repeatedly — the bonus is
   * guarded by a deterministic idempotency key.
   *
   * @param {number} userId - Django auth_user.id (from JWT)
   * @param {object} opts
   * @param {string|null} opts.email
   * @param {string|null} opts.displayName
   * @param {string|null} opts.avatarUrl
   * @param {object|null} providedClient - Optional pg client to participate in
   *   a caller's transaction. If null, ensureUser manages its own transaction.
   * @returns {Promise<object>} treekipedia_users row with extra `is_new` boolean
   */
  async function ensureUser(userId, opts = {}, providedClient = null) {
    const { email = null, displayName = null, avatarUrl = null } = opts;
    const client = providedClient || await pool.connect();
    const manageTx = !providedClient;

    try {
      if (manageTx) await client.query('BEGIN');

      const { rows } = await client.query(
        `INSERT INTO treekipedia_users (silvi_user_id, email, display_name, avatar_url)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (silvi_user_id) DO UPDATE
           SET email = COALESCE(treekipedia_users.email, EXCLUDED.email),
               display_name = COALESCE(treekipedia_users.display_name, EXCLUDED.display_name),
               avatar_url = COALESCE(treekipedia_users.avatar_url, EXCLUDED.avatar_url),
               last_seen_at = NOW()
         RETURNING *, (xmax = 0) AS is_new`,
        [userId, email, displayName, avatarUrl]
      );

      const user = rows[0];

      if (user.is_new) {
        await client.query(
          `INSERT INTO credit_transactions
             (user_id, amount, type, reference_id, description, balance_after, metadata, idempotency_key)
           VALUES ($1, $2, 'signup_bonus', NULL, $3, $2, '{}', $4)
           ON CONFLICT (idempotency_key) DO NOTHING`,
          [userId, SIGNUP_BONUS, `Welcome bonus: ${SIGNUP_BONUS} free credits`, `signup_bonus_${userId}`]
        );
      }

      if (manageTx) await client.query('COMMIT');
      return user;
    } catch (e) {
      if (manageTx) await client.query('ROLLBACK');
      throw e;
    } finally {
      if (manageTx) client.release();
    }
  }

  async function getProfile(userId) {
    const { rows } = await pool.query(
      'SELECT id, silvi_user_id, email, display_name, avatar_url, preferences, created_at, last_seen_at FROM treekipedia_users WHERE silvi_user_id = $1',
      [userId]
    );
    return rows[0] || null;
  }

  async function updateProfile(userId, updates = {}) {
    const allowed = ['email', 'display_name', 'avatar_url', 'preferences'];
    const fields = Object.keys(updates).filter((k) => allowed.includes(k));
    if (fields.length === 0) return getProfile(userId);

    const setClauses = fields.map((f, i) => `${f} = $${i + 2}`).join(', ');
    const values = [userId, ...fields.map((f) => updates[f])];

    const { rows } = await pool.query(
      `UPDATE treekipedia_users SET ${setClauses}, last_seen_at = NOW()
       WHERE silvi_user_id = $1
       RETURNING id, silvi_user_id, email, display_name, avatar_url, preferences, created_at, last_seen_at`,
      values
    );
    return rows[0] || null;
  }

  return {
    ensureUser,
    getProfile,
    updateProfile,
  };
};
