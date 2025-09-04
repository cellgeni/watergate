
CREATE TABLE IF NOT EXISTS wiretaps (
  event_time   TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_type   TEXT,
  user_id      VARCHAR,
  source_ip    INET,
  props        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_event_time ON wiretaps (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_event_type ON wiretaps (event_type);
CREATE INDEX IF NOT EXISTS idx_user_id ON wiretaps (user_id);
