const express = require('express');
const { authenticateUser } = require('../middleware/userAuth');

module.exports = (pool) => {
  const router = express.Router();
  const paymentsController = require('../controllers/payments')(pool);

  router.post('/create-invoice', authenticateUser, paymentsController.createInvoice);
  router.post('/webhooks/nowpayments', paymentsController.handleWebhook);

  return router;
};
