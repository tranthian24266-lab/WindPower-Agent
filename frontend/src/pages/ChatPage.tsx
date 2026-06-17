import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Sparkles, User, Send, BookOpen, ChevronDown, CheckCircle2, History, MessageSquare, Briefcase, ChevronRight, FileText, Activity } from "lucide-react";

import { StatusBanner } from "../components/StatusBanner";
import { createAgentRun, getAgentRun, getApiErrorMessage, getCases, getChatHistory } from "../lib/api";
import { formatDate, taskTypeLabel } from "../lib/format";
import type { CaseSummary, ChatHistoryMessage } from "../types";

const DEFAULT_QUESTION = "请用一句话总结这个案例，并给出下一步维护建议。";

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [messages, setMessages] = useState<ChatHistoryMessage[]>([]);
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);
  const pollingRef = useRef<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const currentCaseId = searchParams.get("caseId") || "";

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pendingRunId]);

  async function loadHistory(caseId: string) {
    const history = await getChatHistory(caseId);
    setMessages(history);
    setSessionId(history.length > 0 ? history[history.length - 1].session_id : undefined);
    const latestAssistant = [...history].reverse().find((item) => item.role === "assistant");
    const runId = latestAssistant?.message_metadata?.run_id;
    setLatestRunId(typeof runId === "string" ? runId : null);
  }

  useEffect(() => {
    getCases()
      .then((items) => {
        setCases(items);
        if (!currentCaseId && items[0]) {
          setSearchParams({ caseId: items[0].case_id });
        }
      })
      .catch((caught: unknown) => setError(getApiErrorMessage(caught, "加载案例列表失败。")));
  }, [currentCaseId, setSearchParams]);

  useEffect(() => {
    if (!currentCaseId) {
      return;
    }
    loadHistory(currentCaseId)
      .catch(() => {
        setMessages([]);
        setLatestRunId(null);
      });
  }, [currentCaseId]);

  useEffect(() => {
    if (!pendingRunId) {
      return;
    }
    const activeRunId = pendingRunId;

    async function pollRun() {
      try {
        const run = await getAgentRun(activeRunId);
        setLatestRunId(run.run_id);
        if (run.status === "succeeded" && run.output) {
          const output = run.output as Record<string, unknown>;
          if (typeof output.session_id === "string") {
            setSessionId(output.session_id);
          }
          await loadHistory(currentCaseId);
          setPendingRunId(null);
          setIsSubmitting(false);
          setError(null);
          return;
        }
        if (run.status === "failed" || run.status === "cancelled") {
          const message = typeof run.error?.message === "string" ? run.error.message : "问答运行失败。";
          setError(message);
          setPendingRunId(null);
          setIsSubmitting(false);
        }
      } catch (caught: unknown) {
        setError(getApiErrorMessage(caught, "获取运行状态失败。"));
        setPendingRunId(null);
        setIsSubmitting(false);
      }
    }

    void pollRun();
    pollingRef.current = window.setInterval(() => {
      void pollRun();
    }, 1200);

    return () => {
      if (pollingRef.current !== null) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [currentCaseId, pendingRunId, sessionId]);

  async function handleSubmit() {
    if (!currentCaseId) {
      setError("请先选择一个案例。");
      return;
    }
    if (!question.trim() || isSubmitting) {
      return;
    }
    setIsSubmitting(true);
    try {
      const submittedAt = new Date().toISOString();
      setMessages((current) => [
        ...current,
        {
          session_id: sessionId || "",
          case_id: currentCaseId,
          role: "user",
          content: question,
          created_at: submittedAt,
          citations: [],
          message_metadata: {},
        },
      ]);
      const submission = await createAgentRun({
        runType: "chat_answer",
        caseId: currentCaseId,
        sessionId,
        input: {
          case_id: currentCaseId,
          question,
          session_id: sessionId,
        },
      });
      setLatestRunId(submission.run_id);
      setPendingRunId(submission.run_id);
      setQuestion("");
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "发送问题失败。"));
      setIsSubmitting(false);
    }
  }

  const currentCase = cases.find(c => c.case_id === currentCaseId);

  return (
    <div className="flex flex-col h-[calc(100vh-80px)] w-full max-w-6xl mx-auto">
      {/* Top Bar Context */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 bg-white border border-slate-200 rounded-2xl shadow-sm mb-4 shrink-0">
        <div className="flex items-center gap-4 w-full sm:w-auto">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <MessageSquare size={20} />
          </div>
          <div className="flex-1">
            <h1 className="text-base font-bold text-slate-800 leading-tight">专家诊断 Copilot</h1>
            <p className="text-xs text-slate-500">基于大模型与知识检索的智能诊断助手</p>
          </div>
        </div>

        <div className="mt-4 sm:mt-0 flex items-center gap-3 w-full sm:w-auto">
          {latestRunId && (
            <Link to={`/runs/${latestRunId}`} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-200 text-slate-600 rounded-lg text-xs font-medium hover:bg-slate-100 transition-colors">
              <Activity size={14} /> 最新运行记录
            </Link>
          )}
          <div className="flex items-center gap-3 p-2 bg-slate-50 rounded-xl border border-slate-100">
            <Briefcase size={16} className="text-slate-400 ml-2 shrink-0" />
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wide">当前上下文 (Context)</span>
              <select 
                className="text-sm font-semibold text-slate-700 bg-transparent border-none p-0 pr-8 focus:ring-0 cursor-pointer appearance-none outline-none"
                value={currentCaseId} 
                onChange={(event) => setSearchParams({ caseId: event.target.value })}
              >
                {cases.length === 0 ? <option value="">无可用案例</option> : null}
                {cases.map((item) => (
                  <option key={item.case_id} value={item.case_id}>
                    {item.case_id} · {taskTypeLabel(item.task_type)}
                  </option>
                ))}
              </select>
            </div>
            <ChevronDown size={14} className="text-slate-400 mr-2 shrink-0" />
          </div>
        </div>
      </div>

      {error ? <div className="shrink-0 mb-4"><StatusBanner variant="error" message={error} /></div> : null}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden relative">
        
        {/* Messages List */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 sm:p-6 custom-scrollbar bg-slate-50/50">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400">
              <Sparkles size={48} className="mb-4 opacity-20 text-emerald-600" />
              <h3 className="text-lg font-medium text-slate-700 mb-2">我是您的风电诊断智能体</h3>
              <p className="text-sm max-w-md text-center leading-relaxed">
                您可以向我提问关于当前案例的任何问题。我会结合本地知识库与模型诊断结果为您提供专业建议。
              </p>
              {currentCase && (
                <div className="mt-8 flex flex-wrap justify-center gap-2">
                  <button onClick={() => setQuestion("请总结当前案例的核心故障和建议处理方案。")} className="px-4 py-2 bg-white border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 rounded-full text-xs font-medium text-slate-600 transition-colors">
                    总结当前案例
                  </button>
                  <button onClick={() => setQuestion("这个故障在历史上有出现过吗？通常怎么解决？")} className="px-4 py-2 bg-white border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 rounded-full text-xs font-medium text-slate-600 transition-colors">
                    检索历史相似案例
                  </button>
                  <button onClick={() => setQuestion("请帮我生成一份标准的诊断维护工单。")} className="px-4 py-2 bg-white border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 rounded-full text-xs font-medium text-slate-600 transition-colors">
                    生成维护工单
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="max-w-4xl mx-auto flex flex-col gap-6">
              {messages.map((message, index) => {
                const isUser = message.role === "user";
                return (
                  <div key={`${message.created_at}-${index}`} className={`flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}>
                    
                    {/* Avatar */}
                    <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center shrink-0 ${isUser ? 'bg-slate-800 text-white shadow-md' : 'bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow-md'}`}>
                      {isUser ? <User size={18} /> : <Sparkles size={18} />}
                    </div>

                    {/* Content */}
                    <div className={`flex-1 flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[85%] sm:max-w-[80%]`}>
                      <div className={`flex items-center gap-2 mb-1.5 ${isUser ? 'flex-row-reverse' : ''}`}>
                        <span className="text-xs font-semibold text-slate-700">{isUser ? "工程师 (You)" : "Agent Copilot"}</span>
                        <span className="text-[10px] text-slate-400">{formatDate(message.created_at)}</span>
                      </div>
                      
                      <div className={`p-4 sm:p-5 rounded-2xl text-sm leading-relaxed shadow-sm ${
                        isUser 
                          ? 'bg-slate-800 text-white rounded-tr-sm' 
                          : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm'
                      }`}>
                        <div className="whitespace-pre-wrap">{message.content}</div>
                        
                        {/* Citations Panel */}
                        {!isUser && message.citations && message.citations.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-slate-100 flex flex-col gap-2">
                            <details className="group cursor-pointer">
                              <summary className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 hover:text-emerald-700 outline-none select-none">
                                <BookOpen size={14} /> 
                                参考了 {message.citations.length} 个知识切片
                                <ChevronRight size={14} className="transition-transform group-open:rotate-90 ml-auto text-slate-400" />
                              </summary>
                              <div className="mt-3 grid grid-cols-1 gap-2 cursor-auto">
                                {message.citations.map((citation, idx) => (
                                  <div key={citation.chunk_id || idx} className="p-3 bg-slate-50 border border-slate-200 rounded-xl hover:border-emerald-200 transition-colors">
                                    <div className="flex items-start justify-between gap-2 mb-1">
                                      <strong className="text-xs text-slate-800 truncate">{citation.title || "未知文档"}</strong>
                                      <span className="text-[10px] bg-white border border-slate-200 px-1.5 py-0.5 rounded text-slate-500 shrink-0">匹配度 {(citation.score * 100).toFixed(1)}%</span>
                                    </div>
                                    <p className="text-xs text-slate-500 line-clamp-2 mt-1">{citation.summary}</p>
                                    {citation.source_path && (
                                      <div className="flex items-center gap-1 mt-2 text-[10px] text-slate-400 font-mono bg-white px-2 py-1 rounded w-fit border border-slate-100">
                                        <FileText size={10} /> {citation.source_path.split('/').pop()}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </details>
                            
                            {/* Run Info Metadata */}
                            {typeof message.message_metadata?.run_id === "string" && (
                              <div className="mt-1 flex items-center gap-1 text-[10px] text-slate-400">
                                <History size={12} />
                                溯源 ID: <Link to={`/runs/${message.message_metadata.run_id}`} className="hover:text-emerald-600 underline decoration-slate-300 underline-offset-2">{message.message_metadata.run_id.substring(0, 8)}...</Link>
                              </div>
                            )}
                          </div>
                        )}

                        {!isUser && message.citations && message.citations.length === 0 && (
                          <div className="mt-3 pt-3 border-t border-slate-100">
                            <span className="text-[10px] text-slate-400 flex items-center gap-1">
                              <CheckCircle2 size={12} />
                              {message.knowledge_mode === "disabled" ? "基于本地规则链路生成 (RAG未启用)" : "基于当前案例上下文直接作答"}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                  </div>
                );
              })}

              {pendingRunId && (
                <div className="flex gap-4">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow-md flex items-center justify-center shrink-0">
                    <Sparkles size={18} className="animate-pulse" />
                  </div>
                  <div className="flex-1 max-w-[85%] sm:max-w-[80%] flex flex-col items-start">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-xs font-semibold text-slate-700">Agent Copilot</span>
                    </div>
                    <div className="p-4 sm:p-5 bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm flex items-center gap-3">
                      <span className="loading-spinner border-emerald-500 border-t-transparent" />
                      <span className="text-sm text-slate-500 animate-pulse">正在深度思考与检索知识库...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 sm:p-6 bg-white border-t border-slate-100 shrink-0">
          <div className="max-w-4xl mx-auto relative group">
            <textarea
              className="w-full bg-slate-50 border border-slate-200 rounded-2xl pl-5 pr-14 py-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 shadow-sm resize-none transition-all"
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleSubmit();
                }
              }}
              disabled={isSubmitting}
              placeholder="向智能体提问，例如：总结故障现象、寻找同类案例、生成排查步骤 (Enter 发送，Shift+Enter 换行)..."
            />
            <button 
              className="absolute right-3 bottom-3 p-2.5 bg-slate-800 text-white rounded-xl hover:bg-emerald-600 disabled:bg-slate-200 disabled:text-slate-400 transition-colors shadow-sm disabled:shadow-none"
              type="button" 
              onClick={handleSubmit} 
              disabled={isSubmitting || !question.trim()}
            >
              <Send size={18} className={isSubmitting ? "opacity-0" : "opacity-100"} />
              {isSubmitting && <span className="absolute inset-0 flex items-center justify-center"><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"/></span>}
            </button>
          </div>
          <div className="max-w-4xl mx-auto mt-2 text-center">
            <span className="text-[10px] text-slate-400">系统生成的建议仅供辅助参考，请结合实际工况与专业判断执行维护操作。</span>
          </div>
        </div>

      </div>
    </div>
  );
}
