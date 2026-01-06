/**
 * API Key Authentication Middleware
 *
 * This middleware validates API keys for public endpoints.
 * API keys should be provided in the 'x-api-key' header.
 *
 * Valid keys are stored in the API_KEYS environment variable (comma-separated)
 * Example: API_KEYS=treeki_live_abc123,treeki_live_xyz789
 */

/**
 * Middleware to validate API key from request headers
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 */
const validateApiKey = (req, res, next) => {
  const apiKey = req.headers['x-api-key'];

  // Check if API key is provided
  if (!apiKey) {
    return res.status(401).json({
      error: 'API key required',
      message: 'Please provide an API key in the x-api-key header. Contact us at https://treekipedia.silvi.earth for access.',
      documentation: 'https://treekipedia.silvi.earth/docs/api'
    });
  }

  // Get valid API keys from environment variable
  const validKeys = process.env.API_KEYS?.split(',').map(key => key.trim()) || [];

  if (validKeys.length === 0) {
    console.error('WARNING: No API keys configured in environment variables');
    return res.status(500).json({
      error: 'API keys not configured on server'
    });
  }

  // Validate the provided key
  if (!validKeys.includes(apiKey)) {
    console.log(`Invalid API key attempt: ${apiKey.substring(0, 12)}...`);
    return res.status(403).json({
      error: 'Invalid API key',
      message: 'The provided API key is not valid or has been revoked.'
    });
  }

  // Log successful API key usage (for monitoring)
  console.log(`API call authorized with key: ${apiKey.substring(0, 12)}... for ${req.method} ${req.path}`);

  // Attach key info to request for potential usage tracking
  req.apiKey = apiKey;
  req.apiKeyPrefix = apiKey.substring(0, 12);

  next();
};

/**
 * Optional: Middleware for rate limiting per API key
 * This is a simple in-memory implementation
 * For production, consider using Redis for distributed rate limiting
 */
const rateLimitByApiKey = (() => {
  const requests = new Map(); // Map<apiKey, Array<timestamp>>
  const WINDOW_MS = 60 * 1000; // 1 minute window
  const MAX_REQUESTS = 60; // 60 requests per minute per key

  return (req, res, next) => {
    const apiKey = req.apiKey;
    const now = Date.now();

    // Get request history for this key
    if (!requests.has(apiKey)) {
      requests.set(apiKey, []);
    }

    const keyRequests = requests.get(apiKey);

    // Remove requests outside the time window
    const recentRequests = keyRequests.filter(timestamp => now - timestamp < WINDOW_MS);

    // Check if limit exceeded
    if (recentRequests.length >= MAX_REQUESTS) {
      return res.status(429).json({
        error: 'Rate limit exceeded',
        message: `Maximum ${MAX_REQUESTS} requests per minute per API key`,
        retryAfter: Math.ceil((recentRequests[0] + WINDOW_MS - now) / 1000)
      });
    }

    // Add current request
    recentRequests.push(now);
    requests.set(apiKey, recentRequests);

    // Clean up old entries periodically
    if (Math.random() < 0.01) { // 1% chance
      for (const [key, timestamps] of requests.entries()) {
        const filtered = timestamps.filter(ts => now - ts < WINDOW_MS);
        if (filtered.length === 0) {
          requests.delete(key);
        } else {
          requests.set(key, filtered);
        }
      }
    }

    // Add rate limit headers
    res.setHeader('X-RateLimit-Limit', MAX_REQUESTS);
    res.setHeader('X-RateLimit-Remaining', MAX_REQUESTS - recentRequests.length);
    res.setHeader('X-RateLimit-Reset', new Date(recentRequests[0] + WINDOW_MS).toISOString());

    next();
  };
})();

module.exports = {
  validateApiKey,
  rateLimitByApiKey
};
