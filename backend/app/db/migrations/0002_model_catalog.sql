CREATE TABLE IF NOT EXISTS model_families (
    family_id TEXT PRIMARY KEY,
    family_code TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    subtask_type TEXT,
    component TEXT,
    description TEXT,
    owner TEXT,
    tags_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_model_families_task_type ON model_families(task_type);
CREATE INDEX IF NOT EXISTS idx_model_families_family_code ON model_families(family_code);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    legacy_model_id TEXT UNIQUE NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    model_dir TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    framework TEXT,
    runtime TEXT,
    dataset TEXT,
    paper_title TEXT,
    input_format TEXT,
    output_schema_json TEXT,
    feature_names_json TEXT,
    limitations_json TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    capabilities_json TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_validated_at TEXT,
    FOREIGN KEY(family_id) REFERENCES model_families(family_id)
);

CREATE INDEX IF NOT EXISTS idx_model_versions_family_id ON model_versions(family_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_legacy_model_id ON model_versions(legacy_model_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_status ON model_versions(status);
CREATE INDEX IF NOT EXISTS idx_model_versions_validation_status ON model_versions(validation_status);

CREATE TABLE IF NOT EXISTS model_aliases (
    alias_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    alias_name TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(family_id, alias_name),
    FOREIGN KEY(family_id) REFERENCES model_families(family_id),
    FOREIGN KEY(model_version_id) REFERENCES model_versions(model_version_id)
);

CREATE INDEX IF NOT EXISTS idx_model_aliases_alias_name ON model_aliases(alias_name);
CREATE INDEX IF NOT EXISTS idx_model_aliases_model_version_id ON model_aliases(model_version_id);

CREATE TABLE IF NOT EXISTS model_validation_runs (
    validation_run_id TEXT PRIMARY KEY,
    model_version_id TEXT NOT NULL,
    validation_type TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    details_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(model_version_id) REFERENCES model_versions(model_version_id)
);

CREATE INDEX IF NOT EXISTS idx_model_validation_runs_model_version_id ON model_validation_runs(model_version_id);

CREATE TABLE IF NOT EXISTS model_registry_sync_runs (
    sync_run_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    status TEXT NOT NULL,
    discovered_count INTEGER NOT NULL,
    upserted_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    details_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_model_registry_sync_runs_started_at ON model_registry_sync_runs(started_at);
