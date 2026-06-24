export type TaskType = "fault_diagnosis" | "rul_prediction" | "anomaly_detection";

export interface ModelSummary {
  model_id: string;
  task_type: TaskType;
  model_dir: string;
  entrypoint: string;
  status: string;
  version: string;
  model_name: string;
  paper_title?: string | null;
  dataset?: string | null;
  input_format?: string[] | string | null;
  output_labels?: string[] | null;
  feature_names?: string[] | null;
  threshold?: number | null;
  limitations: string[];
  readme_summary?: string | null;
}

export interface FileInfo {
  file_id: string;
  original_filename: string;
  stored_path: string;
  suffix: string;
  content_type?: string | null;
  size_bytes: number;
  created_at: string;
}

export interface DiagnoseResponse {
  status: string;
  case_id: string;
  file_id: string;
  task_type: TaskType;
  model_id: string;
  model_name?: string | null;
  model_version_id?: string | null;
  model_alias?: string | null;
  selection_reason?: string | null;
  risk_level?: string | null;
  output_dir: string;
  result_json_path: string;
  created_at: string;
  result: Record<string, unknown>;
}

export interface AutoRoutingCandidate {
  task_type: TaskType;
  model_id: string;
  model_name?: string | null;
  score: number;
  evidence: string[];
  mismatches: string[];
}

export interface AutoDiagnosisRouting {
  status: "selected" | "needs_confirmation" | "unsupported" | "confirmed";
  confidence: number;
  selected_task_type?: TaskType | null;
  selected_model_id?: string | null;
  evidence: string[];
  candidates: AutoRoutingCandidate[];
  input_profile: {
    filename: string;
    suffix: string;
    size_bytes: number;
    container_type: string;
    columns: string[];
    array_shape?: number[] | null;
    array_keys: string[];
    warnings: string[];
  };
}

export interface AutoDiagnosePendingResponse {
  status: "needs_confirmation" | "unsupported";
  file_id: string;
  routing: AutoDiagnosisRouting;
}

export type AutoDiagnoseResponse = (DiagnoseResponse & { routing: AutoDiagnosisRouting }) | AutoDiagnosePendingResponse;

export interface BatchDiagnoseItem {
  filename: string;
  file_id?: string;
  status: string;
  run_id?: string;
  case_id?: string;
  task_type?: TaskType | null;
  model_id?: string | null;
  routing?: AutoDiagnosisRouting;
  error?: { type: string; message: string };
}

export interface BatchDiagnoseResponse {
  status: "completed" | "partial";
  batch_id: string;
  total: number;
  succeeded: number;
  needs_confirmation: number;
  failed: number;
  items: BatchDiagnoseItem[];
}

export interface CaseSummary {
  case_id: string;
  file_id: string;
  task_type: TaskType;
  model_id: string;
  model_name?: string | null;
  model_version_id?: string | null;
  model_alias?: string | null;
  selection_reason?: string | null;
  status: string;
  risk_level?: string | null;
  result_json_path: string;
  output_dir: string;
  created_at: string;
  report_html_path?: string | null;
  original_filename?: string | null;
  suffix?: string | null;
}

export interface CaseDetail extends CaseSummary {
  report_pdf_path?: string | null;
  stored_path?: string | null;
  content_type?: string | null;
  size_bytes?: number | null;
  result: Record<string, unknown>;
}

export interface ReportPayload {
  status: string;
  case_id: string;
  run_id?: string | null;
  report_html_path?: string | null;
  report_pdf_path?: string | null;
  html_content?: string;
  preview_url: string;
  download_url?: string;
  download_html_url?: string | null;
  download_pdf_url?: string | null;
  report_status?: string;
  pdf_status?: string;
  pdf_reason?: string | null;
  generation_metadata?: Record<string, unknown>;
}

export interface EnhancedReportSectionPayload {
  title: string;
  content: string;
  confidence: number;
  evidence_refs: string[];
}

export interface EnhancedReportCitationPayload {
  evidence_ref: string;
  title: string;
  excerpt: string;
  evidence_type: string;
  score?: number | null;
}

export interface EnhancedReportSimilarCasePayload {
  case_id: string;
  summary: string;
  score?: number | null;
}

export interface EnhancedReportJsonPayload {
  case_summary: EnhancedReportSectionPayload;
  diagnosis_conclusion: EnhancedReportSectionPayload;
  risk_assessment: EnhancedReportSectionPayload;
  evidence_summary: EnhancedReportSectionPayload;
  maintenance_actions: EnhancedReportSectionPayload;
  applicability_and_limits: EnhancedReportSectionPayload;
  similar_cases: EnhancedReportSimilarCasePayload[];
  appendix_metrics: Array<{ label: string; value: string }>;
  citations: EnhancedReportCitationPayload[];
}

export interface EnhancedReportPayload {
  status: string;
  case_id: string;
  report_version_id: string;
  run_id?: string | null;
  review_task_id?: string | null;
  report_type: string;
  report_status?: string;
  source_mode: string;
  report_json_path: string;
  report_html_path?: string | null;
  report_docx_path?: string | null;
  report_pdf_path?: string | null;
  report_json?: EnhancedReportJsonPayload;
  html_content?: string | null;
  preview_url: string;
  download_docx_url?: string | null;
  download_pdf_url?: string | null;
  versions_url: string;
  generation_metadata?: Record<string, unknown>;
}

export interface EnhancedReportVersion {
  report_version_id: string;
  case_id: string;
  run_id?: string | null;
  report_type: string;
  status: string;
  source_mode: string;
  report_json_path: string;
  report_html_path?: string | null;
  report_docx_path?: string | null;
  report_pdf_path?: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeIndexStatus {
  status: string;
  remote_enabled: boolean;
  qdrant_enabled: boolean;
  qdrant_prefer_remote: boolean;
  qdrant_collection_name: string;
  qdrant_url_configured: boolean;
  embedding_provider_requested: string;
  embedding_provider_resolved: string;
  embedding_model_name: string;
  embedding_fallback_used: boolean;
  embedding_warning?: string | null;
  document_count: number;
  chunk_count: number;
  indexed_chunk_count: number;
  remote_available: boolean;
  remote_ping_ok?: boolean;
  remote_collection_exists?: boolean;
  remote_collection?: Record<string, unknown>;
  payload_indexes?: string[];
  last_reindex_at?: string | null;
  last_reindex_status?: string | null;
  remote_error?: string | null;
}

export interface KnowledgeReindexResponse {
  status: string;
  mode: string;
  chunk_count: number;
  indexed_count: number;
  embedding_model: string;
  force_recreate?: boolean;
  error?: string | null;
}

export interface SystemConfigSummary {
  status: string;
  paths: {
    backend_root: string;
    project_root: string;
    littlemodel_root: string;
    littlemodel_root_exists: boolean;
    knowledge_base_path: string;
    knowledge_base_path_exists: boolean;
    uploads_path: string;
    outputs_path: string;
    reports_path: string;
  };
  integrations: {
    database_backend?: string;
    database_url_configured?: boolean;
    deepseek_configured: boolean;
    deepseek_base_url: string;
    deepseek_model_name: string;
    auth_enabled: boolean;
    api_key_configured: boolean;
    rbac_enabled?: boolean;
    audit_enabled?: boolean;
    qdrant_enabled: boolean;
    qdrant_config_enabled?: boolean;
    qdrant_url_configured: boolean;
    qdrant_remote_available?: boolean;
    qdrant_remote_ping_ok?: boolean;
  };
  features: {
    base_report_pdf_enabled: boolean;
    enhanced_reports_enabled: boolean;
    knowledge_rag_enabled: boolean;
    chat_rag_enabled: boolean;
    knowledge_ingestion_enabled: boolean;
    knowledge_case_ingestion_enabled: boolean;
    qdrant_enabled: boolean;
    qdrant_config_enabled?: boolean;
  };
}

export interface ChatReply {
  status: string;
  case_id: string;
  session_id: string;
  run_id?: string | null;
  answer: string;
  mode: string;
  citations?: Array<{
    document_id: string;
    chunk_id: string;
    title: string;
    source_path: string;
    source_type: string;
    chunk_index: number;
    summary: string;
    score: number;
  }>;
  retrieval_event_id?: string | null;
  knowledge_mode?: string;
}

export interface ChatHistoryMessage {
  session_id: string;
  case_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations?: KnowledgeCitation[];
  knowledge_mode?: string | null;
  retrieval_event_id?: string | null;
  message_metadata?: Record<string, unknown>;
}

export interface AgentToolCall {
  tool_call_id: string;
  run_id: string;
  step_id: string;
  tool_name: string;
  tool_version?: string | null;
  request?: Record<string, unknown> | null;
  response?: Record<string, unknown> | null;
  status: string;
  duration_ms?: number | null;
  created_at: string;
}

export interface AgentRunStep {
  step_id: string;
  run_id: string;
  step_name: string;
  step_type: string;
  status: string;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  duration_ms?: number | null;
  sequence_no: number;
  started_at: string;
  finished_at?: string | null;
  tool_calls: AgentToolCall[];
}

export interface AgentRun {
  run_id: string;
  run_type: string;
  case_id?: string | null;
  session_id?: string | null;
  status: string;
  current_step?: string | null;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  started_at: string;
  updated_at: string;
  finished_at?: string | null;
  triggered_by?: string | null;
  step_count?: number;
  tool_call_count?: number;
  review_tasks?: ReviewTaskSummary[];
  trace_id?: string | null;
  job?: {
    job_id: string;
    run_id: string;
    job_type: string;
    payload?: Record<string, unknown> | null;
    status: string;
    attempt_count: number;
    max_attempts: number;
    available_at: string;
    lease_expires_at?: string | null;
    worker_id?: string | null;
    last_error?: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
    finished_at?: string | null;
  };
  steps: AgentRunStep[];
}

export interface AgentRunTimelineItem {
  timestamp: string;
  kind: string;
  name: string;
  status: string;
  details?: Record<string, unknown> | null;
}

export interface ReviewTaskSummary {
  review_task_id: string;
  run_id?: string | null;
  case_id?: string | null;
  report_version_id?: string | null;
  review_type: string;
  status: string;
  priority: string;
  reason_code?: string | null;
  summary?: string | null;
  requested_at: string;
  updated_at: string;
  decided_at?: string | null;
}

export interface ReviewAction {
  review_action_id: string;
  review_task_id: string;
  action: string;
  actor?: string | null;
  comment?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface ReviewTaskDetail extends ReviewTaskSummary {
  metadata?: Record<string, unknown> | null;
  actions: ReviewAction[];
}

export interface EvalSuite {
  suite_id: string;
  title: string;
  version: string;
  description?: string | null;
  item_count: number;
}

export interface EvalRunItem {
  eval_item_id: string;
  eval_run_id: string;
  item_key: string;
  status: string;
  score?: number | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export interface EvalRun {
  eval_run_id: string;
  suite_id: string;
  suite_version: string;
  status: string;
  score?: number | null;
  passed_count: number;
  failed_count: number;
  total_count: number;
  summary?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  started_at: string;
  finished_at?: string | null;
  items?: EvalRunItem[];
}

export interface ObservabilitySummary {
  status: string;
  event_count: number;
  events_path: string;
  counts_by_type: Record<string, number>;
  recent_events: Array<{
    event_id: string;
    event_type: string;
    created_at: string;
    payload: Record<string, unknown>;
  }>;
}

export interface AgentRunSummary {
  run_id: string;
  run_type: string;
  case_id?: string | null;
  session_id?: string | null;
  status: string;
  current_step?: string | null;
  started_at: string;
  updated_at: string;
  finished_at?: string | null;
  triggered_by?: string | null;
}

export interface AgentRunSubmission {
  status: string;
  run_id: string;
  job_id: string;
  run_type: string;
  case_id?: string | null;
  session_id?: string | null;
  poll_url: string;
}

export interface KnowledgeCitation {
  document_id: string;
  chunk_id: string;
  title: string;
  source_path: string;
  source_type: string;
  chunk_index: number;
  summary: string;
  score: number;
}

export interface KnowledgeDocument {
  document_id: string;
  source_type: string;
  source_path: string;
  title: string;
  task_type?: string | null;
  subtask_type?: string | null;
  component?: string | null;
  model_family_id?: string | null;
  model_version_id?: string | null;
  language?: string | null;
  status: string;
  checksum?: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeChunk {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  summary?: string | null;
  title: string;
  source_path: string;
  source_type: string;
  task_type?: string | null;
  component?: string | null;
  score?: number;
  metadata: Record<string, unknown>;
  keywords?: string[];
  citations?: Record<string, unknown>[];
}

export interface KnowledgeIngestionRun {
  ingestion_run_id: string;
  status: string;
  source_scope: string;
  discovered_count: number;
  processed_count: number;
  failed_count: number;
  started_at: string;
  finished_at?: string | null;
  details: Record<string, unknown>;
}

export interface ApiListResponse<T> {
  status: string;
  count: number;
  models?: T[];
  cases?: T[];
}

export interface CatalogAlias {
  alias_id: string;
  family_id: string;
  alias_name: string;
  model_version_id: string;
  created_at: string;
  updated_at: string;
}

export interface CatalogModelVersion {
  model_version_id: string;
  family_id: string;
  family_code?: string;
  display_name?: string;
  task_type?: TaskType | string;
  subtask_type?: string | null;
  component?: string | null;
  legacy_model_id: string;
  version: string;
  status: string;
  validation_status: string;
  model_dir: string;
  entrypoint: string;
  framework?: string | null;
  runtime?: string | null;
  dataset?: string | null;
  paper_title?: string | null;
  input_format?: string[] | string | null;
  output_schema?: string[] | Record<string, unknown> | null;
  feature_names?: string[] | null;
  limitations?: string[] | null;
  priority: number;
  capabilities?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  last_validated_at?: string | null;
  aliases?: CatalogAlias[];
  validation_runs?: CatalogValidationRun[];
}

export interface CatalogValidationRun {
  validation_run_id: string;
  model_version_id: string;
  validation_type: string;
  status: string;
  summary?: string | null;
  details?: Record<string, unknown> | null;
  started_at: string;
  finished_at?: string | null;
}

export interface CatalogModelListItem {
  family_id: string;
  family_code: string;
  display_name: string;
  task_type: TaskType | string;
  subtask_type?: string | null;
  component?: string | null;
  description?: string | null;
  owner?: string | null;
  created_at: string;
  updated_at: string;
  tags?: string[] | null;
  aliases: CatalogAlias[];
  latest_version: CatalogModelVersion;
}

export interface CatalogModelDetail {
  family_id: string;
  family_code: string;
  display_name: string;
  task_type: TaskType | string;
  subtask_type?: string | null;
  component?: string | null;
  description?: string | null;
  owner?: string | null;
  tags?: string[] | null;
  aliases: CatalogAlias[];
  versions_count: number;
  created_at: string;
  updated_at: string;
}

export interface CatalogModelListResponse {
  status: string;
  items: CatalogModelListItem[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
}

export interface CatalogRoutingPreview {
  status: string;
  selected_model_version_id?: string | null;
  selected_legacy_model_id: string;
  selection_reason: string;
  model_alias?: string | null;
  evaluated_candidates: CatalogModelListItem[];
}

export interface CatalogSyncResponse {
  status: string;
  sync_run_id: string;
  source_path: string;
  discovered_count: number;
  upserted_count: number;
  failed_count: number;
  details?: Record<string, unknown> | null;
  started_at: string;
  finished_at: string;
  summary: string;
}

export interface CatalogValidateResponse {
  validation_run_id: string;
  status: string;
  summary: string;
  details?: Record<string, unknown> | null;
}

export interface ModelPackageInspection {
  model_card: Record<string, unknown> & {
    model_id: string;
    family_code?: string;
    model_name: string;
    model_version: string;
    task_type: TaskType | string;
    description?: string;
    dataset?: string;
    limitations?: string[];
    parameter_schema?: Record<string, unknown>;
  };
  entrypoint: string;
  sample_path: string;
  weight_files: string[];
  requirements: string[];
  requirements_installation: string;
  warnings: string[];
}

export interface ModelPackageUpload {
  upload_id: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  status: "inspected" | "validated" | "published";
  created_at: string;
  updated_at: string;
  inspection: ModelPackageInspection;
  validation?: {
    status: string;
    validated_at: string;
    sample_path: string;
    result_keys: string[];
    result_status?: string | null;
    stdout?: string;
  } | null;
  published_model_version_id?: string | null;
  published_model_dir?: string | null;
}

export interface AuditLog {
  audit_id: string;
  actor_id: string;
  role: string;
  action: string;
  resource_type: string;
  resource_id: string;
  run_id?: string | null;
  trace_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export interface SpecialistHandoff {
  event_id: string;
  created_at: string;
  run_id?: string | null;
  trace_id?: string | null;
  from_agent?: string | null;
  to_agent?: string | null;
  capability?: string | null;
  status?: string | null;
}

export interface SpecialistSummary {
  status: string;
  counts_by_specialist: Record<string, number>;
  counts_by_workflow: Record<string, number>;
  recent_handoffs: SpecialistHandoff[];
}
