ALTER TABLE agent_runs ADD COLUMN trace_id TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_runs_trace_id ON agent_runs(trace_id);

CREATE TABLE IF NOT EXISTS eval_runs (
    eval_run_id TEXT PRIMARY KEY,
    suite_id TEXT NOT NULL,
    suite_version TEXT NOT NULL,
    status TEXT NOT NULL,
    score REAL,
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    total_count INTEGER NOT NULL,
    summary_json TEXT,
    metadata_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_suite_id ON eval_runs(suite_id, started_at);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON eval_runs(status, started_at);

CREATE TABLE IF NOT EXISTS eval_run_items (
    eval_item_id TEXT PRIMARY KEY,
    eval_run_id TEXT NOT NULL,
    item_key TEXT NOT NULL,
    status TEXT NOT NULL,
    score REAL,
    details_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(eval_run_id) REFERENCES eval_runs(eval_run_id)
);

CREATE INDEX IF NOT EXISTS idx_eval_run_items_eval_run_id ON eval_run_items(eval_run_id, created_at);
