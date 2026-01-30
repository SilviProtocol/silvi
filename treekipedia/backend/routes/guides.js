/**
 * Guide Routes
 * Mounts guide controller on /api/guides
 */
module.exports = (pool) => {
  return require('../controllers/guides')(pool);
};
