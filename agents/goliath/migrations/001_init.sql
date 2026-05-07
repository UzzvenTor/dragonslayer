-- =====================================================================
-- Голиаф v2 — initial schema
-- Размещение: схема `goliath` внутри БД `kurzemnek` (YC Postgres-кластер
-- rc1b-nftoajilh0nnj0gf.mdb.yandexcloud.net) — кластер Валерия для лендинга,
-- переиспользуем чтобы не плодить инфру.
--
-- Запуск: psql или python psycopg2 от пользователя kurzemnek_app
--    SET search_path TO goliath, public;
--    \i 001_init.sql
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS goliath AUTHORIZATION kurzemnek_app;
SET search_path TO goliath, public;
SET TIMEZONE = 'Europe/Moscow';

-- proposals: предложения, ждущие согласия Валерия
CREATE TABLE IF NOT EXISTS proposals (
  id              SERIAL PRIMARY KEY,
  date_proposed   TIMESTAMPTZ NOT NULL DEFAULT now(),
  category        TEXT NOT NULL CHECK (category IN (
    'pause', 'resume', 'scale_budget', 'change_target_cpa', 'change_bid',
    'new_hypothesis', 'creative_rotate', 'creative_text', 'negative_site',
    'bidmodifier_update', 'urgent_arpl_stop'
  )),
  product         TEXT,
  campaign_id     BIGINT,
  ad_group_id     BIGINT,
  ad_id           BIGINT,
  description     TEXT NOT NULL,
  reasoning       TEXT,
  proposed_action JSONB,
  status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending', 'discussing', 'applied', 'rejected', 'superseded', 'expired'
  )),
  expires_at      TIMESTAMPTZ NOT NULL,
  decided_at      TIMESTAMPTZ,
  decision_reason TEXT,
  superseded_by   INT REFERENCES proposals(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS proposals_status_idx       ON proposals(status);
CREATE INDEX IF NOT EXISTS proposals_date_idx         ON proposals(date_proposed DESC);
CREATE INDEX IF NOT EXISTS proposals_product_idx      ON proposals(product);
CREATE INDEX IF NOT EXISTS proposals_pending_active   ON proposals(expires_at) WHERE status = 'pending';

-- actions_log: журнал всех write-действий Голиафа
CREATE TABLE IF NOT EXISTS actions_log (
  id            SERIAL PRIMARY KEY,
  date_action   TIMESTAMPTZ NOT NULL DEFAULT now(),
  proposal_id   INT REFERENCES proposals(id) ON DELETE SET NULL,
  trigger_type  TEXT NOT NULL CHECK (trigger_type IN (
    'proposal', 'auto_stop', 'scheduled', 'manual', 'rollback'
  )),
  tool          TEXT NOT NULL,
  args          JSONB NOT NULL,
  before_state  JSONB,
  after_state   JSONB,
  result        JSONB,
  reverted_by   INT REFERENCES actions_log(id) ON DELETE SET NULL,
  reverted_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS actions_log_date_idx       ON actions_log(date_action DESC);
CREATE INDEX IF NOT EXISTS actions_log_trigger_idx    ON actions_log(trigger_type);
CREATE INDEX IF NOT EXISTS actions_log_proposal_idx   ON actions_log(proposal_id);

-- daily_snapshots: агрегаты за день per продукт (для трендов)
CREATE TABLE IF NOT EXISTS daily_snapshots (
  id              SERIAL PRIMARY KEY,
  snapshot_date   DATE NOT NULL,
  product         TEXT NOT NULL,
  cost_rub        NUMERIC(10,2),
  clicks          INT,
  impressions     INT,
  unique_leads    INT,
  viewers         INT,
  viewer_rate_pct NUMERIC(5,2),
  orders_intent   INT,
  paid_orders     INT,
  revenue_rub     NUMERIC(12,2),
  cpa_rub         NUMERIC(10,2),
  roas_pct        NUMERIC(8,2),
  raw_data        JSONB,
  fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (snapshot_date, product)
);
CREATE INDEX IF NOT EXISTS daily_snapshots_date_idx ON daily_snapshots(snapshot_date DESC);

-- auto_actions: журнал auto-stops (3×/5×/10× ARPL)
CREATE TABLE IF NOT EXISTS auto_actions (
  id                SERIAL PRIMARY KEY,
  date_action       TIMESTAMPTZ NOT NULL DEFAULT now(),
  rule              TEXT NOT NULL CHECK (rule IN ('3xARPL', '5xARPL', '10xARPL', '13K_no_payments')),
  product           TEXT,
  campaign_id       BIGINT,
  ad_group_id       BIGINT,
  ad_id             BIGINT,
  cost_window_rub   NUMERIC(10,2) NOT NULL,
  arpl_threshold    NUMERIC(10,2) NOT NULL,
  window_days       INT NOT NULL DEFAULT 14,
  action_log_id     INT REFERENCES actions_log(id) ON DELETE SET NULL,
  rollback_deadline TIMESTAMPTZ NOT NULL,
  reverted          BOOLEAN NOT NULL DEFAULT false,
  reverted_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS auto_actions_date_idx      ON auto_actions(date_action DESC);
CREATE INDEX IF NOT EXISTS auto_actions_pending_revert ON auto_actions(rollback_deadline) WHERE reverted = false;

-- chat_context: память диалога Валерий ↔ Голиаф
CREATE TABLE IF NOT EXISTS chat_context (
  id              SERIAL PRIMARY KEY,
  date_recorded   TIMESTAMPTZ NOT NULL DEFAULT now(),
  proposal_id     INT REFERENCES proposals(id) ON DELETE CASCADE,
  speaker         TEXT NOT NULL CHECK (speaker IN ('valerii', 'goliath')),
  message         TEXT NOT NULL,
  metadata        JSONB
);
CREATE INDEX IF NOT EXISTS chat_context_proposal_idx ON chat_context(proposal_id);
CREATE INDEX IF NOT EXISTS chat_context_date_idx     ON chat_context(date_recorded DESC);

-- Views
CREATE OR REPLACE VIEW v_active_proposals AS
SELECT *
FROM proposals
WHERE status IN ('pending', 'discussing')
  AND (expires_at > now() OR status = 'discussing')
ORDER BY date_proposed DESC;

CREATE OR REPLACE VIEW v_revertable_auto_actions AS
SELECT a.*, l.tool, l.args, l.before_state
FROM auto_actions a
LEFT JOIN actions_log l ON l.id = a.action_log_id
WHERE a.reverted = false
  AND a.rollback_deadline > now()
ORDER BY a.date_action DESC;

COMMENT ON SCHEMA goliath IS 'Голиаф v2 — write-агент Я.Директа Зерокодера. См. Wiki/shared/agents/Голиаф v2 — спецификация агента.md';
COMMENT ON TABLE proposals IS 'Предложения Голиафа на изменения (ждут согласия Валерия в Claude Code)';
COMMENT ON TABLE actions_log IS 'Журнал всех write-действий — для аудита и откатов';
COMMENT ON TABLE daily_snapshots IS 'Агрегаты за день per продукт — источник трендов и графиков';
COMMENT ON TABLE auto_actions IS 'Auto-stops по правилам ARPL (Фаза 2)';
COMMENT ON TABLE chat_context IS 'Память диалога Валерий ↔ Голиаф per предложение';
