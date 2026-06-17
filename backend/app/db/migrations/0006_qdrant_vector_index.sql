CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_vector_store_id
ON knowledge_chunks(vector_store_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_model
ON knowledge_chunks(embedding_model);
