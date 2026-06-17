import { useEffect, useMemo, useState } from "react";
import { Search, Box, CheckCircle2, ShieldCheck, RefreshCw } from "lucide-react";

import { MetricGrid } from "../components/MetricGrid";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  getApiErrorMessage,
  getModelCatalogModel,
  getModelCatalogModels,
  getModelCatalogVersions,
  syncModelCatalog,
} from "../lib/api";
import {
  catalogDescriptionZh,
  formatDate,
  modelStatusLabel,
  shortModelDisplayName,
  taskTypeLabel,
  validationStatusLabel,
} from "../lib/format";
import type { CatalogModelDetail, CatalogModelListItem, CatalogModelVersion } from "../types";

export function ModelLibraryPage() {
  const [items, setItems] = useState<CatalogModelListItem[]>([]);
  const [selectedFamilyId, setSelectedFamilyId] = useState("");
  const [detail, setDetail] = useState<CatalogModelDetail | null>(null);
  const [versions, setVersions] = useState<CatalogModelVersion[]>([]);
  const [query, setQuery] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [taskType, setTaskType] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getModelCatalogModels({
      q: query || undefined,
      taskType: taskType || undefined,
      page: 1,
      pageSize: 50,
      sortBy: "task_type",
      sortOrder: "asc",
    })
      .then((payload) => {
        setItems(payload.items);
        if (!selectedFamilyId || !payload.items.some((item) => item.family_id === selectedFamilyId)) {
          setSelectedFamilyId(payload.items[0]?.family_id || "");
        }
        setError(null);
      })
      .catch((caught: unknown) => {
        setError(getApiErrorMessage(caught, "加载模型库失败。"));
      })
      .finally(() => setLoading(false));
  }, [query, selectedFamilyId, taskType]);

  useEffect(() => {
    if (!selectedFamilyId) {
      setDetail(null);
      setVersions([]);
      return;
    }

    Promise.all([getModelCatalogModel(selectedFamilyId), getModelCatalogVersions(selectedFamilyId)])
      .then(([nextDetail, nextVersions]) => {
        setDetail(nextDetail);
        setVersions(nextVersions);
        setError(null);
      })
      .catch((caught: unknown) => {
        setError(getApiErrorMessage(caught, "加载模型详情失败。"));
      });
  }, [selectedFamilyId]);

  const productionCount = useMemo(
    () => items.filter((item) => item.latest_version.status === "production").length,
    [items],
  );
  const pendingCount = useMemo(
    () => items.filter((item) => item.latest_version.validation_status === "pending").length,
    [items],
  );

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      const result = await syncModelCatalog();
      setNotice(result.summary);
      const refreshed = await getModelCatalogModels({
        q: query || undefined,
        taskType: taskType || undefined,
        page: 1,
        pageSize: 50,
        sortBy: "task_type",
        sortOrder: "asc",
      });
      setItems(refreshed.items);
      if (!selectedFamilyId || !refreshed.items.some((item) => item.family_id === selectedFamilyId)) {
        setSelectedFamilyId(refreshed.items[0]?.family_id || "");
      }
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "同步模型目录失败。"));
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="page-stack max-w-[1400px]">
      <PageHeader
        variant="workspace"
        eyebrow="模型资产中心"
        title="模型库"
        description="管理与维护平台内所有可用的诊断模型版本、验证状态及动态路由别名。"
        action={
          <button className="action-button" type="button" disabled={syncing} onClick={handleSync}>
            <RefreshCw size={18} />
            {syncing ? "同步中..." : "同步模型目录"}
          </button>
        }
      />

      {loading ? <StatusBanner message="模型库加载中..." /> : null}
      {notice ? <StatusBanner variant="success" message={notice} /> : null}
      {error ? <StatusBanner variant="error" message={error} /> : null}

      <MetricGrid
        items={[
          { label: "模型家族", value: items.length, variant: "large", icon: <Box size={32} /> },
          { label: "生产中版本", value: productionCount, icon: <CheckCircle2 size={20} /> },
          { label: "待验证模型", value: pendingCount, icon: <ShieldCheck size={20} /> },
          { label: "当前结果数", value: items.length, icon: <Box size={20} /> },
        ]}
      />

      <section className="content-panel py-4 px-6">
        <div className="flex flex-col lg:flex-row gap-4 items-center justify-between">
          <div className="flex-1 w-full max-w-lg relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input
              className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm bg-slate-50 focus:bg-white focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all"
              placeholder="搜索模型编码、名称或描述..."
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  setQuery(queryInput.trim());
                }
              }}
            />
          </div>
          <div className="flex gap-3 w-full lg:w-auto">
            <select
              className="px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white"
              value={taskType}
              onChange={(event) => setTaskType(event.target.value)}
            >
              <option value="">全部任务类型</option>
              <option value="fault_diagnosis">故障诊断</option>
              <option value="rul_prediction">RUL 预测</option>
              <option value="anomaly_detection">异常检测</option>
            </select>
            <button className="ghost-button" type="button" onClick={() => setQuery(queryInput.trim())}>
              搜索
            </button>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <article className="content-panel flex flex-col lg:col-span-4 p-0 overflow-hidden">
          <div className="section-head px-6 py-4 border-b border-slate-100 bg-slate-50/50 m-0">
            <div className="flex justify-between items-center w-full">
              <h3 className="text-base font-semibold text-slate-800 m-0">模型列表</h3>
              <span className="text-xs font-medium px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full">
                {items.length} 个结果
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-3 p-4 max-h-[780px] overflow-y-auto">
            {items.map((item) => (
              <button
                key={item.family_id}
                type="button"
                className={`text-left p-4 rounded-xl border transition-all ${
                  item.family_id === selectedFamilyId
                    ? "border-emerald-500 bg-emerald-50/20 shadow-sm"
                    : "border-slate-200 hover:border-emerald-300 hover:bg-slate-50"
                }`}
                onClick={() => setSelectedFamilyId(item.family_id)}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1 pr-2">
                    <strong className="text-sm text-slate-900 block truncate" title={shortModelDisplayName(item.display_name)}>
                      {shortModelDisplayName(item.display_name)}
                    </strong>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{item.family_code}</div>
                  </div>
                </div>

                <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed mb-3">
                  {catalogDescriptionZh({
                    familyCode: item.family_code,
                    taskType: item.task_type,
                    fallback: item.description,
                  })}
                </p>

                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] font-medium rounded">
                    {taskTypeLabel(item.task_type)}
                  </span>
                  <span
                    className={`px-2 py-0.5 text-[10px] font-medium rounded ${
                      item.latest_version.status === "production"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {modelStatusLabel(item.latest_version.status)}
                  </span>
                  <span
                    className={`px-2 py-0.5 text-[10px] font-medium rounded ${
                      item.latest_version.validation_status === "passed"
                        ? "bg-blue-100 text-blue-700"
                        : item.latest_version.validation_status === "failed"
                          ? "bg-rose-100 text-rose-700"
                          : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {validationStatusLabel(item.latest_version.validation_status)}
                  </span>
                </div>

                {item.aliases.length > 0 ? (
                  <div className="flex flex-wrap gap-1 mt-2 border-t border-slate-100 pt-2">
                    {item.aliases.map((alias) => (
                      <span
                        key={alias.alias_id}
                        className="px-1.5 py-0.5 bg-purple-50 text-purple-600 border border-purple-100 rounded text-[10px] font-medium"
                      >
                        {alias.alias_name}
                      </span>
                    ))}
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        </article>

        <article className="content-panel lg:col-span-8">
          {detail ? (
            <div className="flex flex-col gap-6">
              <div className="section-head">
                <div>
                  <h3>{shortModelDisplayName(detail.display_name)}</h3>
                  <p className="text-sm text-slate-500 mt-1">
                    {catalogDescriptionZh({
                      familyCode: detail.family_code,
                      taskType: detail.task_type,
                      fallback: detail.description,
                    })}
                  </p>
                </div>
                <span className="pill">{taskTypeLabel(detail.task_type)}</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="preview-card">
                  <span className="metric-label">家族编码</span>
                  <strong>{detail.family_code}</strong>
                </div>
                <div className="preview-card">
                  <span className="metric-label">版本数量</span>
                  <strong>{detail.versions_count}</strong>
                </div>
                <div className="preview-card">
                  <span className="metric-label">更新时间</span>
                  <strong>{formatDate(detail.updated_at)}</strong>
                </div>
              </div>

              <section className="content-panel">
                <div className="section-head">
                  <h3>版本列表</h3>
                  <span className="helper-copy">{versions.length} 个版本</span>
                </div>
                <div className="stack-list">
                  {versions.map((version) => (
                    <div key={version.model_version_id} className="list-card">
                      <div className="section-head">
                        <div>
                          <strong>{version.version}</strong>
                          <p className="helper-copy">{version.legacy_model_id}</p>
                        </div>
                        <div className="flex gap-2">
                          <span className="pill">{modelStatusLabel(version.status)}</span>
                          <span className="pill">{validationStatusLabel(version.validation_status)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <StatusBanner message="请选择一个模型查看详情。" />
          )}
        </article>
      </section>
    </div>
  );
}
