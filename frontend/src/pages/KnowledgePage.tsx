import { useEffect, useMemo, useState } from "react";
import { Folder, FileText, Database, Activity, Zap, Server, ChevronDown, ChevronUp, ScanLine, RefreshCw, ServerCrash, CheckCircle2, Clock } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  getApiErrorMessage,
  getKnowledgeChunks,
  getKnowledgeDocuments,
  getKnowledgeIndexStatus,
  getKnowledgeIngestionRuns,
  ingestKnowledge,
  reindexKnowledge,
} from "../lib/api";
import { formatDate, taskTypeLabel } from "../lib/format";
import type {
  KnowledgeChunk,
  KnowledgeDocument,
  KnowledgeIndexStatus,
  KnowledgeIngestionRun,
} from "../types";

type KnowledgePanel = "chunks" | "runs";

type DocumentGroup = {
  key: string;
  label: string;
  documents: KnowledgeDocument[];
};

const SOURCE_GROUP_LABELS: Record<string, string> = {
  historical_case_summary: "历史案例总结",
  littlemodel_summary: "模型摘要",
  littlemodel_model_card: "模型卡片",
  littlemodel_readme: "模型 README",
  curated_papers: "论文摘要",
  curated_datasets: "数据集说明",
  model_markdown: "模型知识文档",
  domain_markdown: "领域知识文档",
};

const SOURCE_GROUP_ORDER = [
  "historical_case_summary",
  "curated_papers",
  "curated_datasets",
  "littlemodel_summary",
  "littlemodel_model_card",
  "littlemodel_readme",
  "model_markdown",
  "domain_markdown",
];

function getDocumentBadge(document: KnowledgeDocument): string {
  const sourceLabel = SOURCE_GROUP_LABELS[document.source_type] || document.source_type;
  return document.task_type ? `${sourceLabel} · ${taskTypeLabel(document.task_type)}` : sourceLabel;
}

function groupDocuments(documents: KnowledgeDocument[]): DocumentGroup[] {
  const grouped = new Map<string, KnowledgeDocument[]>();

  for (const document of documents) {
    const bucket = grouped.get(document.source_type) ?? [];
    bucket.push(document);
    grouped.set(document.source_type, bucket);
  }

  return Array.from(grouped.entries())
    .sort((left, right) => {
      const leftIndex = SOURCE_GROUP_ORDER.indexOf(left[0]);
      const rightIndex = SOURCE_GROUP_ORDER.indexOf(right[0]);
      const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
      const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;
      return normalizedLeft - normalizedRight || left[0].localeCompare(right[0]);
    })
    .map(([key, items]) => ({
      key,
      label: SOURCE_GROUP_LABELS[key] || key,
      documents: items,
    }));
}

function formatIndexMode(status: KnowledgeIndexStatus | null): string {
  if (!status) {
    return "尚未读取";
  }
  if (!status.qdrant_enabled || !status.qdrant_url_configured) {
    return "仅本地索引";
  }
  if (status.remote_available) {
    return status.qdrant_prefer_remote ? "远端优先" : "远端可用";
  }
  return "回退本地索引";
}

function formatRemoteError(status: KnowledgeIndexStatus | null): string {
  if (!status?.remote_error) {
    return "";
  }
  if (status.remote_error.indexOf("WinError 10061") >= 0) {
    return "Qdrant 服务当前没有启动或端口不可达。";
  }
  if (status.remote_error.indexOf("qdrant_disabled_or_unconfigured") >= 0) {
    return "未开启 Qdrant，系统仅使用本地索引。";
  }
  return status.remote_error;
}

export function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [runs, setRuns] = useState<KnowledgeIngestionRun[]>([]);
  const [indexStatus, setIndexStatus] = useState<KnowledgeIndexStatus | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [activePanel, setActivePanel] = useState<KnowledgePanel>("chunks");
  const [documentsExpanded, setDocumentsExpanded] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<string[]>(["historical_case_summary"]);
  const [loading, setLoading] = useState(true);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [runningIngest, setRunningIngest] = useState(false);
  const [runningReindex, setRunningReindex] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedDocument = documents.find((document) => document.document_id === selectedDocumentId) ?? null;
  const documentGroups = useMemo(() => groupDocuments(documents), [documents]);
  const remoteErrorText = formatRemoteError(indexStatus);

  async function loadKnowledge() {
    setLoading(true);
    try {
      const [nextDocuments, nextRuns, nextIndexStatus] = await Promise.all([
        getKnowledgeDocuments(),
        getKnowledgeIngestionRuns(),
        getKnowledgeIndexStatus(),
      ]);
      setDocuments(nextDocuments);
      setRuns(nextRuns);
      setIndexStatus(nextIndexStatus);

      const hasSelectedDocument = nextDocuments.some((document) => document.document_id === selectedDocumentId);
      const nextSelectedDocumentId = hasSelectedDocument ? selectedDocumentId : nextDocuments[0]?.document_id || "";
      const selectedSourceType =
        nextDocuments.find((document) => document.document_id === nextSelectedDocumentId)?.source_type || null;

      setSelectedDocumentId(nextSelectedDocumentId);
      if (!nextSelectedDocumentId) {
        setChunks([]);
      }

      if (selectedSourceType) {
        setExpandedGroups((current) =>
          current.includes(selectedSourceType) ? current : [selectedSourceType, ...current].slice(0, 4),
        );
      }

      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "知识库信息加载失败。"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadKnowledge();
  }, []);

  useEffect(() => {
    if (!selectedDocumentId) {
      setChunks([]);
      setChunkLoading(false);
      return;
    }

    let cancelled = false;
    setChunkLoading(true);

    getKnowledgeChunks({ documentId: selectedDocumentId, limit: 12 })
      .then((items) => {
        if (cancelled) {
          return;
        }
        setChunks(items);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (cancelled) {
          return;
        }
        setError(getApiErrorMessage(caught, "知识切片加载失败。"));
      })
      .finally(() => {
        if (!cancelled) {
          setChunkLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDocumentId]);

  async function handleIngest() {
    setRunningIngest(true);
    setStatusMessage(null);
    try {
      const result = await ingestKnowledge(false);
      setStatusMessage(
        `扫描入库完成：发现 ${result.discovered_count} 篇，成功 ${result.processed_count} 篇，失败 ${result.failed_count} 篇。`,
      );
      setActivePanel("runs");
      await loadKnowledge();
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "知识入库失败。"));
    } finally {
      setRunningIngest(false);
    }
  }

  async function handleReindex(forceRecreate = false) {
    setRunningReindex(true);
    setStatusMessage(null);
    try {
      const result = await reindexKnowledge(forceRecreate);
      const suffix = result.error ? ` (远端提示：${result.error})` : "";
      setStatusMessage(
        `索引重建完成：模式 [${result.mode}]，共 ${result.chunk_count} 个切片，已写入 ${result.indexed_count} 个。${suffix}`,
      );
      await loadKnowledge();
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "知识索引重建失败。"));
    } finally {
      setRunningReindex(false);
    }
  }

  function handleSelectDocument(document: KnowledgeDocument) {
    setSelectedDocumentId(document.document_id);
    setActivePanel("chunks");
    setDocumentsExpanded(false);
    setExpandedGroups((current) =>
      current.includes(document.source_type) ? current : [document.source_type, ...current].slice(0, 4),
    );
  }

  function toggleGroup(groupKey: string) {
    setExpandedGroups((current) =>
      current.includes(groupKey) ? current.filter((item) => item !== groupKey) : [...current, groupKey],
    );
  }

  return (
    <div className="page-stack max-w-7xl">
      <PageHeader
        variant="workspace"
        eyebrow="知识与检索底座"
        title="知识引擎与索引控制台"
        description="管理结构化及非结构化领域知识、检查切片质量，并维护向量检索服务 (Qdrant/Local) 的运行状态。"
        action={
          <div className="flex gap-4">
            <button className="ghost-button" type="button" onClick={() => void handleReindex(false)} disabled={runningReindex || loading}>
              {runningReindex ? <><span className="loading-spinner"/> 重建中...</> : <><RefreshCw size={18} /> 重建向量索引</>}
            </button>
            <button className="action-button" type="button" onClick={handleIngest} disabled={runningIngest || loading}>
              {runningIngest ? <><span className="loading-spinner border-white border-t-transparent"/> 扫描中...</> : <><ScanLine size={18} /> 扫描入库</>}
            </button>
          </div>
        }
      />

      {loading && documents.length === 0 ? <StatusBanner message="正在加载知识引擎状态..." /> : null}
      {statusMessage ? <StatusBanner variant="success" message={statusMessage} /> : null}
      {error ? <StatusBanner variant="error" message={error} /> : null}

      {/* Index Status Area */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-2">
        <div className="p-6 bg-white border border-slate-200 rounded-2xl flex flex-col relative overflow-hidden">
          <div className="absolute top-0 right-0 p-6 opacity-5"><Database size={120} /></div>
          <div className="flex items-center gap-2 text-slate-500 mb-4 z-10"><Database size={18} /> <h3 className="font-semibold text-sm">知识库规模</h3></div>
          <div className="flex flex-col gap-1 z-10">
            <span className="text-3xl font-bold text-slate-800">{indexStatus?.document_count ?? 0} <span className="text-sm font-normal text-slate-500">篇文档</span></span>
            <span className="text-sm text-slate-500 mt-2">拆分为 {indexStatus?.chunk_count ?? 0} 个知识切片</span>
            <span className="text-sm text-slate-500">已写入向量索引 {indexStatus?.indexed_chunk_count ?? 0} 个</span>
          </div>
        </div>
        
        <div className="p-6 bg-white border border-slate-200 rounded-2xl flex flex-col relative overflow-hidden">
          <div className="absolute top-0 right-0 p-6 opacity-5"><Server size={120} /></div>
          <div className="flex items-center gap-2 text-slate-500 mb-4 z-10"><Server size={18} /> <h3 className="font-semibold text-sm">检索服务状态</h3></div>
          <div className="flex flex-col gap-1 z-10">
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-3 h-3 rounded-full ${indexStatus?.remote_available ? 'bg-emerald-500' : indexStatus?.qdrant_enabled ? 'bg-amber-500' : 'bg-slate-300'}`}></span>
              <span className="text-lg font-bold text-slate-800">{formatIndexMode(indexStatus)}</span>
            </div>
            <span className="text-xs text-slate-500 leading-relaxed mb-2">
              Qdrant启用: {indexStatus?.qdrant_enabled ? "是" : "否"} · 
              服务可用: {indexStatus?.remote_available ? "是" : "否"}
            </span>
            {indexStatus?.remote_available ? (
              <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded inline-block w-fit">远端集合已连接，负载 {indexStatus.payload_indexes?.length ?? 0} 个索引项</span>
            ) : (
              <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded inline-block border border-amber-100">{remoteErrorText || "当前未连接远端 Qdrant"}</span>
            )}
          </div>
        </div>

        <div className="p-6 bg-white border border-slate-200 rounded-2xl flex flex-col relative overflow-hidden">
          <div className="absolute top-0 right-0 p-6 opacity-5"><Zap size={120} /></div>
          <div className="flex items-center gap-2 text-slate-500 mb-4 z-10"><Zap size={18} /> <h3 className="font-semibold text-sm">最近操作信息</h3></div>
          <div className="flex flex-col gap-2 z-10 mt-1">
            <div className="flex flex-col gap-0.5">
              <span className="text-xs text-slate-400">Embedding 驱动</span>
              <span className="text-sm font-medium text-slate-800 truncate">{indexStatus?.embedding_provider_resolved || "unknown"} ({indexStatus?.embedding_model_name || "unknown"})</span>
            </div>
            <div className="flex flex-col gap-0.5 mt-2">
              <span className="text-xs text-slate-400">最近索引重建时间</span>
              <span className="text-sm font-medium text-slate-800">{formatDate(indexStatus?.last_reindex_at || undefined)}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Two-Column Layout */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Document Browser */}
        <article className="content-panel lg:col-span-4 flex flex-col p-0 border border-slate-200 bg-white min-h-[600px] overflow-hidden">
          <div className="p-4 border-b border-slate-100 bg-slate-50/80">
            <h3 className="text-sm font-semibold text-slate-800 mb-1">知识文档浏览器</h3>
            <p className="text-xs text-slate-500">共计 {documents.length} 篇领域源文档</p>
          </div>

          <div className="p-4 bg-slate-50 border-b border-slate-100">
            <div className="p-4 bg-white border border-slate-200 rounded-xl shadow-sm">
              <span className="text-xs text-slate-400 font-medium mb-1 block">当前聚焦文档</span>
              <strong className="block text-sm text-emerald-700 truncate mb-2">{selectedDocument?.title || "未选择文档"}</strong>
              {selectedDocument ? (
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-1 rounded w-fit">{getDocumentBadge(selectedDocument)}</span>
                  <span className="text-[10px] text-slate-400 truncate mt-1" title={selectedDocument.source_path}>{selectedDocument.source_path}</span>
                </div>
              ) : (
                <span className="text-xs text-slate-400">在下方列表中选择文档即可预览对应的知识切片内容。</span>
              )}
            </div>
            
            <button
              className="w-full mt-3 py-2 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center justify-center gap-1 transition-colors"
              type="button"
              onClick={() => setDocumentsExpanded(!documentsExpanded)}
              disabled={documents.length === 0}
            >
              {documentsExpanded ? <><ChevronUp size={14}/> 收起文档树</> : <><ChevronDown size={14}/> 展开完整分类结构</>}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
            {documentsExpanded ? (
              <div className="flex flex-col gap-2">
                {documentGroups.map((group) => {
                  const expanded = expandedGroups.includes(group.key);
                  return (
                    <div key={group.key} className="bg-white border border-slate-100 rounded-xl overflow-hidden">
                      <button
                        type="button"
                        className="w-full flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100 transition-colors"
                        onClick={() => toggleGroup(group.key)}
                      >
                        <div className="flex items-center gap-2">
                          <Folder size={14} className="text-emerald-600" />
                          <span className="text-sm font-medium text-slate-700">{group.label}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-medium bg-white text-slate-500 px-1.5 py-0.5 rounded border border-slate-200">{group.documents.length}</span>
                          {expanded ? <ChevronUp size={14} className="text-slate-400"/> : <ChevronDown size={14} className="text-slate-400"/>}
                        </div>
                      </button>
                      
                      {expanded && (
                        <div className="flex flex-col gap-1 p-2 bg-white">
                          {group.documents.map((document) => (
                            <button
                              key={document.document_id}
                              type="button"
                              className={`text-left p-3 rounded-lg border transition-all flex items-start gap-3 ${
                                selectedDocumentId === document.document_id 
                                  ? "border-emerald-500 bg-emerald-50/30" 
                                  : "border-transparent hover:bg-slate-50"
                              }`}
                              onClick={() => handleSelectDocument(document)}
                            >
                              <FileText size={14} className={`mt-0.5 shrink-0 ${selectedDocumentId === document.document_id ? "text-emerald-500" : "text-slate-400"}`} />
                              <div className="overflow-hidden">
                                <strong className={`block text-xs truncate mb-1 ${selectedDocumentId === document.document_id ? "text-emerald-800 font-bold" : "text-slate-700"}`}>{document.title}</strong>
                                <span className="block text-[10px] text-slate-400 truncate">{document.source_path.split('/').pop()}</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 p-6 text-center">
                <Folder size={48} className="mb-3 opacity-20" />
                <p className="text-sm">文档树已收起</p>
                <p className="text-xs mt-1">点击“展开完整分类结构”查看</p>
              </div>
            )}

            {documents.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 p-6 text-center">
                <FileText size={48} className="mb-3 opacity-20" />
                <p className="text-sm font-medium text-slate-600 mb-1">当前还没有知识文档</p>
                <p className="text-xs">点击顶部“扫描入库”后会出现文档分类</p>
              </div>
            )}
          </div>
        </article>

        {/* Right: Content Preview Area */}
        <article className="content-panel lg:col-span-8 flex flex-col p-0 border border-slate-200 bg-white min-h-[600px] overflow-hidden">
          <div className="flex border-b border-slate-100 bg-slate-50/50">
            <button
              type="button"
              className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activePanel === "chunks" ? "border-emerald-500 text-emerald-700 bg-white" : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-white/50"}`}
              onClick={() => setActivePanel("chunks")}
            >
              <FileText size={16} /> 文档切片预览 (Chunks)
            </button>
            <button
              type="button"
              className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activePanel === "runs" ? "border-emerald-500 text-emerald-700 bg-white" : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-white/50"}`}
              onClick={() => setActivePanel("runs")}
            >
              <Activity size={16} /> 入库作业记录
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 bg-slate-50/30">
            {activePanel === "chunks" ? (
              <div className="flex flex-col gap-4">
                {chunkLoading && <div className="p-8 text-center text-slate-500"><span className="loading-spinner border-emerald-500 border-t-transparent mr-2"/> 正在加载切片内容...</div>}
                
                {!chunkLoading && chunks.length === 0 && (
                  <div className="flex flex-col items-center justify-center p-12 text-slate-400 bg-white border border-slate-200 rounded-2xl border-dashed">
                    <FileText size={48} className="mb-4 opacity-20" />
                    <p className="text-sm font-medium text-slate-600">当前文档没有切片</p>
                    <p className="text-xs mt-1">可能内容为空或尚未被索引切分处理</p>
                  </div>
                )}
                
                {!chunkLoading && chunks.length > 0 && (
                  <div className="flex justify-between items-end mb-2">
                    <span className="text-sm font-medium text-slate-700">发现 {chunks.length} 个切片片段</span>
                  </div>
                )}

                {!chunkLoading && chunks.map((chunk) => (
                  <div key={chunk.chunk_id} className="p-5 bg-white border border-slate-200 rounded-xl shadow-sm hover:border-emerald-200 transition-colors group">
                    <div className="flex justify-between items-start mb-3 border-b border-slate-50 pb-3">
                      <strong className="text-sm text-slate-800 font-medium group-hover:text-emerald-700 transition-colors">{chunk.title}</strong>
                      <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-[10px] font-mono rounded">Chunk #{chunk.chunk_index}</span>
                    </div>
                    <div className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap font-mono bg-slate-50 p-4 rounded-lg border border-slate-100 max-h-[300px] overflow-y-auto custom-scrollbar">
                      {chunk.summary || chunk.content}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {runs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center p-12 text-slate-400 bg-white border border-slate-200 rounded-2xl border-dashed">
                    <Activity size={48} className="mb-4 opacity-20" />
                    <p className="text-sm font-medium text-slate-600">暂无入库记录</p>
                    <p className="text-xs mt-1">执行扫描入库后将在此处保留历史记录</p>
                  </div>
                ) : (
                  runs.slice(0, 10).map((run) => (
                    <div key={run.ingestion_run_id} className="p-5 bg-white border border-slate-200 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`w-2 h-2 rounded-full ${run.status === 'completed' ? 'bg-emerald-500' : run.status === 'failed' ? 'bg-rose-500' : 'bg-amber-500'}`}></span>
                          <strong className="text-sm font-medium text-slate-800 uppercase tracking-wide">{run.status}</strong>
                          <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded ml-2">{run.source_scope}</span>
                        </div>
                        <div className="flex gap-4 text-xs text-slate-600 mt-2">
                          <span className="flex items-center gap-1"><ScanLine size={12} className="text-slate-400"/> 发现 {run.discovered_count}</span>
                          <span className="flex items-center gap-1"><CheckCircle2 size={12} className="text-emerald-500"/> 成功 {run.processed_count}</span>
                          {run.failed_count > 0 && <span className="flex items-center gap-1 text-rose-600"><ServerCrash size={12} /> 失败 {run.failed_count}</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100 whitespace-nowrap">
                        <Clock size={12} />
                        {formatDate(run.started_at)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}
