-- Credit System Schema
-- Adds credit packs, balances, transactions, and invoice tracking for NOWPayments

-- Credit packs (admin-configurable)
CREATE TABLE credit_packs (
  id VARCHAR(20) PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  credits INTEGER NOT NULL,
  price_usd DECIMAL(10,2) NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO credit_packs VALUES
  ('starter', 'Starter', 100, 10.00, true, NOW()),
  ('pro', 'Pro', 500, 40.00, true, NOW()),
  ('enterprise', 'Enterprise', 2000, 120.00, true, NOW());

-- Credit balances (one row per user, updated by trigger)
CREATE TABLE credit_balances (
  user_id INTEGER PRIMARY KEY,
  balance INTEGER NOT NULL DEFAULT 0,
  lifetime_purchased INTEGER DEFAULT 0,
  lifetime_spent INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Immutable transaction log
CREATE TABLE credit_transactions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  type VARCHAR(30) NOT NULL,
  reference_id TEXT,
  description TEXT,
  balance_after INTEGER NOT NULL,
  metadata JSONB DEFAULT '{}',
  idempotency_key VARCHAR(100) UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_credit_txns_user ON credit_transactions(user_id);
CREATE INDEX idx_credit_txns_type ON credit_transactions(type);
CREATE INDEX idx_credit_txns_created ON credit_transactions(created_at);

-- NOWPayments invoice tracking
CREATE TABLE credit_invoices (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  pack_id VARCHAR(20) REFERENCES credit_packs(id),
  nowpayments_invoice_id VARCHAR(100) UNIQUE,
  nowpayments_payment_id VARCHAR(100) UNIQUE,
  amount_usd DECIMAL(10,2) NOT NULL,
  credits INTEGER NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  pay_currency VARCHAR(20),
  fulfilled BOOLEAN DEFAULT FALSE,
  fulfilled_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_invoices_user ON credit_invoices(user_id);

-- Trigger: auto-update balance on transaction insert
CREATE OR REPLACE FUNCTION update_credit_balance()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO credit_balances (user_id, balance, lifetime_purchased, lifetime_spent, updated_at)
  VALUES (
    NEW.user_id, NEW.amount,
    CASE WHEN NEW.amount > 0 THEN NEW.amount ELSE 0 END,
    CASE WHEN NEW.amount < 0 THEN ABS(NEW.amount) ELSE 0 END,
    NOW()
  )
  ON CONFLICT (user_id) DO UPDATE SET
    balance = credit_balances.balance + NEW.amount,
    lifetime_purchased = credit_balances.lifetime_purchased +
      CASE WHEN NEW.amount > 0 THEN NEW.amount ELSE 0 END,
    lifetime_spent = credit_balances.lifetime_spent +
      CASE WHEN NEW.amount < 0 THEN ABS(NEW.amount) ELSE 0 END,
    updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_update_credit_balance
  AFTER INSERT ON credit_transactions
  FOR EACH ROW EXECUTE FUNCTION update_credit_balance();
