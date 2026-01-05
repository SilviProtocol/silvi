/**
 * Admin Authentication Middleware
 * Protects admin routes with session-based authentication
 */

const requireAdminAuth = (req, res, next) => {
  // Check if user is authenticated via session
  if (req.session && req.session.isAdminAuthenticated === true) {
    // User is authenticated, proceed to the route
    return next();
  }

  // User is not authenticated
  return res.status(401).json({
    error: 'Unauthorized',
    message: 'Admin authentication required'
  });
};

module.exports = { requireAdminAuth };
