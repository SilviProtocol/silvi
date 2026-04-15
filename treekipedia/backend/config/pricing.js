/**
 * Credit Pricing Configuration
 *
 * Single source of truth for:
 *   - Signup bonus amount
 *   - Per-product credit costs
 *   - Free/paid toggles (enabled: false -> product is free for everyone)
 *
 * To make a product free: set `enabled: false`.
 * To change a cost: edit the `cost` field (number or function).
 * Gate sites must call `creditService.chargeForProduct(userId, productKey, context, referenceId)`
 * rather than hardcoding costs in controllers.
 */

const SIGNUP_BONUS = 100;

/**
 * Tiered pricing for polygon-area operations.
 *   1-10 ha:       10 credits (minimum)
 *   11-100 ha:     10 + (ha - 10) × 0.5
 *   101-1,000 ha:  55 + (ha - 100) × 0.2
 *   1,001-10,000:  235 + (ha - 1000) × 0.05
 *   10,001+ ha:    685 + (ha - 10000) × 0.02
 */
function calculateSiteAnalysisCost(hectares) {
  if (hectares <= 10)    return 10;
  if (hectares <= 100)   return Math.ceil(10  + (hectares - 10)    * 0.5);
  if (hectares <= 1000)  return Math.ceil(55  + (hectares - 100)   * 0.2);
  if (hectares <= 10000) return Math.ceil(235 + (hectares - 1000)  * 0.05);
  return                        Math.ceil(685 + (hectares - 10000) * 0.02);
}

/**
 * Product gate config.
 *   enabled:      false -> skip deduction entirely (free for everyone)
 *   cost: number      -> flat cost
 *   cost: function    -> dynamic, receives { hectares?, ...ctx } and returns credits
 */
const PRODUCTS = {
  species_research: {
    enabled: true,
    cost: 25,
  },
  guide_synthesis: {
    enabled: true,
    cost: 200,
  },
  leaf_score: {
    enabled: true,
    cost: (ctx) => (ctx && ctx.hectares ? calculateSiteAnalysisCost(ctx.hectares) : 10),
  },
  polygon_prediction: {
    enabled: true,
    cost: 25,
  },
};

module.exports = {
  SIGNUP_BONUS,
  PRODUCTS,
  calculateSiteAnalysisCost,
};
