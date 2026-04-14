CREATE TABLE IF NOT EXISTS payment_orders (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  product_code TEXT NOT NULL,
  product_name TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  unit_price_cents INTEGER NOT NULL,
  total_price_cents INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'CNY',
  status TEXT NOT NULL DEFAULT 'pending',
  metadata TEXT DEFAULT '{}',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  paid_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created
ON payment_orders(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_orders_status_created
ON payment_orders(status, created_at DESC);

CREATE TABLE IF NOT EXISTS payment_transactions (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  provider_txn_id TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  raw_payload TEXT DEFAULT '{}',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_transactions_provider_txn
ON payment_transactions(provider, provider_txn_id);

CREATE INDEX IF NOT EXISTS idx_payment_transactions_order
ON payment_transactions(order_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_entitlements (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  feature_code TEXT NOT NULL,
  balance INTEGER NOT NULL DEFAULT 0,
  total_granted INTEGER NOT NULL DEFAULT 0,
  total_consumed INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_user_entitlements_user_feature
ON user_entitlements(user_id, feature_code);

CREATE TABLE IF NOT EXISTS entitlement_ledger (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  feature_code TEXT NOT NULL,
  change_amount INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  note TEXT DEFAULT '',
  metadata TEXT DEFAULT '{}',
  created_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_entitlement_ledger_source
ON entitlement_ledger(user_id, feature_code, source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_entitlement_ledger_user_feature
ON entitlement_ledger(user_id, feature_code, created_at DESC);
