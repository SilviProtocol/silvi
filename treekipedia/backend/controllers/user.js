/**
 * User Controller
 * Endpoints for the treekipedia_users profile. POST is the canonical
 * registration entry point — the frontend calls it once after login
 * (both OTP and Google SSO paths) to sync email and trigger the signup bonus.
 */

module.exports = (pool) => {
  const userService = require('../services/userService')(pool);
  const creditService = require('../services/creditService')(pool);

  /**
   * POST /api/user/profile
   * Body: { email?, display_name?, avatar_url? }
   * Upserts the treekipedia_users row. Grants signup bonus on first call.
   * Returns { profile, credits }.
   */
  async function upsertProfile(req, res) {
    try {
      const { email, display_name, avatar_url } = req.body || {};

      const profile = await userService.ensureUser(req.user.id, {
        email: email || null,
        displayName: display_name || null,
        avatarUrl: avatar_url || null,
      });

      const credits = await creditService.getBalance(req.user.id);

      res.json({ success: true, profile, credits, is_new: profile.is_new });
    } catch (error) {
      console.error('Error upserting user profile:', error);
      res.status(500).json({ error: 'Failed to upsert user profile' });
    }
  }

  /**
   * GET /api/user/profile
   * Returns { profile, credits } for the authenticated user.
   * Returns null profile if user has never registered via POST /profile
   * (edge case — shouldn't happen in normal flow).
   */
  async function getProfile(req, res) {
    try {
      const profile = await userService.getProfile(req.user.id);
      const credits = await creditService.getBalance(req.user.id);
      res.json({ success: true, profile, credits });
    } catch (error) {
      console.error('Error getting user profile:', error);
      res.status(500).json({ error: 'Failed to get user profile' });
    }
  }

  return {
    upsertProfile,
    getProfile,
  };
};
