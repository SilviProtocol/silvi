const express = require('express');
const { authenticateUser } = require('../middleware/userAuth');

module.exports = (pool) => {
  const router = express.Router();
  const userController = require('../controllers/user')(pool);

  router.post('/profile', authenticateUser, userController.upsertProfile);
  router.get('/profile', authenticateUser, userController.getProfile);

  return router;
};
