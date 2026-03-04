/**
 * Credit Service
 * Core credit system logic: balance checks, deductions, grants, cost calculations
 */

module.exports = (pool) => {

  /**
   * Get user's credit balance and lifetime stats
   * Auto-grants signup bonus if user has no balance row
   */
  async function getBalance(userId) {
    const { rows } = await pool.query(
      'SELECT balance, lifetime_purchased, lifetime_spent FROM credit_balances WHERE user_id = $1',
      [userId]
    );

    if (rows.length === 0) {
      // New user — grant signup bonus
      await grantSignupBonus(userId);
      // Re-query actual balance (handles concurrent requests / deduplicated bonus)
      const { rows: updated } = await pool.query(
        'SELECT balance, lifetime_purchased, lifetime_spent FROM credit_balances WHERE user_id = $1',
        [userId]
      );
      return updated[0] || { balance: 50, lifetime_purchased: 50, lifetime_spent: 0 };
    }

    return rows[0];
  }

  /**
   * Deduct credits atomically with balance check
   * Uses SELECT FOR UPDATE to prevent race conditions
   */
  async function deductCredits(userId, amount, type, referenceId, metadata = {}, idempotencyKey = null) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      // Ensure balance row exists (auto-grant signup bonus if needed)
      const { rows } = await client.query(
        'SELECT balance FROM credit_balances WHERE user_id = $1 FOR UPDATE',
        [userId]
      );

      let balance;
      if (rows.length === 0) {
        // Grant signup bonus within this transaction
        await client.query(
          `INSERT INTO credit_transactions (user_id, amount, type, reference_id, description, balance_after, metadata, idempotency_key)
           VALUES ($1, 50, 'signup_bonus', NULL, 'Welcome bonus: 50 free credits', 50, '{}', $2)`,
          [userId, `signup_bonus_${userId}`]
        );
        balance = 50;
      } else {
        balance = rows[0].balance;
      }

      if (balance < amount) {
        await client.query('ROLLBACK');
        return { success: false, error: 'insufficient_credits', balance, required: amount };
      }

      const description = `${type}: ${amount} credits`;
      const balanceAfter = balance - amount;

      const txn = await client.query(
        `INSERT INTO credit_transactions (user_id, amount, type, reference_id, description, balance_after, metadata, idempotency_key)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id`,
        [userId, -amount, type, referenceId, description, balanceAfter, JSON.stringify(metadata), idempotencyKey]
      );

      await client.query('COMMIT');
      return { success: true, balance_after: balanceAfter, transaction_id: txn.rows[0].id };
    } catch (e) {
      await client.query('ROLLBACK');
      // Idempotency key conflict means this was already processed
      if (e.code === '23505' && e.constraint && idempotencyKey) {
        const existing = await pool.query(
          'SELECT balance_after FROM credit_transactions WHERE idempotency_key = $1',
          [idempotencyKey]
        );
        if (existing.rows.length > 0) {
          return { success: true, balance_after: existing.rows[0].balance_after, deduplicated: true };
        }
      }
      throw e;
    } finally {
      client.release();
    }
  }

  /**
   * Grant credits to a user (purchases, bonuses, refunds, admin grants)
   */
  async function grantCredits(userId, amount, type, referenceId, description, idempotencyKey = null) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      // Get current balance (or 0 if new user)
      const { rows } = await client.query(
        'SELECT balance FROM credit_balances WHERE user_id = $1 FOR UPDATE',
        [userId]
      );
      const balance = rows.length > 0 ? rows[0].balance : 0;
      const balanceAfter = balance + amount;

      await client.query(
        `INSERT INTO credit_transactions (user_id, amount, type, reference_id, description, balance_after, metadata, idempotency_key)
         VALUES ($1, $2, $3, $4, $5, $6, '{}', $7)`,
        [userId, amount, type, referenceId, description, balanceAfter, idempotencyKey]
      );

      await client.query('COMMIT');
      return { success: true, balance_after: balanceAfter };
    } catch (e) {
      await client.query('ROLLBACK');
      // Idempotency key conflict — already granted
      if (e.code === '23505' && idempotencyKey) {
        return { success: true, deduplicated: true };
      }
      throw e;
    } finally {
      client.release();
    }
  }

  /**
   * Grant 50 credit signup bonus (idempotent)
   */
  async function grantSignupBonus(userId) {
    return grantCredits(
      userId, 50, 'signup_bonus', null,
      'Welcome bonus: 50 free credits',
      `signup_bonus_${userId}`
    );
  }

  /**
   * Calculate site analysis cost based on area in hectares
   * Tiered pricing:
   *   1-10 ha:        10 credits (minimum)
   *   11-100 ha:      10 + (ha - 10) × 0.5
   *   101-1,000 ha:   55 + (ha - 100) × 0.2
   *   1,001-10,000:   235 + (ha - 1000) × 0.05
   *   10,001+ ha:     685 + (ha - 10000) × 0.02
   */
  function calculateSiteAnalysisCost(hectares) {
    if (hectares <= 10) return 10;
    if (hectares <= 100) return Math.ceil(10 + (hectares - 10) * 0.5);
    if (hectares <= 1000) return Math.ceil(55 + (hectares - 100) * 0.2);
    if (hectares <= 10000) return Math.ceil(235 + (hectares - 1000) * 0.05);
    return Math.ceil(685 + (hectares - 10000) * 0.02);
  }

  /**
   * Get paginated transaction history for a user
   */
  async function getTransactionHistory(userId, limit = 50, offset = 0) {
    const { rows } = await pool.query(
      `SELECT id, amount, type, reference_id, description, balance_after, metadata, created_at
       FROM credit_transactions
       WHERE user_id = $1
       ORDER BY created_at DESC
       LIMIT $2 OFFSET $3`,
      [userId, limit, offset]
    );

    const countResult = await pool.query(
      'SELECT COUNT(*) as total FROM credit_transactions WHERE user_id = $1',
      [userId]
    );

    return {
      transactions: rows,
      total: parseInt(countResult.rows[0].total),
      limit,
      offset
    };
  }

  return {
    getBalance,
    deductCredits,
    grantCredits,
    grantSignupBonus,
    calculateSiteAnalysisCost,
    getTransactionHistory
  };
};
