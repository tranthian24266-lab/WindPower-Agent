import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, UploadCloud, Settings2, Play, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { diagnose, getApiErrorMessage, uploadFile } from "../lib/api";
import type { TaskType } from "../types";

const taskOptions: Array<{
  value: TaskType;
  label: string;
  desc: string;
  icon: React.ReactNode;
  format: string;
  output: string;
}> = [
  {
    value: "fault_diagnosis",
    label: "故障诊断",
    desc: "判断齿轮箱当前更接近健康还是受损状态。",
    icon: <Activity size={24} />,
    format: ".csv 振动数据",
    output: "健康/故障概率与受损定位",
  },
  {
    value: "rul_prediction",
    label: "RUL 预测",
    desc: "估计剩余可用寿命，辅助维护决策。",
    icon: <Activity size={24} />,
    format: ".mat 振动/运行数据",
    output: "预测寿命天数与置信区间",
  },
  {
    value: "anomaly_detection",
    label: "异常检测",
    desc: "评估设备整体异常比例和运行风险。",
    icon: <Activity size={24} />,
    format: ".npy/.npz SCADA 数据",
    output: "异常得分与越限点分布",
  },
];

export function DiagnosisPage() {
  const navigate = useNavigate();
  const [taskType, setTaskType] = useState<TaskType>("fault_diagnosis");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [preferredAlias, setPreferredAlias] = useState("");
  const [preferredModelId, setPreferredModelId] = useState("");

  const selectedOption = useMemo(() => taskOptions.find((item) => item.value === taskType), [taskType]);

  async function handleRun() {
    if (!selectedFile) {
      setError("请先选择一个样本文件。");
      return;
    }

    setRunning(true);
    setError(null);
    setStatus("正在上传样本文件...");
    try {
      const fileInfo = await uploadFile(selectedFile);
      setStatus("文件上传成功，正在调度智能体进行诊断...");
      const diagnosis = await diagnose(fileInfo.file_id, taskType, {
        preferredAlias: preferredAlias.trim() || undefined,
        preferredModelId: preferredModelId.trim() || undefined,
      });
      setStatus("诊断已完成，正在打开结果工作台...");
      setTimeout(() => {
        navigate(`/cases/${diagnosis.case_id}`);
      }, 500);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "诊断失败。"));
      setStatus("");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="page-stack max-w-5xl">
      <PageHeader
        variant="workspace"
        eyebrow="诊断工作台"
        title="诊断任务"
        description="选择需要执行的分析任务并上传设备样本数据，系统将自动路由至最佳模型并输出诊断依据。"
      />
      {error ? <StatusBanner variant="error" message={error} /> : null}

      <div className="flex flex-col gap-6">
        <article className="content-panel flex flex-col">
          <div className="section-head mb-4 border-b border-slate-100 pb-4">
            <h3 className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm font-bold">
                1
              </span>
              选择诊断任务
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {taskOptions.map((item) => (
              <button
                key={item.value}
                className={`choice-card flex flex-col gap-3 relative ${taskType === item.value ? " selected" : ""}`}
                onClick={() => setTaskType(item.value)}
                type="button"
              >
                {taskType === item.value ? (
                  <div className="absolute top-0 left-0 w-full h-1 bg-emerald-500 rounded-t-xl" />
                ) : null}
                <div className="flex items-center gap-3 mt-1">
                  <div className={taskType === item.value ? "text-emerald-600" : "text-slate-400"}>{item.icon}</div>
                  <strong className="text-lg">{item.label}</strong>
                </div>
                <p className="text-sm text-slate-500 leading-relaxed min-h-[40px]">{item.desc}</p>
                <div className="mt-auto pt-3 border-t border-slate-100 flex flex-col gap-1 text-xs">
                  <span className="text-slate-500">
                    <strong>输入：</strong> {item.format}
                  </span>
                  <span className="text-slate-500">
                    <strong>输出：</strong> {item.output}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </article>

        <article className="content-panel flex flex-col">
          <div className="section-head mb-4 border-b border-slate-100 pb-4">
            <h3 className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm font-bold">
                2
              </span>
              上传样本文件
            </h3>
          </div>
          <label
            className={`upload-zone flex flex-col items-center justify-center py-12 transition-all ${
              selectedFile ? "border-emerald-500 bg-emerald-50/50" : "hover:border-emerald-400 hover:bg-emerald-50/30"
            }`}
          >
            <input
              type="file"
              accept=".csv,.mat,.npy,.npz"
              onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
            />
            {selectedFile ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mb-2">
                  <CheckCircle2 size={32} />
                </div>
                <span className="text-lg font-medium text-emerald-800">{selectedFile.name}</span>
                <span className="text-sm text-emerald-600/80">已准备好执行 {selectedOption?.label}</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-slate-400">
                <UploadCloud size={48} strokeWidth={1.5} />
                <span className="text-base text-slate-600 mt-2">点击或拖拽上传样本文件</span>
                <span className="text-sm">支持 {selectedOption?.format}</span>
              </div>
            )}
          </label>
        </article>

        <article className="content-panel flex flex-col bg-slate-50/50">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex-1 w-full">
              {status ? (
                <div className="flex items-center gap-3 text-emerald-700 font-medium">
                  {running ? <span className="loading-spinner border-emerald-500 border-t-transparent" /> : null}
                  {status}
                </div>
              ) : null}
            </div>

            <div className="flex items-center gap-4 w-full sm:w-auto">
              <button className="ghost-button flex items-center gap-2" type="button" onClick={() => setShowAdvanced(!showAdvanced)}>
                <Settings2 size={16} />
                专家路由控制
                {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              <button className="action-button px-8" type="button" disabled={running || !selectedFile} onClick={handleRun}>
                <Play size={18} />
                {running ? "诊断执行中..." : "开始智能诊断"}
              </button>
            </div>
          </div>

          {showAdvanced ? (
            <div className="mt-6 p-5 bg-white border border-slate-200 rounded-xl">
              <div className="mb-4">
                <h4 className="font-medium text-slate-800 flex items-center gap-2">
                  <Settings2 size={16} className="text-slate-500" /> 专家路由偏好
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  此选项用于强制指定诊断模型路由，通常用于模型 A/B 测试或调试，非必填。
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <label className="flex flex-col gap-2">
                  <span className="text-sm font-medium text-slate-700">优先模型别名 (Alias)</span>
                  <input
                    className="px-3 py-2 border border-slate-200 rounded-lg text-sm bg-slate-50 focus:bg-white focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all"
                    value={preferredAlias}
                    onChange={(event) => setPreferredAlias(event.target.value)}
                    placeholder="例如: champion, canary"
                    type="text"
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <span className="text-sm font-medium text-slate-700">显式模型 ID (Legacy)</span>
                  <input
                    className="px-3 py-2 border border-slate-200 rounded-lg text-sm bg-slate-50 focus:bg-white focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all"
                    value={preferredModelId}
                    onChange={(event) => setPreferredModelId(event.target.value)}
                    placeholder="可选: model_abc123"
                    type="text"
                  />
                </label>
              </div>
            </div>
          ) : null}
        </article>
      </div>
    </div>
  );
}
