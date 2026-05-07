-- Эхо v1 — голос ЦА из транскрибаций ОП.
-- Источник: внешний API (предоставляется Деном), pull раз в сутки/неделю.
-- Pipeline: API → анонимизация PII → voice_raw_transcripts → LLM-извлечение → voice_insights.

SET search_path TO goliath, public;

-- 1) Сырые транскрибации (анонимизированные)
CREATE TABLE IF NOT EXISTS voice_raw_transcripts (
  id                 SERIAL PRIMARY KEY,
  external_id        TEXT NOT NULL,                   -- ID из исходной БД (для дедупликации pull'ов)
  pulled_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  call_date          TIMESTAMPTZ NOT NULL,
  phone_normalized   TEXT,                            -- E.164: +7XXXXXXXXXX
  duration_sec       INT,
  manager_id         TEXT,                            -- идентификатор менеджера ОП (если отдаётся API)
  transcript_text    TEXT NOT NULL,                   -- УЖЕ анонимизированный
  raw_metadata       JSONB,                           -- всё прочее что отдал API
  -- метчинг (заполняется отдельным шагом sync с getcourseUsers по phone)
  matched_email      TEXT,
  matched_uid        BIGINT,                          -- gcuid
  matched_utm_campaign  TEXT,
  matched_product    TEXT,                            -- sysai/openclaw/n8n/law/...
  matched_at         TIMESTAMPTZ,
  UNIQUE (external_id)
);
CREATE INDEX IF NOT EXISTS voice_raw_call_date_idx ON voice_raw_transcripts (call_date DESC);
CREATE INDEX IF NOT EXISTS voice_raw_phone_idx     ON voice_raw_transcripts (phone_normalized);
CREATE INDEX IF NOT EXISTS voice_raw_product_idx   ON voice_raw_transcripts (matched_product);

-- 2) Извлечённые инсайты (структурированный слой для Голиафа/Аякса)
CREATE TABLE IF NOT EXISTS voice_insights (
  id                SERIAL PRIMARY KEY,
  transcript_id     INT NOT NULL REFERENCES voice_raw_transcripts(id) ON DELETE CASCADE,
  extracted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  category          TEXT NOT NULL CHECK (category IN (
    'objection',       -- возражение лида («дорого», «не сейчас», «уже пробовал»)
    'trigger',         -- триггер интереса («хочу свою AI-студию», «уйти из найма»)
    'pain',            -- боль («не могу сам разобраться», «не хватает структуры»)
    'language',        -- характерная формулировка ЦА (для копи)
    'refusal_reason',  -- причина отказа от покупки
    'success_signal'   -- что хвалили после оплаты / что зацепило
  )),
  quote             TEXT NOT NULL,                    -- дословная цитата (анонимизированная)
  context_summary   TEXT,                             -- 1-2 строки что было до/после
  product           TEXT,                             -- sysai/openclaw/n8n/law/null
  segment           TEXT,                             -- руководитель / специалист / фрилансер / новичок
  funnel_stage      TEXT,                             -- cold / warmup / objection / closing / onboarding / churn
  confidence        NUMERIC(3,2),                     -- 0.00-1.00 (уверенность LLM в категоризации)
  metadata          JSONB
);
CREATE INDEX IF NOT EXISTS voice_insights_category_idx ON voice_insights (category);
CREATE INDEX IF NOT EXISTS voice_insights_product_idx  ON voice_insights (product);
CREATE INDEX IF NOT EXISTS voice_insights_extracted_idx ON voice_insights (extracted_at DESC);

-- 3) Word-bank — cumulative банк фраз (накапливается, дедуплицируется по нормализованной форме)
CREATE TABLE IF NOT EXISTS voice_wordbank (
  id                SERIAL PRIMARY KEY,
  phrase_normalized TEXT NOT NULL,                    -- lower + trim + без знаков → ключ дедупликации
  phrase_canonical  TEXT NOT NULL,                    -- читабельная форма (как впервые встретилась)
  category          TEXT NOT NULL,                    -- те же что в voice_insights
  product           TEXT,
  first_seen        TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen         TIMESTAMPTZ NOT NULL DEFAULT now(),
  occurrences       INT NOT NULL DEFAULT 1,
  example_quote_ids INT[] DEFAULT '{}',               -- ссылки на voice_insights.id
  UNIQUE (phrase_normalized, category, product)
);
CREATE INDEX IF NOT EXISTS voice_wordbank_freq_idx ON voice_wordbank (occurrences DESC);
CREATE INDEX IF NOT EXISTS voice_wordbank_last_idx ON voice_wordbank (last_seen DESC);

-- 4) Pull-журнал — отслеживать что уже забрали из внешнего API
CREATE TABLE IF NOT EXISTS voice_pull_log (
  id              SERIAL PRIMARY KEY,
  pulled_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  pull_from       TIMESTAMPTZ,                        -- от какой даты тянули (cursor)
  pull_to         TIMESTAMPTZ,                        -- до какой
  records_total   INT,
  records_new     INT,
  records_updated INT,
  api_response_status INT,
  error_text      TEXT
);
CREATE INDEX IF NOT EXISTS voice_pull_log_at_idx ON voice_pull_log (pulled_at DESC);

-- Views для удобства консьюмеров (Голиаф/Аякс)
CREATE OR REPLACE VIEW v_voice_recent_objections AS
SELECT vi.product, vi.quote, vi.segment, vi.context_summary, vrt.call_date, vi.confidence
FROM voice_insights vi
JOIN voice_raw_transcripts vrt ON vrt.id = vi.transcript_id
WHERE vi.category = 'objection' AND vrt.call_date > now() - interval '30 days'
ORDER BY vrt.call_date DESC;

CREATE OR REPLACE VIEW v_voice_top_phrases_per_product AS
SELECT product, category, phrase_canonical, occurrences, last_seen
FROM voice_wordbank
WHERE last_seen > now() - interval '60 days' AND product IS NOT NULL
ORDER BY product, category, occurrences DESC;

COMMENT ON TABLE voice_raw_transcripts IS 'Анонимизированные транскрипты звонков ОП — источник для Эхо. Pull через внешний API (Ден).';
COMMENT ON TABLE voice_insights IS 'Структурированные инсайты, извлечённые LLM из транскриптов. Голиаф/Аякс читают свежие.';
COMMENT ON TABLE voice_wordbank IS 'Cumulative банк фраз ЦА с подсчётом частоты. Используется для копи.';
