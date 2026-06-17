CREATE TABLE IF NOT EXISTS agent_review_tasks (
    review_task_id TEXT PRIMARY KEY,
    run_id TEXT,
    case_id TEXT,
    report_version_id TEXT,
    review_type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    reason_code TEXT,
    summary TEXT,
    metadata_json TEXT,
    requested_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id),
    FOREIGN KEY(report_version_id) REFERENCES report_versions(report_version_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_review_tasks_status ON agent_review_tasks(status, requested_at);
CREATE INDEX IF NOT EXISTS idx_agent_review_tasks_run_id ON agent_review_tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_review_tasks_report_version_id ON agent_review_tasks(report_version_id);

CREATE TABLE IF NOT EXISTS agent_review_actions (
    review_action_id TEXT PRIMARY KEY,
    review_task_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT,
    comment TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(review_task_id) REFERENCES agent_review_tasks(review_task_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_review_actions_review_task_id
ON agent_review_actions(review_task_id, created_at);
