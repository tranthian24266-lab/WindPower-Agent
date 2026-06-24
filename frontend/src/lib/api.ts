import axios from "axios";

import type {
  AgentRun,
  AutoDiagnoseResponse,
  BatchDiagnoseResponse,
  AgentRunTimelineItem,
  AgentRunSubmission,
  AgentRunSummary,
  CatalogModelDetail,
  CatalogModelListResponse,
  CatalogModelVersion,
  CatalogRoutingPreview,
  CatalogSyncResponse,
  CatalogValidateResponse,
  CaseDetail,
  CaseSummary,
  ChatHistoryMessage,
  ChatReply,
  DiagnoseResponse,
  EvalRun,
  EvalSuite,
  EnhancedReportPayload,
  EnhancedReportVersion,
  FileInfo,
  KnowledgeChunk,
  KnowledgeDocument,
  KnowledgeIngestionRun,
  KnowledgeIndexStatus,
  KnowledgeReindexResponse,
  ModelSummary,
  ModelPackageUpload,
  ObservabilitySummary,
  ReviewTaskDetail,
  ReviewTaskSummary,
  ReportPayload,
  SpecialistSummary,
  SystemConfigSummary,
  TaskType,
  AuditLog,
} from "../types";

function normalizeApiBaseUrl(value: string | undefined): string {
  if (!value) {
    return "";
  }
  const trimmed = value.trim();
  if (!trimmed || trimmed === "/") {
    return "";
  }
  return trimmed.replace(/\/+$/, "");
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
export const API_KEY_STORAGE_KEY = "windpower_api_key";

function readStoredApiKey(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.sessionStorage.getItem(API_KEY_STORAGE_KEY) || "";
}

export function getStoredApiKey(): string {
  return readStoredApiKey();
}

export function setStoredApiKey(value: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const trimmed = value.trim();
  if (trimmed) {
    window.sessionStorage.setItem(API_KEY_STORAGE_KEY, trimmed);
    return;
  }
  window.sessionStorage.removeItem(API_KEY_STORAGE_KEY);
}

export function clearStoredApiKey(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.removeItem(API_KEY_STORAGE_KEY);
}

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!API_BASE_URL) {
    return normalizedPath;
  }
  return `${API_BASE_URL}${normalizedPath}`;
}

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

client.interceptors.request.use((config) => {
  const storedApiKey = readStoredApiKey();
  if (storedApiKey) {
    config.headers = config.headers ?? {};
    config.headers["X-API-Key"] = storedApiKey;
  }
  return config;
});

export function getApiErrorMessage(caught: unknown, fallback: string): string {
  if (axios.isAxiosError(caught)) {
    const detail = caught.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (caught.message) {
      return caught.message;
    }
  }

  if (caught instanceof Error) {
    return caught.message;
  }

  return fallback;
}

export async function getModels(): Promise<ModelSummary[]> {
  const response = await client.get<{ models: ModelSummary[] }>("/api/models");
  return response.data.models;
}

export async function getSystemConfigSummary(): Promise<SystemConfigSummary> {
  const response = await client.get<SystemConfigSummary>("/api/system/config-summary");
  return response.data;
}

export async function getModelCatalogModels(params?: {
  q?: string;
  taskType?: string;
  status?: string;
  validationStatus?: string;
  alias?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}): Promise<CatalogModelListResponse> {
  const response = await client.get<CatalogModelListResponse>("/api/model-catalog/models", {
    params: {
      q: params?.q || undefined,
      task_type: params?.taskType || undefined,
      status: params?.status || undefined,
      validation_status: params?.validationStatus || undefined,
      alias: params?.alias || undefined,
      page: params?.page || 1,
      page_size: params?.pageSize || undefined,
      sort_by: params?.sortBy || undefined,
      sort_order: params?.sortOrder || undefined,
    },
  });
  return response.data;
}

export async function getModelCatalogModel(familyId: string): Promise<CatalogModelDetail> {
  const response = await client.get<{ model: CatalogModelDetail }>(`/api/model-catalog/models/${familyId}`);
  return response.data.model;
}

export async function getModelCatalogVersions(familyId: string): Promise<CatalogModelVersion[]> {
  const response = await client.get<{ versions: CatalogModelVersion[] }>(`/api/model-catalog/models/${familyId}/versions`);
  return response.data.versions;
}

export async function getModelCatalogVersion(modelVersionId: string): Promise<CatalogModelVersion> {
  const response = await client.get<{ model_version: CatalogModelVersion }>(
    `/api/model-catalog/model-versions/${modelVersionId}`,
  );
  return response.data.model_version;
}

export async function syncModelCatalog(): Promise<CatalogSyncResponse> {
  const response = await client.post<CatalogSyncResponse>("/api/model-catalog/sync");
  return response.data;
}

export async function validateModelCatalogVersion(modelVersionId: string): Promise<CatalogValidateResponse> {
  const response = await client.post<CatalogValidateResponse>(
    `/api/model-catalog/model-versions/${modelVersionId}/validate`,
  );
  return response.data;
}

export async function uploadModelPackage(file: File): Promise<ModelPackageUpload> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await client.post<{ package: ModelPackageUpload }>("/api/model-catalog/packages/upload", formData);
  return response.data.package;
}

export async function updateModelPackageMetadata(
  uploadId: string,
  payload: { model_name?: string; description?: string; dataset?: string; limitations?: string[] },
): Promise<ModelPackageUpload> {
  const response = await client.put<{ package: ModelPackageUpload }>(
    `/api/model-catalog/packages/${uploadId}/metadata`,
    payload,
  );
  return response.data.package;
}

export async function validateModelPackage(uploadId: string): Promise<ModelPackageUpload> {
  const response = await client.post<{ package: ModelPackageUpload }>(
    `/api/model-catalog/packages/${uploadId}/validate`,
  );
  return response.data.package;
}

export async function publishModelPackage(uploadId: string): Promise<ModelPackageUpload> {
  const response = await client.post<{ package: ModelPackageUpload }>(
    `/api/model-catalog/packages/${uploadId}/publish`,
  );
  return response.data.package;
}

export async function archiveModelVersion(modelVersionId: string): Promise<CatalogModelVersion> {
  const response = await client.post<{ model_version: CatalogModelVersion }>(
    `/api/model-catalog/model-versions/${modelVersionId}/archive`,
  );
  return response.data.model_version;
}

export async function deleteModelVersion(modelVersionId: string): Promise<void> {
  await client.delete(`/api/model-catalog/model-versions/${modelVersionId}`);
}

export async function updateModelAlias(
  familyId: string,
  aliasName: string,
  modelVersionId: string,
  reason?: string,
): Promise<{ status: string }> {
  const response = await client.put<{ status: string }>(`/api/model-catalog/models/${familyId}/aliases/${aliasName}`, {
    model_version_id: modelVersionId,
    reason,
  });
  return response.data;
}

export async function previewModelRouting(params: {
  taskType: string;
  preferredAlias?: string;
  preferredModelId?: string;
  inputFormat?: string;
}): Promise<CatalogRoutingPreview> {
  const response = await client.get<CatalogRoutingPreview>("/api/model-catalog/routing/preview", {
    params: {
      task_type: params.taskType,
      preferred_alias: params.preferredAlias || undefined,
      preferred_model_id: params.preferredModelId || undefined,
      input_format: params.inputFormat || undefined,
    },
  });
  return response.data;
}

export async function uploadFile(file: File): Promise<FileInfo> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await client.post<{ file: FileInfo }>("/api/upload", formData);
  return response.data.file;
}

export async function diagnose(
  fileId: string,
  taskType: TaskType,
  options?: {
    preferredAlias?: string;
    preferredModelId?: string;
  },
): Promise<DiagnoseResponse> {
  const response = await client.post<DiagnoseResponse>("/api/diagnose", {
    file_id: fileId,
    task_type: taskType,
    options: options
      ? {
          preferred_alias: options.preferredAlias || undefined,
          preferred_model_id: options.preferredModelId || undefined,
        }
      : undefined,
  });
  return response.data;
}
export async function autoDiagnose(
  fileId: string,
  confirmedTaskType?: TaskType,
  options?: { preferredAlias?: string; preferredModelId?: string },
): Promise<AutoDiagnoseResponse> {
  const response = await client.post<AutoDiagnoseResponse>("/api/diagnose/auto", {
    file_id: fileId,
    confirmed_task_type: confirmedTaskType || undefined,
    options: options
      ? {
          preferred_alias: options.preferredAlias || undefined,
          preferred_model_id: options.preferredModelId || undefined,
        }
      : undefined,
  });
  return response.data;
}

export async function batchDiagnose(files: File[]): Promise<BatchDiagnoseResponse> {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);
  const response = await client.post<BatchDiagnoseResponse>("/api/diagnose/batch", formData, {
    timeout: 600000,
  });
  return response.data;
}


export async function getCases(filters?: {
  taskType?: string;
  riskLevel?: string;
}): Promise<CaseSummary[]> {
  const response = await client.get<{ cases: CaseSummary[] }>("/api/cases", {
    params: {
      task_type: filters?.taskType || undefined,
      risk_level: filters?.riskLevel || undefined,
    },
  });
  return response.data.cases;
}

export async function getCase(caseId: string): Promise<CaseDetail> {
  const response = await client.get<{ case: CaseDetail }>(`/api/cases/${caseId}`);
  return response.data.case;
}

export async function generateReport(caseId: string): Promise<ReportPayload> {
  const response = await client.post<ReportPayload>(`/api/reports/${caseId}/generate`);
  return response.data;
}

export async function getReport(caseId: string): Promise<ReportPayload> {
  const response = await client.get<ReportPayload>(`/api/reports/${caseId}`);
  return response.data;
}

export async function generateEnhancedReport(caseId: string): Promise<EnhancedReportPayload> {
  const response = await client.post<EnhancedReportPayload>(`/api/enhanced-reports/${caseId}/generate`);
  return response.data;
}

export async function getEnhancedReport(caseId: string, reportVersionId?: string): Promise<EnhancedReportPayload> {
  const response = await client.get<EnhancedReportPayload>(`/api/enhanced-reports/${caseId}`, {
    params: {
      report_version_id: reportVersionId || undefined,
    },
  });
  return response.data;
}

export async function getEnhancedReportVersions(caseId: string): Promise<EnhancedReportVersion[]> {
  const response = await client.get<{ versions: EnhancedReportVersion[] }>(`/api/enhanced-reports/${caseId}/versions`);
  return response.data.versions;
}

export async function sendChat(caseId: string, question: string, sessionId?: string): Promise<ChatReply> {
  const response = await client.post<ChatReply>("/api/chat", {
    case_id: caseId,
    question,
    session_id: sessionId,
  });
  return response.data;
}

export async function getChatHistory(caseId: string): Promise<ChatHistoryMessage[]> {
  const response = await client.get<{ messages: ChatHistoryMessage[] }>(`/api/chat/history/${caseId}`);
  return response.data.messages;
}

export async function ingestKnowledge(includeDefaultsOnly = false): Promise<{
  status: string;
  ingestion_run_id?: string;
  discovered_count: number;
  processed_count: number;
  failed_count: number;
}> {
  const response = await client.post("/api/knowledge/ingest", {
    source_scope: includeDefaultsOnly ? "knowledge_base" : "all",
    include_defaults_only: includeDefaultsOnly,
  });
  return response.data;
}

export async function getKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  const response = await client.get<{ documents: KnowledgeDocument[] }>("/api/knowledge/documents");
  return response.data.documents;
}

export async function getKnowledgeChunks(params?: {
  documentId?: string;
  taskType?: string;
  sourceType?: string;
  limit?: number;
}): Promise<KnowledgeChunk[]> {
  const response = await client.get<{ chunks: KnowledgeChunk[] }>("/api/knowledge/chunks", {
    params: {
      document_id: params?.documentId || undefined,
      task_type: params?.taskType || undefined,
      source_type: params?.sourceType || undefined,
      limit: params?.limit || 20,
    },
  });
  return response.data.chunks;
}

export async function getKnowledgeIngestionRuns(): Promise<KnowledgeIngestionRun[]> {
  const response = await client.get<{ runs: KnowledgeIngestionRun[] }>("/api/knowledge/ingestion-runs");
  return response.data.runs;
}

export async function reindexKnowledge(forceRecreate = false): Promise<KnowledgeReindexResponse> {
  const response = await client.post<KnowledgeReindexResponse>("/api/knowledge/reindex", {
    force_recreate: forceRecreate,
  });
  return response.data;
}

export async function getKnowledgeIndexStatus(): Promise<KnowledgeIndexStatus> {
  const response = await client.get<KnowledgeIndexStatus>("/api/knowledge/index-status");
  return response.data;
}

export async function getAgentRuns(params?: {
  caseId?: string;
  runType?: string;
  limit?: number;
}): Promise<AgentRunSummary[]> {
  const response = await client.get<{ runs: AgentRunSummary[] }>("/api/agent-runs", {
    params: {
      case_id: params?.caseId || undefined,
      run_type: params?.runType || undefined,
      limit: params?.limit || 20,
    },
  });
  return response.data.runs;
}

export async function getAgentRun(runId: string): Promise<AgentRun> {
  const response = await client.get<{ run: AgentRun }>(`/api/agent-runs/${runId}`);
  return response.data.run;
}

export async function getAgentRunTimeline(
  runId: string,
): Promise<{ runId: string; traceId?: string | null; timeline: AgentRunTimelineItem[] }> {
  const response = await client.get<{
    run_id: string;
    trace_id?: string | null;
    timeline: AgentRunTimelineItem[];
  }>(`/api/agent-runs/${runId}/timeline`);
  return {
    runId: response.data.run_id,
    traceId: response.data.trace_id,
    timeline: response.data.timeline,
  };
}

export async function createAgentRun(payload: {
  runType: "chat_answer" | "enhanced_report";
  caseId?: string;
  sessionId?: string;
  input?: Record<string, unknown>;
}): Promise<AgentRunSubmission> {
  const response = await client.post<AgentRunSubmission>("/api/agent-runs", {
    run_type: payload.runType,
    case_id: payload.caseId,
    session_id: payload.sessionId,
    input: payload.input || {},
  });
  return response.data;
}

export async function cancelAgentRun(runId: string): Promise<{ status: string; run_id: string }> {
  const response = await client.post<{ status: string; run_id: string }>(`/api/agent-runs/${runId}/cancel`);
  return response.data;
}

export async function resumeAgentRun(runId: string): Promise<{ status: string; run_id: string }> {
  const response = await client.post<{ status: string; run_id: string }>(`/api/agent-runs/${runId}/resume`);
  return response.data;
}

export async function getReviewTasks(params?: {
  status?: string;
  reviewType?: string;
  limit?: number;
}): Promise<ReviewTaskSummary[]> {
  const response = await client.get<{ tasks: ReviewTaskSummary[] }>("/api/reviews", {
    params: {
      status: params?.status || undefined,
      review_type: params?.reviewType || undefined,
      limit: params?.limit || 50,
    },
  });
  return response.data.tasks;
}

export async function getReviewTask(reviewTaskId: string): Promise<ReviewTaskDetail> {
  const response = await client.get<{ task: ReviewTaskDetail }>(`/api/reviews/${reviewTaskId}`);
  return response.data.task;
}

async function postReviewDecision(
  reviewTaskId: string,
  action: "approve" | "reject" | "request-changes",
  payload?: { reviewer?: string; comment?: string },
): Promise<ReviewTaskDetail> {
  const response = await client.post<{ task: ReviewTaskDetail }>(`/api/reviews/${reviewTaskId}/${action}`, payload || {});
  return response.data.task;
}

export async function approveReviewTask(
  reviewTaskId: string,
  payload?: { reviewer?: string; comment?: string },
): Promise<ReviewTaskDetail> {
  return postReviewDecision(reviewTaskId, "approve", payload);
}

export async function rejectReviewTask(
  reviewTaskId: string,
  payload?: { reviewer?: string; comment?: string },
): Promise<ReviewTaskDetail> {
  return postReviewDecision(reviewTaskId, "reject", payload);
}

export async function requestReviewChanges(
  reviewTaskId: string,
  payload?: { reviewer?: string; comment?: string },
): Promise<ReviewTaskDetail> {
  return postReviewDecision(reviewTaskId, "request-changes", payload);
}

export async function getEvalSuites(): Promise<EvalSuite[]> {
  const response = await client.get<{ suites: EvalSuite[] }>("/api/evals/suites");
  return response.data.suites;
}

export async function getEvalRuns(limit = 50): Promise<EvalRun[]> {
  const response = await client.get<{ runs: EvalRun[] }>("/api/evals", { params: { limit } });
  return response.data.runs;
}

export async function getEvalRun(evalRunId: string): Promise<EvalRun> {
  const response = await client.get<{ eval_run: EvalRun }>(`/api/evals/${evalRunId}`);
  return response.data.eval_run;
}

export async function runEvalSuite(suiteId: string): Promise<EvalRun> {
  const response = await client.post<{ eval_run: EvalRun }>("/api/evals/run", { suite_id: suiteId });
  return response.data.eval_run;
}

export async function getObservabilitySummary(): Promise<ObservabilitySummary> {
  const response = await client.get<ObservabilitySummary>("/api/system/observability-summary");
  return response.data;
}

export async function getAuditLogs(limit = 50): Promise<AuditLog[]> {
  const response = await client.get<{ logs: AuditLog[] }>("/api/system/audit-logs", { params: { limit } });
  return response.data.logs;
}

export async function getSpecialistSummary(): Promise<SpecialistSummary> {
  const response = await client.get<SpecialistSummary>("/api/system/specialist-summary");
  return response.data;
}
