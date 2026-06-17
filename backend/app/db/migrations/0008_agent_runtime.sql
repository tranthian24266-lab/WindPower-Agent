CREATE TABLE IF NOT EXISTS agent_runs (
    run_id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    case_id TEXT,
    session_id TEXT,
    status TEXT NOT NULL,
    current_step TEXT,
    input_json TEXT,
    output_json TEXT,
    error_json TEXT,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    triggered_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_case_id ON agent_runs(case_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_run_type ON agent_runs(run_type);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at);

CREATE TABLE IF NOT EXISTS agent_run_steps (
    step_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    error_json TEXT,
    duration_ms INTEGER,
    sequence_no INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_run_steps_run_id ON agent_run_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_run_steps_sequence_no ON agent_run_steps(run_id, sequence_no);

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    tool_call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_version TEXT,
    request_json TEXT,
    response_json TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id),
    FOREIGN KEY(step_id) REFERENCES agent_run_steps(step_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_run_id ON agent_tool_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_step_id ON agent_tool_calls(step_id);

ALTER TABLE report_versions ADD COLUMN run_id TEXT;
CREATE INDEX IF NOT EXISTS idx_report_versions_run_id ON report_versions(run_id);
