-- Гибрид-режим: локальный скрипт пишет YD-данные сюда, cloud-routine читает.
-- Pull раз в сутки (точнее — каждый раз когда ноут включён); cloud берёт MAX(pulled_at).

SET search_path TO goliath, public;

CREATE TABLE IF NOT EXISTS yd_raw_pulls (
  id              SERIAL PRIMARY KEY,
  pulled_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  date_from       DATE NOT NULL,
  date_to         DATE NOT NULL,
  campaign_id     BIGINT NOT NULL,
  campaign_name   TEXT,
  cost_rub        NUMERIC(10,2) NOT NULL DEFAULT 0,
  clicks          INT NOT NULL DEFAULT 0,
  impressions     INT NOT NULL DEFAULT 0,
  conversions     INT NOT NULL DEFAULT 0,
  raw             JSONB
);

CREATE INDEX IF NOT EXISTS yd_raw_pulls_lookup_idx
  ON yd_raw_pulls (date_from, date_to, pulled_at DESC);
CREATE INDEX IF NOT EXISTS yd_raw_pulls_pulled_idx
  ON yd_raw_pulls (pulled_at DESC);

-- View: последний pull для каждой пары (date_from, date_to)
CREATE OR REPLACE VIEW v_yd_latest_pull AS
SELECT DISTINCT ON (date_from, date_to, campaign_id)
  date_from, date_to, campaign_id, campaign_name,
  cost_rub, clicks, impressions, conversions,
  pulled_at
FROM yd_raw_pulls
ORDER BY date_from, date_to, campaign_id, pulled_at DESC;

COMMENT ON TABLE yd_raw_pulls IS 'YD данные, забранные локальным скриптом (из-за IP-allowlist Я.Директа). Append-only; cloud берёт MAX(pulled_at).';
