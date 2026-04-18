/**
 * Credit Service
 * Core credit system logic: balance checks, deductions, grants, cost calculations
 *
 * Pricing and free/paid toggles live in `backend/config/pricing.js`.
 * Controllers should use `chargeForProduct` rather than calling `deductCredits` directly.
 */

const { SIGNUP_BONUS, PRODUCTS, calculateSiteAnalysisCost } = require('../config/pricing');

module.exports = (pool) => {
  // Lazy-required to avoid any startup-order concerns; safe because userService
  // doesn't require creditService back (no circular dependency).
  const userService = require('./userService')(pool);

  /**
   * Get user's credit balance and lifetime stats.
   * Returns zeros if user has no balance row yet — does NOT auto-register.
   * Registration happens at POST /api/user/profile or via the safety net in deductCredits.
   */
  async function getBalance(userId) {
    const { rows } = await pool.query(
      'SELECT balance, lifetime_purchased, lifetime_spent FROM credit_balances WHERE user_id = $1',
      [userId]
    );
    return rows[0] || { balance: 0, lifetime_purchased: 0, lifetime_spent: 0 };
  }

  /**
   * Deduct credits atomically with balance check.
   * Uses SELECT FOR UPDATE to prevent race conditions.
   * Safety net: if the user has no balance row, assume they bypassed POST /profile
   * and call userService.ensureUser within this transaction to create the row
   * and grant the signup bonus atomically.
   */
  async function deductCredits(userId, amount, type, referenceId, metadata = {}, idempotencyKey = null) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      let { rows } = await client.query(
        'SELECT balance FROM credit_balances WHERE user_id = $1 FOR UPDATE',
        [userId]
      );

      if (rows.length === 0) {
        // Safety net — user hit a gated endpoint without registering via POST /profile.
        // ensureUser upserts the treekipedia_users row and grants the signup bonus
        // in this transaction; then re-SELECT the balance.
        await userService.ensureUser(userId, {}, client);
        ({ rows } = await client.query(
          'SELECT balance FROM credit_balances WHERE user_id = $1 FOR UPDATE',
          [userId]
        ));
      }

      const balance = rows[0].balance;

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
   * Grant credits to a user (purchases, bonuses, refunds, admin grants).
   */
  async function grantCredits(userId, amount, type, referenceId, description, idempotencyKey = null) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

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
      if (e.code === '23505' && idempotencyKey) {
        return { success: true, deduplicated: true };
      }
      throw e;
    } finally {
      client.release();
    }
  }

  /**
   * Grant signup bonus (idempotent via key `signup_bonus_${userId}`).
   */
  async function grantSignupBonus(userId) {
    return grantCredits(
      userId,
      SIGNUP_BONUS,
      'signup_bonus',
      null,
      `Welcome bonus: ${SIGNUP_BONUS} free credits`,
      `signup_bonus_${userId}`
    );
  }

  /**
   * Charge a user for a named product per `config/pricing.js`.
   * Returns { ok: true, ... } on success or free, or { ok: false, status, body } on failure
   * (response body is shaped for the controller to return directly).
   */
  async function chargeForProduct(userId, productKey, context = {}, referenceId = null) {
    const product = PRODUCTS[productKey];
    if (!product) throw new Error(`Unknown product: ${productKey}`);

    if (!product.enabled) return { ok: true, free: true, cost: 0 };

    const cost = typeof product.cost === 'function' ? product.cost(context) : product.cost;
    if (!cost || cost <= 0) return { ok: true, free: true, cost: 0 };

    const refSegment = referenceId !== null && referenceId !== undefined ? `_${referenceId}` : '';
    const idempotencyKey = `${productKey}_${userId}${refSegment}_${Date.now()}`;

    const deduction = await deductCredits(userId, cost, productKey, referenceId, context, idempotencyKey);

    if (!deduction.success) {
      return {
        ok: false,
        status: 402,
        body: {
          error: 'Insufficient credits',
          required: deduction.required,
          balance: deduction.balance,
          cost_credits: cost,
        },
      };
    }

    return { ok: true, cost, balance_after: deduction.balance_after, transaction_id: deduction.transaction_id };
  }

  /**
   * Get paginated transaction history for a user.
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
    chargeForProduct,
    calculateSiteAnalysisCost,
    getTransactionHistory,
  };
};
