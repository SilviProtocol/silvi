const express = require('express');
const { authenticateUser } = require('../middleware/userAuth');

module.exports = (pool) => {
  const router = express.Router();
  const creditsController = require('../controllers/credits')(pool);

  // Public endpoints
  router.get('/packs', creditsController.getPacks);
  router.post('/estimate-analysis', creditsController.estimateAnalysis);

  // Authenticated endpoints
  router.get('/balance', authenticateUser, creditsController.getBalance);
  router.get('/transactions', authenticateUser, creditsController.getTransactions);

  return router;
};
