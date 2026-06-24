import { useState } from "react";
import { Boxes, ExternalLink, UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { batchDiagnose, getApiErrorMessage } from "../lib/api";
import { taskTypeLabel } from "../lib/format";
import type { BatchDiagnoseResponse } from "../types";
import { StatusBanner } from "./StatusBanner";


export function BatchDiagnosisPanel() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<BatchDiagnoseResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runBatch() {
    if (!files.length) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      setResult(await batchDiagnose(files));
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "批量智能检测失败。"));
    } finally {
      setRunning(false);
    }
  }

  return (
    <article className="content-panel flex flex-col gap-4">
      <div className="section-head">
        <div>
          <h3 className="flex items-center gap-2"><Boxes size={20} />批量智能检测</h3>
          <p className="helper-copy">一次上传最多 50 个文件，每个文件独立识别任务、调用模型并保存 Agent 时间线。</p>
        </div>
        <span className="pill">逐文件自动路由</span>
      </div>
      {error ? <StatusBanner variant="error" message={error} /> : null}
      <label className="upload-zone flex flex-col items-center justify-center py-8">
        <input
          type="file"
          multiple
          accept=".csv,.mat,.npy,.npz"
          onChange={(event) => setFiles(Array.from(event.target.files || []))}
        />
        <UploadCloud size={36} className="text-emerald-600" />
        <strong>{files.length ? `已选择 ${files.length} 个文件` : "选择或拖拽多个检测文件"}</strong>
      </label>
      <button className="action-button self-end" type="button" disabled={running || !files.length} onClick={runBatch}>
        {running ? "批量检测中..." : "开始批量智能检测"}
      </button>

      {result ? (
        <div className="flex flex-col gap-3">
          <StatusBanner
            variant={result.failed ? "error" : "success"}
            message={`共 ${result.total} 个：成功 ${result.succeeded}，待确认 ${result.needs_confirmation}，失败 ${result.failed}`}
          />
          {result.items.map((item, index) => (
            <div className="list-card" key={`${item.filename}-${index}`}>
              <div className="section-head">
                <div>
                  <strong>{item.filename}</strong>
                  <p className="helper-copy">
                    {item.task_type ? taskTypeLabel(item.task_type) : "未识别任务"}
                    {item.model_id ? ` · ${item.model_id}` : ""}
                  </p>
                </div>
                <span className="pill">{item.status}</span>
              </div>
              {item.error ? <p className="text-sm text-rose-600">{item.error.message}</p> : null}
              <div className="flex flex-wrap gap-2 mt-2">
                {item.case_id ? (
                  <button className="ghost-button" type="button" onClick={() => navigate(`/cases/${item.case_id}`)}>
                    <ExternalLink size={14} />查看诊断案例
                  </button>
                ) : null}
                {item.run_id ? (
                  <button className="ghost-button" type="button" onClick={() => navigate(`/runs/${item.run_id}`)}>
                    <ExternalLink size={14} />查看 Agent 时间线
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}
