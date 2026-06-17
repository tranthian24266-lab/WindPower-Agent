CREATE TABLE IF NOT EXISTS agent_run_queue (
    job_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    available_at TEXT NOT NULL,
    lease_expires_at TEXT,
    worker_id TEXT,
    last_error_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_run_queue_status_available
    ON agent_run_queue(status, available_at);

CREATE INDEX IF NOT EXISTS idx_agent_run_queue_worker_status
    ON agent_run_queue(worker_id, status);
