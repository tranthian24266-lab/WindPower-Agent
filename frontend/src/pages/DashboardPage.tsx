import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Box, FileText, AlertTriangle, Play, Database, Shield } from "lucide-react";

import { MetricGrid } from "../components/MetricGrid";
import { PageHeader } from "../components/PageHeader";
import { RiskBadge } from "../components/RiskBadge";
import { StatusBanner } from "../components/StatusBanner";
import { getCases, getModels } from "../lib/api";
import { formatDate, modelNameZh, modelSummaryZh, taskTypeLabel } from "../lib/format";
import type { CaseSummary, ModelSummary } from "../types";

export function DashboardPage() {
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getModels(), getCases()])
      .then(([nextModels, nextCases]) => {
        setModels(nextModels);
        setCases(nextCases);
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "加载总览页面失败");
      });
  }, []);

  const todayCasesCount = cases.slice(0, 10).length;
  const onlineModelsCount = models.length;
  const faultModelsCount = models.filter((item) => item.task_type === "fault_diagnosis").length;
  const anomalyModelsCount = models.filter((item) => item.task_type === "anomaly_detection").length;

  return (
    <div className="page-stack">
      <PageHeader
        variant="overview"
        eyebrow={"平台总览"}
        title={"风电智能诊断平台"}
        description={"统一调度诊断、问答与模型能力，让风电诊断从静态报告升级到实时决策流。"}
        action={
          <div className="flex gap-4">
            <Link className="action-button" to="/diagnosis">
              <Play size={18} /> {"开始诊断"}
            </Link>
            <Link className="ghost-button" to="/models">
              {"打开模型库"}
            </Link>
          </div>
        }
      />
      {error ? <StatusBanner variant="error" message={error} /> : null}

      <MetricGrid
        items={[
          {
            label: "历史处理案例数",
            value: cases.length,
            variant: "large",
            icon: <Activity size={32} />,
            trend: { value: `${todayCasesCount} 今日新增`, isUp: true, isGood: true },
          },
          { label: "在线诊断模型", value: onlineModelsCount, icon: <Box size={20} /> },
          { label: "故障分类模型", value: faultModelsCount, icon: <AlertTriangle size={20} /> },
          { label: "异常检测模型", value: anomalyModelsCount, icon: <Activity size={20} /> },
        ]}
      />

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <article className="content-panel flex flex-col">
          <div className="section-head">
            <div>
              <h3>{"模型库"}</h3>
              <p className="text-sm text-slate-500 mt-1">{"当前部署的可用诊断模型"}</p>
            </div>
            <Link to="/models" className="text-sm text-emerald-600 font-medium hover:underline">
              {"查看全部"}
            </Link>
          </div>
          <div className="stack-list flex-1">
            {models.map((model) => (
              <div key={model.model_id} className="list-card flex items-start gap-4">
                <div className="mt-1 p-2 bg-emerald-50 rounded-lg text-emerald-600">
                  {model.task_type === "fault_diagnosis" ? <AlertTriangle size={20} /> : <Activity size={20} />}
                </div>
                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <strong className="text-base">{modelNameZh(model.model_id, model.model_name)}</strong>
                    <span className="pill">{taskTypeLabel(model.task_type)}</span>
                  </div>
                  <p className="mt-2">{modelSummaryZh(model)}</p>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="content-panel flex flex-col">
          <div className="section-head">
            <div>
              <h3>{"诊断案例"}</h3>
              <p className="text-sm text-slate-500 mt-1">{"最近处理的风电样本案例"}</p>
            </div>
            <Link to="/cases" className="text-sm text-emerald-600 font-medium hover:underline">
              {"查看历史"}
            </Link>
          </div>
          <div className="stack-list flex-1">
            {cases.slice(0, 5).map((item) => (
              <Link
                key={item.case_id}
                className="list-card subtle-link flex items-center justify-between"
                to={`/cases/${item.case_id}`}
              >
                <div className="flex items-center gap-3">
                  <div className="text-slate-400">
                    <FileText size={18} />
                  </div>
                  <div>
                    <strong className="block text-sm">{item.original_filename || item.case_id}</strong>
                    <span className="text-xs text-slate-500">{formatDate(item.created_at)}</span>
                  </div>
                </div>
                <RiskBadge value={item.risk_level} />
              </Link>
            ))}
          </div>
        </article>
      </section>

      <section className="content-panel">
        <h3 className="text-lg font-semibold mb-4">{"快捷工作台"}</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Link
            to="/diagnosis"
            className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 hover:border-emerald-400 hover:shadow-md transition-all bg-white"
          >
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <Play size={20} />
            </div>
            <span className="font-medium text-slate-700">{"新建诊断"}</span>
          </Link>
          <Link
            to="/chat"
            className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 hover:border-emerald-400 hover:shadow-md transition-all bg-white"
          >
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <FileText size={20} />
            </div>
            <span className="font-medium text-slate-700">{"打开问答"}</span>
          </Link>
          <Link
            to="/knowledge"
            className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 hover:border-emerald-400 hover:shadow-md transition-all bg-white"
          >
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <Database size={20} />
            </div>
            <span className="font-medium text-slate-700">{"查看知识库"}</span>
          </Link>
          <Link
            to="/reviews"
            className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 hover:border-emerald-400 hover:shadow-md transition-all bg-white"
          >
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <Shield size={20} />
            </div>
            <span className="font-medium text-slate-700">{"审核队列"}</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
