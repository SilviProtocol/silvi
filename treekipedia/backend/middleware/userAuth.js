/**
 * User Authentication Middleware
 *
 * Validates Django Simple JWT tokens issued by Silvi's Django backend.
 * Django uses HS256 with SECRET_KEY by default.
 *
 * Usage:
 *   const { authenticateUser, optionalAuth } = require('./middleware/userAuth');
 *
 *   // Require auth:
 *   router.get('/protected', authenticateUser, handler);
 *
 *   // Optional auth (req.user is null if no token):
 *   router.get('/public', optionalAuth, handler);
 */

const jwt = require('jsonwebtoken');

const DJANGO_SECRET = process.env.DJANGO_SECRET_KEY;

/**
 * Required authentication — returns 401 if no valid token
 * Sets req.user = { id, token_type }
 */
const authenticateUser = (req, res, next) => {
  if (!DJANGO_SECRET) {
    console.error('DJANGO_SECRET_KEY not configured');
    return res.status(500).json({ error: 'Auth not configured' });
  }

  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Authorization header required' });
  }

  const token = authHeader.split(' ')[1];

  try {
    const decoded = jwt.verify(token, DJANGO_SECRET, { algorithms: ['HS256'] });
    req.user = {
      id: decoded.user_id,
      token_type: decoded.token_type,
    };
    next();
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({ error: 'Token expired' });
    }
    return res.status(401).json({ error: 'Invalid token' });
  }
};

/**
 * Optional authentication — sets req.user if valid token present, null otherwise
 * Never blocks the request
 */
const optionalAuth = (req, res, next) => {
  req.user = null;

  if (!DJANGO_SECRET) {
    return next();
  }

  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return next();
  }

  const token = authHeader.split(' ')[1];

  try {
    const decoded = jwt.verify(token, DJANGO_SECRET, { algorithms: ['HS256'] });
    req.user = {
      id: decoded.user_id,
      token_type: decoded.token_type,
    };
  } catch {
    // Invalid token — treat as unauthenticated, don't block
  }

  next();
};

module.exports = { authenticateUser, optionalAuth };
