# Research System & User Framework Integration

**Status**: Planning
**Created**: 2026-01-23
**Priority**: Medium (after frontend insights display)

---

## Overview

This document outlines the planned integration of:
1. **Dual Research System** - Instant (paid) vs Queue (free) research paths
2. **User Framework** - Alignment with Silvi's user models for future merge

These are separate but related features that share a dependency on user authentication.

---

## Current State

### Research System (Implemented)
- Single synchronous path: `POST /species/:taxon_id/research`
- Uses Grok 4.1 Fast API with agentic web search
- Creates atomic insights, syncs to `_ai` columns
- No payment or queueing - research executes immediately
- No user authentication required

### User System (Minimal)
- Wallet-based identity only (no user accounts)
- Sponsorship table tracks wallet → research contributions
- No user profiles, preferences, or permissions
- No session management beyond wallet connection

---

## Target Architecture

### Dual Research Paths

```
User clicks "Research Species"
           │
           ▼
    ┌──────────────┐
    │ Authenticated?│
    └──────┬───────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
  [Guest]     [User]
     │           │
     ▼           ▼
  Queue Only   Choose:
     │         ┌─────┴─────┐
     │         │           │
     │         ▼           ▼
     │    [Instant]    [Queue]
     │    (Pay $X)     (Free)
     │         │           │
     │         ▼           │
     │    Grok API         │
     │    (sync)           │
     │         │           │
     └─────────┼───────────┘
               │
               ▼
         research_queue
               │
               ▼ (async - Claude Code CLI)
         Process batch
               │
               ▼
         Notify user when complete
```

### Payment Model

**Instant Research** (Paid):
- User pays (amount TBD - ~$0.50-1.00?)
- Research executes immediately via Grok API
- Results displayed in real-time
- Receipt/transaction recorded

**Queue Research** (Free):
- Species added to `research_queue` table
- User notified when research completes
- Processed by Claude Code CLI in batches
- Lower priority than paid research

### Queue Processing

**Claude Code CLI Processor** (to be built):
```bash
# Process next item in queue
python scripts/research_queue_processor.py --next

# Process batch of N items
python scripts/research_queue_processor.py --batch 10

# Process specific species
python scripts/research_queue_processor.py --taxon AngMaErSpTc07647-03
```

Processor would:
1. Pull from `research_queue` WHERE status = 'pending' ORDER BY priority DESC
2. Use Claude Code with web search for research
3. Create insights via same flow as Grok
4. Update queue status to 'completed'
5. Trigger notification (email/webhook)

---

## User Framework Requirements

### Analysis Needed: Silvi's User Schema

Before implementing Treekipedia users, we must analyze Silvi's existing user models to ensure compatibility for future merge.

**Questions to Answer**:
1. What tables/models does Silvi use for users?
2. What authentication method (wallet, email, OAuth)?
3. What user attributes are stored?
4. How are permissions/roles handled?
5. What relationships exist (user → projects, user → contributions)?

**Action Item**: Review Silvi codebase for user schema
- Repository: github.com/SilviProtocol/silvi (main branch)
- Look for: User models, auth middleware, database migrations

### Proposed Treekipedia User Fields

Based on current needs (pending Silvi analysis):

```sql
-- Minimal user table (may need adjustment after Silvi review)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identity (flexible for Silvi merge)
  wallet_address VARCHAR(42),          -- Current primary identity
  email VARCHAR(255),                   -- Future: notification delivery
  display_name VARCHAR(100),

  -- Silvi compatibility fields (TBD after analysis)
  silvi_user_id UUID,                   -- Link to Silvi user if exists

  -- Treekipedia-specific
  role VARCHAR(20) DEFAULT 'user',      -- 'user', 'admin', 'researcher'
  research_credits INTEGER DEFAULT 0,   -- Paid research balance
  notification_preferences JSONB,

  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  last_login_at TIMESTAMP
);

-- Index for wallet lookup
CREATE UNIQUE INDEX idx_users_wallet ON users(wallet_address) WHERE wallet_address IS NOT NULL;
```

### Permissions Model

**Roles**:
- `guest` - No account, can only queue research
- `user` - Standard user, can pay for instant or queue
- `admin` - Can instant research without payment, manage queue

**Capabilities by Role**:
| Action | Guest | User | Admin |
|--------|-------|------|-------|
| View species | Yes | Yes | Yes |
| Queue research | Yes | Yes | Yes |
| Instant research | No | Paid | Free |
| View queue status | Own only | Own only | All |
| Manage queue | No | No | Yes |
| Re-research species | No | Paid | Free |

---

## Notification System

### When Queue Research Completes

**Options** (ranked by implementation effort):
1. **Email** - Standard, requires email collection
2. **Webhook** - User provides URL, we POST when done
3. **In-app** - Requires persistent connection (websocket/polling)
4. **Push notification** - Requires mobile app or browser permission

**MVP Recommendation**: Email notification
- User provides email when queueing (optional for logged-in users)
- Send simple email with link to species page
- Include research summary (confidence, fields filled)

---

## Implementation Phases

### Phase 1: Frontend Insights Display (Current)
- Display insights on species detail page
- No user changes required
- Use existing research endpoint

### Phase 2: Queue Infrastructure
- [ ] Create `research_queue` table (already exists from migration)
- [ ] Build queue status endpoint: `GET /research/queue/status`
- [ ] Build user's queue endpoint: `GET /research/queue/mine?wallet=0x...`
- [ ] Add queue option to research flow (frontend button)
- [ ] Build `scripts/research_queue_processor.py`

### Phase 3: User Framework
- [ ] Analyze Silvi user schema (BLOCKER)
- [ ] Design compatible user table
- [ ] Implement auth middleware
- [ ] Add user registration/login flow
- [ ] Migrate existing wallet-based sponsorships to users

### Phase 4: Payment Integration
- [ ] Define pricing model
- [ ] Integrate payment (crypto or fiat?)
- [ ] Add instant research payment flow
- [ ] Track credits/balance

### Phase 5: Notifications
- [ ] Add email field to user/queue
- [ ] Build notification service
- [ ] Send completion emails

---

## Open Decisions

### Pricing
- How much for instant research? ($0.50? $1.00? $3.00?)
- Pay per research or buy credits?
- Discounts for bulk?

### Queue Priority
- FIFO or priority queue?
- Priority for returning users?
- Priority boost for small payment?

### Silvi Merge Strategy
- Shared user table or linked tables?
- Single sign-on across products?
- Unified wallet connection?

### Notification Timing
- Notify immediately on completion?
- Batch notifications (daily digest)?
- Notify on partial completion?

---

## Dependencies

1. **Silvi user schema analysis** - Blocks Phase 3
2. **Payment provider decision** - Blocks Phase 4
3. **Email service setup** - Blocks Phase 5
4. **Frontend insights display** - Should complete first (Phase 1)

---

## Files to Create/Modify

**New Files**:
- `scripts/research_queue_processor.py` - CLI queue processor
- `backend/middleware/auth.js` - User authentication
- `backend/controllers/users.js` - User management
- `database/07_users.sql` - User schema migration

**Modify**:
- `backend/controllers/species.js` - Add queue path to research endpoint
- `backend/routes/index.js` - Add user routes
- `frontend/` - Auth UI, queue UI, payment UI

---

## References

- Current insights architecture: `database/06_insights_architecture.sql`
- Grok research service: `backend/services/grokResearch.js`
- Research endpoint: `backend/controllers/species.js` (POST /:taxon_id/research)
- Djimo's queue approach: github.com/SilviProtocol/silvi/tree/djimotreekipedia
