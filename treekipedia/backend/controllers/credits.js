/**
 * Credits Controller
 * Endpoints for credit balance, transactions, packs, and cost estimation
 */

module.exports = (pool) => {
  const creditService = require('../services/creditService')(pool);

  /**
   * GET /api/credits/balance
   * Returns user's credit balance and lifetime stats
   * Requires authentication
   */
  async function getBalance(req, res) {
    try {
      const balance = await creditService.getBalance(req.user.id);
      res.json({ success: true, ...balance });
    } catch (error) {
      console.error('Error getting credit balance:', error);
      res.status(500).json({ error: 'Failed to get credit balance' });
    }
  }

  /**
   * GET /api/credits/transactions?limit=50&offset=0
   * Returns paginated transaction history
   * Requires authentication
   */
  async function getTransactions(req, res) {
    try {
      const limit = Math.min(parseInt(req.query.limit) || 50, 100);
      const offset = parseInt(req.query.offset) || 0;
      const result = await creditService.getTransactionHistory(req.user.id, limit, offset);
      res.json({ success: true, ...result });
    } catch (error) {
      console.error('Error getting transactions:', error);
      res.status(500).json({ error: 'Failed to get transaction history' });
    }
  }

  /**
   * GET /api/credits/packs
   * Returns available credit packs and prices (no auth required)
   */
  async function getPacks(req, res) {
    try {
      const { rows } = await pool.query(
        'SELECT id, name, credits, price_usd FROM credit_packs WHERE active = true ORDER BY credits ASC'
      );
      res.json({ success: true, packs: rows });
    } catch (error) {
      console.error('Error getting credit packs:', error);
      res.status(500).json({ error: 'Failed to get credit packs' });
    }
  }

  /**
   * POST /api/credits/estimate-analysis
   * Body: { geometry: GeoJSON Polygon }
   * Returns estimated cost in credits for a site analysis (no auth required)
   */
  async function estimateAnalysis(req, res) {
    try {
      const { geometry } = req.body;
      if (!geometry || geometry.type !== 'Polygon') {
        return res.status(400).json({ error: 'Invalid geometry. Must be a GeoJSON Polygon' });
      }

      const geoJsonString = JSON.stringify(geometry);
      const areaResult = await pool.query(
        'SELECT ST_Area(ST_GeomFromGeoJSON($1)::geography) / 10000 AS hectares',
        [geoJsonString]
      );

      const hectares = parseFloat(areaResult.rows[0].hectares);
      const cost = creditService.calculateSiteAnalysisCost(hectares);

      res.json({
        success: true,
        area_hectares: Math.round(hectares * 100) / 100,
        cost_credits: cost
      });
    } catch (error) {
      console.error('Error estimating analysis cost:', error);
      res.status(500).json({ error: 'Failed to estimate analysis cost' });
    }
  }

  return {
    getBalance,
    getTransactions,
    getPacks,
    estimateAnalysis
  };
};
