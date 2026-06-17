CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT NOT NULL,
    task_type TEXT,
    subtask_type TEXT,
    component TEXT,
    model_family_id TEXT,
    model_version_id TEXT,
    language TEXT,
    status TEXT NOT NULL,
    checksum TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_task_type ON knowledge_documents(task_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_source_type ON knowledge_documents(source_type);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    tokens_estimate INTEGER,
    embedding_model TEXT,
    vector_store_id TEXT,
    keywords_json TEXT,
    citations_json TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES knowledge_documents(document_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document_id ON knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_chunk_index ON knowledge_chunks(chunk_index);

CREATE TABLE IF NOT EXISTS knowledge_ingestion_runs (
    ingestion_run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    discovered_count INTEGER NOT NULL,
    processed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    details_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_knowledge_ingestion_runs_started_at ON knowledge_ingestion_runs(started_at);

CREATE TABLE IF NOT EXISTS retrieval_events (
    retrieval_event_id TEXT PRIMARY KEY,
    case_id TEXT,
    query_text TEXT NOT NULL,
    task_type TEXT,
    top_k INTEGER NOT NULL,
    filters_json TEXT,
    results_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_retrieval_events_case_id ON retrieval_events(case_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_events_created_at ON retrieval_events(created_at);
