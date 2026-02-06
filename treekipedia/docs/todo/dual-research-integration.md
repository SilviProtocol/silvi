# Dual Research Integration Plan

**Status**: Planning
**Added**: January 2026
**Linked from**: TODO.md

---

## Overview

Two research paths for species data enrichment, differentiated by speed and cost:

| Path | Trigger | Speed | Cost | Engine |
|------|---------|-------|------|--------|
| **Instant Research** | "Research Instantly" button + crypto payment | ~10-30s | $1 (crypto via NOWPayments) | Grok 4.1 Fast w/ agentic web search |
| **Queue Research** | "Add to Queue" button | Async (batch) | Free | Claude CLI batch processing |

Both paths write to the same `insights` table and sync to `species._ai` columns.

---

## Architecture

### Instant Research Flow

```
User clicks "Research Instantly"
  → Frontend calls POST /api/payments/create-invoice
    → Backend creates NOWPayments invoice (taxon_id as order_id)
    → Returns invoice URL
  → User pays in any crypto ($1)
  → NOWPayments POSTs webhook to /api/webhooks/nowpayments
    → Backend verifies HMAC-SHA512 signature
    → Backend records payment in research_payments table
    → Backend triggers Grok instant research (grokResearch.js)
    → Research creates insights + syncs to species table
  → Frontend polls GET /research/:taxon_id for status
  → Page updates with new data
```

### Queue Research Flow (existing)

```
User clicks "Add to Queue"
  → Frontend calls POST /research/fund-research
  → Backend adds to research_queue table (status: pending)
  → CLI batch processor picks up and processes later
  → Results written same way (insights + species sync)
```

---

## Backend Implementation

### New Files

- `backend/controllers/payments.js` — NOWPayments invoice creation + webhook handler
- `backend/routes/payments.js` — Route registration

### New Database Table

```sql
CREATE TABLE research_payments (
  id SERIAL PRIMARY KEY,
  taxon_id VARCHAR(50) NOT NULL,
  payment_id VARCHAR(100),          -- NOWPayments payment ID
  invoice_id VARCHAR(100),          -- NOWPayments invoice ID
  amount DECIMAL(10,2) DEFAULT 1.00,
  currency VARCHAR(10) DEFAULT 'usd',
  pay_currency VARCHAR(10),         -- Crypto used (btc, eth, etc.)
  status VARCHAR(20) DEFAULT 'pending', -- pending, confirming, confirmed, finished, failed
  research_triggered BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_research_payments_taxon ON research_payments(taxon_id);
CREATE INDEX idx_research_payments_invoice ON research_payments(invoice_id);
```

### Webhook Handler (payments.js)

```js
// POST /api/webhooks/nowpayments
// Verifies x-nowpayments-sig header using HMAC-SHA512
// On status "finished" or "confirmed":
//   1. Update research_payments row
//   2. Trigger grokResearch(taxon_id)
//   3. Set research_triggered = true

const crypto = require('crypto');

function verifySignature(body, signature, secret) {
  const sorted = JSON.stringify(body, Object.keys(body).sort());
  const hmac = crypto.createHmac('sha512', secret).update(sorted).digest('hex');
  return hmac === signature;
}
```

### Environment Variables

```env
NOWPAYMENTS_API_KEY=your_api_key
NOWPAYMENTS_IPN_SECRET=your_ipn_secret_key
```

### Invoice Creation Endpoint

```js
// POST /api/payments/create-invoice
// Body: { taxon_id, species_name }
// Calls NOWPayments POST /v1/invoice:
//   price_amount: 1
//   price_currency: "usd"
//   ipn_callback_url: "https://treekipedia-api.silvi.earth/api/webhooks/nowpayments"
//   order_id: taxon_id
//   order_description: "Instant AI research for {species_name}"
// Returns: { invoice_url, invoice_id }
```

---

## Frontend Implementation

### Species Page Changes

Replace single research button with dual-button UI:

```
┌─────────────────────────────────────────────────┐
│  Species: Quercus alba                          │
│                                                 │
│  Research Status: Not yet researched             │
│  ── OR ──                                       │
│  Last researched: Jan 15, 2026 (v2)             │
│                                                 │
│  ┌─────────────────┐  ┌──────────────────────┐  │
│  │ Research Instantly│  │  Add to Queue (Free) │  │
│  │     ($1 crypto)  │  │                      │  │
│  └─────────────────┘  └──────────────────────┘  │
│                                                 │
│  If already researched, buttons show:           │
│  "Re-research Instantly" / "Re-add to Queue"    │
│  with last research date displayed              │
└─────────────────────────────────────────────────┘
```

### Frontend Files to Modify

- `hooks/useResearchProcess.ts` — Add instant research flow alongside queue flow
- `page.tsx` — Dual button UI
- `lib/api.ts` — Add `createResearchInvoice()` API call

### Payment UX Flow

1. User clicks "Research Instantly"
2. Frontend calls backend to create invoice
3. Backend returns NOWPayments invoice URL
4. Frontend opens invoice URL (new tab or modal/iframe)
5. User pays in crypto of their choice
6. NOWPayments sends webhook → backend triggers research
7. Frontend polls research status until complete
8. Page refreshes with new data

---

## NOWPayments Integration Details

**Service**: [NOWPayments](https://nowpayments.io)
**JS SDK**: `@nowpaymentsio/nowpayments-api-js`
**Fee**: 0.5% per transaction
**Supported**: 300+ cryptocurrencies

### Setup Steps

1. Sign up at nowpayments.io with dev@silvi.earth
2. Set payout wallet address
3. Generate API key from dashboard
4. Generate IPN Secret key from Payment Settings
5. Add keys to `.env`
6. Test with sandbox before production

### Key API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/v1/status` | Check API availability |
| POST | `/v1/invoice` | Create payment invoice |
| GET | `/v1/payment/:id` | Check payment status |
| POST | (your webhook) | Receive IPN callbacks |

### Webhook Payload (IPN)

NOWPayments POSTs payment status changes to your `ipn_callback_url`. The `x-nowpayments-sig` header contains HMAC-SHA512 signature. Verify by:
1. Sort request body keys alphabetically
2. `JSON.stringify` the sorted body
3. HMAC-SHA512 with IPN secret
4. Compare to header signature

---

## Future Enhancements

### User Roles (post-MVP)
- Admin users: bypass payment, click "Research Instantly" for free
- Requires user accounts + authentication system
- Role check in payment controller: if admin, skip NOWPayments, trigger directly

### Research Credits
- Bulk purchase credits (e.g., 10 researches for $8)
- Credit balance tracked per wallet address or user account

### Sponsorship Display
- Show "Researched by [wallet address]" on species page
- On-chain attestation of research sponsorship via EAS

---

## Dependencies

- NOWPayments account + API keys
- Grok API key (already configured in `.env`)
- `@nowpaymentsio/nowpayments-api-js` npm package
- Existing `grokResearch.js` service (already working)
- Existing `research_queue` table (already exists)
