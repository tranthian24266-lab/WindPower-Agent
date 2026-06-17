SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS uploaded_files (
        file_id TEXT PRIMARY KEY,
        original_filename TEXT NOT NULL,
        stored_path TEXT NOT NULL,
        suffix TEXT NOT NULL,
        content_type TEXT,
        size_bytes INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS diagnosis_cases (
        case_id TEXT PRIMARY KEY,
        file_id TEXT NOT NULL,
        task_type TEXT NOT NULL,
        model_id TEXT NOT NULL,
        model_name TEXT,
        status TEXT NOT NULL,
        risk_level TEXT,
        result_json_path TEXT NOT NULL,
        output_dir TEXT NOT NULL,
        created_at TEXT NOT NULL,
        report_html_path TEXT,
        report_pdf_path TEXT,
        FOREIGN KEY(file_id) REFERENCES uploaded_files(file_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(case_id) REFERENCES diagnosis_cases(case_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        message_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        citations_json TEXT,
        knowledge_mode TEXT,
        retrieval_event_id TEXT,
        message_metadata_json TEXT,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
    )
    """,
]
