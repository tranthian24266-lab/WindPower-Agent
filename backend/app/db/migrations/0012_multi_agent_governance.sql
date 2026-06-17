CREATE TABLE IF NOT EXISTS agent_audit_logs (
    audit_log_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    outcome TEXT NOT NULL,
    run_id TEXT,
    trace_id TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_created_at ON agent_audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_action ON agent_audit_logs(action, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_resource ON agent_audit_logs(resource_type, resource_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_run_id ON agent_audit_logs(run_id, created_at);
