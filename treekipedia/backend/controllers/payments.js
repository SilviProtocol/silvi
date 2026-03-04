/**
 * Payments Controller
 * NOWPayments invoice creation and webhook handling for credit purchases
 */

const crypto = require('crypto');

module.exports = (pool) => {
  const creditService = require('../services/creditService')(pool);

  const NOWPAYMENTS_API_KEY = process.env.NOWPAYMENTS_API_KEY;
  const NOWPAYMENTS_IPN_SECRET = process.env.NOWPAYMENTS_IPN_SECRET;
  const NOWPAYMENTS_SANDBOX = process.env.NOWPAYMENTS_SANDBOX === 'true';
  const NOWPAYMENTS_BASE = NOWPAYMENTS_SANDBOX
    ? 'https://api-sandbox.nowpayments.io/v1'
    : 'https://api.nowpayments.io/v1';

  /**
   * POST /api/payments/create-invoice
   * Creates a NOWPayments invoice for a credit pack purchase
   * Requires authentication
   */
  async function createInvoice(req, res) {
    try {
      const { pack_id } = req.body;
      const userId = req.user.id;

      if (!pack_id) {
        return res.status(400).json({ error: 'pack_id is required' });
      }

      // Validate pack exists and is active
      const packResult = await pool.query(
        'SELECT id, name, credits, price_usd FROM credit_packs WHERE id = $1 AND active = true',
        [pack_id]
      );

      if (packResult.rows.length === 0) {
        return res.status(404).json({ error: 'Credit pack not found' });
      }

      const pack = packResult.rows[0];

      // Create local invoice record
      const invoiceResult = await pool.query(
        `INSERT INTO credit_invoices (user_id, pack_id, amount_usd, credits, status)
         VALUES ($1, $2, $3, $4, 'pending') RETURNING id`,
        [userId, pack.id, pack.price_usd, pack.credits]
      );

      const invoiceId = invoiceResult.rows[0].id;
      const orderId = `credit_${userId}_${pack.id}_${invoiceId}`;

      // Create NOWPayments invoice
      const response = await fetch(`${NOWPAYMENTS_BASE}/invoice`, {
        method: 'POST',
        headers: {
          'x-api-key': NOWPAYMENTS_API_KEY,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          price_amount: parseFloat(pack.price_usd),
          price_currency: 'usd',
          order_id: orderId,
          order_description: `Treekipedia ${pack.name} Pack — ${pack.credits} credits`,
          ipn_callback_url: 'https://treekipedia-api.silvi.earth/api/payments/webhooks/nowpayments',
          success_url: 'https://treekipedia.silvi.earth/credits?purchased=true',
          cancel_url: 'https://treekipedia.silvi.earth/credits?cancelled=true'
        })
      });

      if (!response.ok) {
        const errorBody = await response.text();
        console.error('NOWPayments invoice creation failed:', response.status, errorBody);
        // Clean up local invoice
        await pool.query('UPDATE credit_invoices SET status = $1 WHERE id = $2', ['failed', invoiceId]);
        return res.status(502).json({ error: 'Failed to create payment invoice' });
      }

      const invoiceData = await response.json();

      // Update local invoice with NOWPayments ID
      await pool.query(
        'UPDATE credit_invoices SET nowpayments_invoice_id = $1 WHERE id = $2',
        [invoiceData.id, invoiceId]
      );

      res.json({
        success: true,
        invoice_url: invoiceData.invoice_url,
        invoice_id: invoiceId,
        pack: { id: pack.id, name: pack.name, credits: pack.credits, price_usd: pack.price_usd }
      });
    } catch (error) {
      console.error('Error creating invoice:', error);
      res.status(500).json({ error: 'Failed to create invoice' });
    }
  }

  /**
   * POST /api/payments/webhooks/nowpayments
   * IPN callback from NOWPayments — verifies HMAC signature and fulfills credit purchase
   * No auth — HMAC verified
   */
  async function handleWebhook(req, res) {
    try {
      // Verify HMAC-SHA512 signature (NOWPayments spec: sorted keys, compact JSON)
      const receivedSig = req.headers['x-nowpayments-sig'];
      if (!receivedSig || !NOWPAYMENTS_IPN_SECRET) {
        return res.status(400).json({ error: 'Missing signature or IPN secret not configured' });
      }

      const sortedBody = sortObject(req.body);
      const hmac = crypto.createHmac('sha512', NOWPAYMENTS_IPN_SECRET);
      hmac.update(JSON.stringify(sortedBody));
      const expectedSig = hmac.digest('hex');

      const sigBuffer = Buffer.from(receivedSig, 'hex');
      const expectedBuffer = Buffer.from(expectedSig, 'hex');
      if (sigBuffer.length !== expectedBuffer.length || !crypto.timingSafeEqual(sigBuffer, expectedBuffer)) {
        console.error('NOWPayments webhook: signature mismatch');
        return res.status(403).json({ error: 'Invalid signature' });
      }

      const { payment_status, order_id, payment_id, pay_currency } = req.body;

      // Only process finished payments
      if (payment_status !== 'finished') {
        // Update status on the invoice for tracking
        if (order_id) {
          const parts = order_id.split('_');
          if (parts.length >= 4) {
            const invoiceId = parts[3];
            await pool.query(
              'UPDATE credit_invoices SET status = $1, pay_currency = $2, nowpayments_payment_id = $3 WHERE id = $4 AND fulfilled = false',
              [payment_status, pay_currency, String(payment_id), invoiceId]
            );
          }
        }
        return res.json({ success: true, message: `Status ${payment_status} recorded` });
      }

      // Parse order_id: credit_{userId}_{packId}_{invoiceId}
      if (!order_id || !order_id.startsWith('credit_')) {
        return res.status(400).json({ error: 'Invalid order_id format' });
      }

      const parts = order_id.split('_');
      if (parts.length < 4) {
        return res.status(400).json({ error: 'Invalid order_id format' });
      }

      const userId = parseInt(parts[1]);
      const packId = parts[2];
      const invoiceId = parseInt(parts[3]);

      // Look up invoice and verify not already fulfilled
      const invoiceResult = await pool.query(
        'SELECT id, credits, fulfilled FROM credit_invoices WHERE id = $1 AND user_id = $2',
        [invoiceId, userId]
      );

      if (invoiceResult.rows.length === 0) {
        return res.status(404).json({ error: 'Invoice not found' });
      }

      const invoice = invoiceResult.rows[0];
      if (invoice.fulfilled) {
        return res.json({ success: true, message: 'Already fulfilled' });
      }

      // Grant credits (idempotent via key)
      const idempotencyKey = `nowpay_${payment_id}`;
      await creditService.grantCredits(
        userId,
        invoice.credits,
        'purchase',
        String(invoiceId),
        `Purchased ${invoice.credits} credits (${packId} pack)`,
        idempotencyKey
      );

      // Mark invoice as fulfilled
      await pool.query(
        `UPDATE credit_invoices
         SET fulfilled = true, fulfilled_at = NOW(), status = 'finished',
             pay_currency = $1, nowpayments_payment_id = $2
         WHERE id = $3`,
        [pay_currency, String(payment_id), invoiceId]
      );

      console.log(`Credits fulfilled: user=${userId}, credits=${invoice.credits}, invoice=${invoiceId}`);
      res.json({ success: true, message: 'Credits granted' });
    } catch (error) {
      console.error('Error handling NOWPayments webhook:', error);
      res.status(500).json({ error: 'Webhook processing failed' });
    }
  }

  /**
   * Sort object keys recursively for HMAC verification (NOWPayments spec)
   */
  function sortObject(obj) {
    if (typeof obj !== 'object' || obj === null) return obj;
    if (Array.isArray(obj)) return obj.map(sortObject);
    return Object.keys(obj).sort().reduce((sorted, key) => {
      sorted[key] = sortObject(obj[key]);
      return sorted;
    }, {});
  }

  return {
    createInvoice,
    handleWebhook
  };
};
