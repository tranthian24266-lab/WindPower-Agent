import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { RiskBadge } from "../components/RiskBadge";
import { StatusBanner } from "../components/StatusBanner";
import { getCases } from "../lib/api";
import { formatDate, taskTypeLabel } from "../lib/format";
import type { CaseSummary } from "../types";

export function CasesPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [taskType, setTaskType] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCases({ taskType, riskLevel })
      .then(setCases)
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "历史案例加载失败");
      });
  }, [taskType, riskLevel]);

  return (
    <div className="page-stack">
      <PageHeader eyebrow="历史案例" title="可回溯的诊断案例" />
      {error ? <StatusBanner variant="error" message={error} /> : null}
      <section className="content-panel">
        <div className="filters-row">
          <select value={taskType} onChange={(event) => setTaskType(event.target.value)}>
            <option value="">全部任务</option>
            <option value="fault_diagnosis">故障诊断</option>
            <option value="rul_prediction">故障预测</option>
            <option value="anomaly_detection">健康状态检测</option>
          </select>
          <select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)}>
            <option value="">全部风险等级</option>
            <option value="normal">正常</option>
            <option value="warning">需关注</option>
            <option value="critical">高风险</option>
          </select>
        </div>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>案例编号</th>
                <th>任务</th>
                <th>文件</th>
                <th>时间</th>
                <th>风险</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((item) => (
                <tr key={item.case_id}>
                  <td className="table-cell-break">
                    <Link className="table-link" to={`/cases/${item.case_id}`}>
                      {item.case_id}
                    </Link>
                  </td>
                  <td>{taskTypeLabel(item.task_type)}</td>
                  <td className="table-cell-break">{item.original_filename || "--"}</td>
                  <td>{formatDate(item.created_at)}</td>
                  <td>
                    <RiskBadge value={item.risk_level} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
