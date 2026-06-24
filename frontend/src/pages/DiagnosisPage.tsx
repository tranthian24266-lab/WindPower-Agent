import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Play,
  Settings2,
  UploadCloud,
} from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { BatchDiagnosisPanel } from "../components/BatchDiagnosisPanel";
import { StatusBanner } from "../components/StatusBanner";
import { autoDiagnose, diagnose, getApiErrorMessage, uploadFile } from "../lib/api";
import { taskTypeLabel } from "../lib/format";
import type { AutoDiagnoseResponse, AutoDiagnosisRouting, TaskType } from "../types";

const taskOptions: Array<{ value: TaskType; label: string; desc: string; format: string }> = [
  { value: "fault_diagnosis", label: "故障诊断", desc: "判断齿轮箱当前更接近健康还是受损状态。", format: ".npy/.npz/.mat/.csv" },
  { value: "rul_prediction", label: "故障预测", desc: "估计剩余可用寿命与退化趋势。", format: ".mat" },
  { value: "anomaly_detection", label: "健康状态检测", desc: "评估设备整体健康状态和运行风险。", format: ".csv" },
];

export function DiagnosisPage() {
  const navigate = useNavigate();
  const [manualMode, setManualMode] = useState(false);
  const [taskType, setTaskType] = useState<TaskType>("fault_diagnosis");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedFileId, setUploadedFileId] = useState("");
  const [routing, setRouting] = useState<AutoDiagnosisRouting | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [preferredAlias, setPreferredAlias] = useState("");
  const [preferredModelId, setPreferredModelId] = useState("");

  const routeOptions = {
    preferredAlias: preferredAlias.trim() || undefined,
    preferredModelId: preferredModelId.trim() || undefined,
  };

  function openCompletedDiagnosis(response: AutoDiagnoseResponse) {
    if (!("case_id" in response)) {
      setRouting(response.routing);
      setStatus(
        response.status === "needs_confirmation"
          ? "智能体发现多个可能的任务，请确认后继续。"
          : "当前数据与已有模型输入契约不匹配。",
      );
      return;
    }
    setRouting(response.routing);
    setStatus("智能体已完成模型选择和诊断，正在打开结果工作台...");
    setTimeout(() => navigate(`/cases/${response.case_id}`), 400);
  }

  async function handleRun() {
    if (!selectedFile) {
      setError("请先选择一个样本文件。");
      return;
    }
    setRunning(true);
    setError(null);
    setRouting(null);
    setStatus("正在上传并分析样本文件...");
    try {
      const fileInfo = await uploadFile(selectedFile);
      setUploadedFileId(fileInfo.file_id);
      if (manualMode) {
        setStatus(`正在使用${taskTypeLabel(taskType)}模型执行诊断...`);
        const result = await diagnose(fileInfo.file_id, taskType, routeOptions);
        setTimeout(() => navigate(`/cases/${result.case_id}`), 400);
        return;
      }
      setStatus("智能体正在识别任务类型并选择目标模型...");
      openCompletedDiagnosis(await autoDiagnose(fileInfo.file_id, undefined, routeOptions));
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "智能诊断失败。"));
      setStatus("");
    } finally {
      setRunning(false);
    }
  }

  async function handleConfirmTask(confirmedTaskType: TaskType) {
    if (!uploadedFileId) return;
    setRunning(true);
    setError(null);
    setStatus(`已确认${taskTypeLabel(confirmedTaskType)}，正在执行目标模型...`);
    try {
      openCompletedDiagnosis(await autoDiagnose(uploadedFileId, confirmedTaskType, routeOptions));
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "确认任务后诊断失败。"));
      setStatus("");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="page-stack max-w-5xl">
      <PageHeader
        variant="workspace"
        eyebrow="轻量诊断智能体"
        title="智能检测"
        description="上传设备数据后，智能体将分析输入结构、自动选择小模型并完成诊断；模糊数据会先请求确认。"
      />
      {error ? <StatusBanner variant="error" message={error} /> : null}

      <article className="content-panel flex flex-col gap-5">
        <div className="section-head">
          <div>
            <h3 className="flex items-center gap-2"><Bot size={20} className="text-emerald-600" />智能体工作模式</h3>
            <p className="helper-copy">默认采用可解释的输入契约匹配，不使用大模型猜测任务类型。</p>
          </div>
          <button className="ghost-button" type="button" onClick={() => setManualMode((value) => !value)}>
            <Settings2 size={16} />
            {manualMode ? "返回智能模式" : "切换到手动模式"}
          </button>
        </div>

        {manualMode ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {taskOptions.map((item) => (
              <button
                key={item.value}
                className={`choice-card flex flex-col gap-3 ${taskType === item.value ? " selected" : ""}`}
                onClick={() => setTaskType(item.value)}
                type="button"
              >
                <div className="flex items-center gap-3"><Activity size={22} /><strong>{item.label}</strong></div>
                <p className="text-sm text-slate-500">{item.desc}</p>
                <span className="text-xs text-slate-500">输入：{item.format}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {["分析文件格式与数据结构", "计算三类任务匹配分数", "选择模型并自动执行诊断"].map((item, index) => (
              <div className="preview-card" key={item}>
                <span className="metric-label">步骤 {index + 1}</span>
                <strong className="text-sm">{item}</strong>
              </div>
            ))}
          </div>
        )}
      </article>

      <article className="content-panel flex flex-col gap-4">
        <div className="section-head"><h3>上传检测数据</h3><span className="pill">.csv / .mat / .npy / .npz</span></div>
        <label htmlFor="diagnosis-file-upload" className={`upload-zone flex flex-col items-center justify-center py-12 ${selectedFile ? "border-emerald-500 bg-emerald-50/50" : ""}`}>
          <input
            id="diagnosis-file-upload"
            type="file"
            accept=".csv,.mat,.npy,.npz"
            onClick={(event) => {
              (event.target as HTMLInputElement).value = "";
            }}
            onChange={(event) => {
              setSelectedFile(event.target.files?.[0] || null);
              setRouting(null);
              setUploadedFileId("");
            }}
          />
          {selectedFile ? (
            <div className="flex flex-col items-center gap-2 text-emerald-700"><CheckCircle2 size={36} /><strong>{selectedFile.name}</strong><span className="text-sm">已准备好执行{manualMode ? "手动" : "智能"}诊断</span></div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-slate-400"><UploadCloud size={46} /><span className="text-slate-600">点击或拖拽上传样本文件</span></div>
          )}
        </label>
      </article>

      {routing ? (
        <article className="content-panel flex flex-col gap-4">
          <div className="section-head">
            <div><h3>智能体路由判断</h3><p className="helper-copy">置信度 {(routing.confidence * 100).toFixed(0)}%</p></div>
            <span className="pill">{routing.status}</span>
          </div>
          {routing.evidence.length > 0 ? <ul className="text-sm text-slate-600 list-disc pl-5">{routing.evidence.map((item) => <li key={item}>{item}</li>)}</ul> : null}
          {routing.status === "needs_confirmation" ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {routing.candidates.map((candidate) => (
                <div className="preview-card" key={candidate.task_type}>
                  <strong>{taskTypeLabel(candidate.task_type)}</strong>
                  <span className="helper-copy">匹配度 {(candidate.score * 100).toFixed(0)}%</span>
                  <button className="ghost-button" type="button" disabled={running} onClick={() => handleConfirmTask(candidate.task_type)}>确认使用此任务</button>
                </div>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}

      <article className="content-panel bg-slate-50/50">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>{status ? <div className="flex items-center gap-3 text-emerald-700 font-medium">{running ? <span className="loading-spinner border-emerald-500 border-t-transparent" /> : null}{status}</div> : null}</div>
          <div className="flex gap-3">
            <button className="ghost-button" type="button" onClick={() => setShowAdvanced((value) => !value)}><Settings2 size={16} />专家路由控制{showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</button>
            <button className="action-button px-8" type="button" disabled={running || !selectedFile} onClick={handleRun}><Play size={18} />{running ? "执行中..." : manualMode ? "开始手动诊断" : "开始智能诊断"}</button>
          </div>
        </div>
        {showAdvanced ? (
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm" value={preferredAlias} onChange={(event) => setPreferredAlias(event.target.value)} placeholder="优先模型别名，例如 champion" />
            <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm" value={preferredModelId} onChange={(event) => setPreferredModelId(event.target.value)} placeholder="显式模型 ID（调试用）" />
          </div>
        ) : null}
      </article>
      <BatchDiagnosisPanel />
    </div>
  );
}
