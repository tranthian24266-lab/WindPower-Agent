import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { MetricGrid } from "../components/MetricGrid";
import { PageHeader } from "../components/PageHeader";
import { RiskBadge } from "../components/RiskBadge";
import { StatusBanner } from "../components/StatusBanner";
import { generateReport, getApiErrorMessage, getCase } from "../lib/api";
import { formatDate, taskTypeLabel } from "../lib/format";
import type { CaseDetail } from "../types";

const ResultChart = lazy(() => import("../components/ResultChart").then((module) => ({ default: module.ResultChart })));

function diagnosisLabel(value: unknown): string {
  if (value === "healthy") {
    return "健康";
  }
  if (value === "damaged") {
    return "受损";
  }
  return String(value ?? "--");
}

function buildCaseSummary(caseDetail: CaseDetail) {
  const result = caseDetail.result;
  if (caseDetail.task_type === "fault_diagnosis") {
    const preprocess = result.preprocess as Record<string, unknown> | undefined;
    return `本次共处理 ${String(preprocess?.num_windows ?? "--")} 个窗口，预测结果为 ${diagnosisLabel(result.prediction)}。`;
  }
  if (caseDetail.task_type === "rul_prediction") {
    return `当前展示的剩余寿命为 ${String(result.rul_clipped ?? "--")} ${String(result.rul_unit ?? "")}`.trim();
  }
  return `共检测到 ${String(result.num_anomalies ?? "--")} 个异常样本，总样本数为 ${String(
    result.num_samples ?? "--",
  )}。`;
}

function buildMetrics(caseDetail: CaseDetail) {
  const result = caseDetail.result;
  if (caseDetail.task_type === "fault_diagnosis") {
    return [
      { label: "预测结果", value: diagnosisLabel(result.prediction) },
      { label: "置信度", value: result.confidence },
      { label: "健康概率", value: (result.class_probabilities as Record<string, unknown> | undefined)?.healthy },
      { label: "受损概率", value: (result.class_probabilities as Record<string, unknown> | undefined)?.damaged },
    ];
  }

  if (caseDetail.task_type === "rul_prediction") {
    return [
      { label: "原始 RUL", value: result.rul_raw },
      { label: "展示 RUL", value: result.rul_clipped },
      { label: "单位", value: result.rul_unit },
      { label: "特征数量", value: Object.keys((result.features as Record<string, unknown>) || {}).length },
    ];
  }

  return [
    { label: "阈值", value: result.threshold },
    { label: "样本数", value: result.num_samples },
    { label: "异常数", value: result.num_anomalies },
    { label: "异常比例", value: result.anomaly_ratio },
  ];
}

export function CaseDetailPage() {
  const { caseId = "" } = useParams();
  const navigate = useNavigate();
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    getCase(caseId)
      .then(setCaseDetail)
      .catch((caught: unknown) => {
        setError(getApiErrorMessage(caught, "加载案例详情失败。"));
      });
  }, [caseId]);

  const metrics = useMemo(() => (caseDetail ? buildMetrics(caseDetail) : []), [caseDetail]);

  async function handleGenerateReport() {
    if (!caseDetail) {
      return;
    }
    setGenerating(true);
    try {
      await generateReport(caseDetail.case_id);
      navigate(`/reports/${caseDetail.case_id}`);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "生成报告失败。"));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="案例详情"
        title="案例详情"
        action={
          caseDetail ? (
            <div className="button-row">
              <button className="action-button" type="button" disabled={generating} onClick={handleGenerateReport}>
                {generating ? "生成中..." : "生成报告"}
              </button>
              <Link className="ghost-button" to={`/chat?caseId=${caseDetail.case_id}`}>
                打开问答
              </Link>
              <Link className="ghost-button" to="/cases">
                返回案例列表
              </Link>
            </div>
          ) : null
        }
      />
      {error ? <StatusBanner variant="error" message={error} /> : null}
      {caseDetail ? (
        <>
          <section className="panel-grid two-up">
            <article className="content-panel">
              <div className="section-head">
                <h3>案例概览</h3>
                <RiskBadge value={caseDetail.risk_level} />
              </div>
              <dl className="meta-grid">
                <div>
                  <dt>案例 ID</dt>
                  <dd>{caseDetail.case_id}</dd>
                </div>
                <div>
                  <dt>任务类型</dt>
                  <dd>{taskTypeLabel(caseDetail.task_type)}</dd>
                </div>
                <div>
                  <dt>模型</dt>
                  <dd>{caseDetail.model_name || caseDetail.model_id}</dd>
                </div>
                <div>
                  <dt>文件</dt>
                  <dd>{caseDetail.original_filename || "--"}</dd>
                </div>
                <div>
                  <dt>创建时间</dt>
                  <dd>{formatDate(caseDetail.created_at)}</dd>
                </div>
              </dl>
              <p className="inline-note">{buildCaseSummary(caseDetail)}</p>
            </article>
            <article className="content-panel">
              <div className="section-head">
                <h3>路由追踪</h3>
              </div>
              <dl className="meta-grid">
                <div>
                  <dt>Model Version ID</dt>
                  <dd>{caseDetail.model_version_id || "--"}</dd>
                </div>
                <div>
                  <dt>Model Alias</dt>
                  <dd>{caseDetail.model_alias || "--"}</dd>
                </div>
                <div>
                  <dt>选择原因</dt>
                  <dd>{caseDetail.selection_reason || "--"}</dd>
                </div>
              </dl>
            </article>
          </section>

          <section className="content-panel">
            <div className="section-head">
              <h3>结果图示</h3>
            </div>
            <Suspense fallback={<StatusBanner message="图表加载中..." />}>
              <ResultChart taskType={caseDetail.task_type} result={caseDetail.result} />
            </Suspense>
          </section>

          <MetricGrid items={metrics} />

          <section className="content-panel">
            <div className="section-head">
              <h3>原始结果 JSON</h3>
              <Link to={`/reports/${caseDetail.case_id}`}>打开报告中心</Link>
            </div>
            <pre className="json-panel">{JSON.stringify(caseDetail.result, null, 2)}</pre>
          </section>
        </>
      ) : (
        <StatusBanner message="案例详情加载中..." />
      )}
    </div>
  );
}
