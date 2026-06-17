CREATE TABLE IF NOT EXISTS report_versions (
    report_version_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    status TEXT NOT NULL,
    source_mode TEXT NOT NULL,
    report_json_path TEXT NOT NULL,
    report_html_path TEXT,
    report_docx_path TEXT,
    report_pdf_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_report_versions_case_id ON report_versions(case_id);
CREATE INDEX IF NOT EXISTS idx_report_versions_report_type ON report_versions(report_type);
CREATE INDEX IF NOT EXISTS idx_report_versions_created_at ON report_versions(created_at);

CREATE TABLE IF NOT EXISTS report_evidence_items (
    evidence_item_id TEXT PRIMARY KEY,
    report_version_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    source_id TEXT,
    title TEXT,
    excerpt TEXT,
    score REAL,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(report_version_id) REFERENCES report_versions(report_version_id)
);

CREATE INDEX IF NOT EXISTS idx_report_evidence_items_report_version_id ON report_evidence_items(report_version_id);
CREATE INDEX IF NOT EXISTS idx_report_evidence_items_evidence_type ON report_evidence_items(evidence_type);
