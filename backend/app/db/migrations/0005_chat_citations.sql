PRAGMA foreign_keys=OFF;

ALTER TABLE chat_messages RENAME TO chat_messages_legacy;

CREATE TABLE chat_messages (
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
);

INSERT INTO chat_messages (
    message_id,
    session_id,
    role,
    content,
    created_at,
    citations_json,
    knowledge_mode,
    retrieval_event_id,
    message_metadata_json
)
SELECT
    message_id,
    session_id,
    role,
    content,
    created_at,
    NULL,
    NULL,
    NULL,
    NULL
FROM chat_messages_legacy;

DROP TABLE chat_messages_legacy;

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_retrieval_event_id ON chat_messages(retrieval_event_id);

PRAGMA foreign_keys=ON;
