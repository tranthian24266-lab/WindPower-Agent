import { useEffect, useState } from "react";

import { MetricGrid } from "../components/MetricGrid";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  getApiErrorMessage,
  getEvalRun,
  getEvalRuns,
  getEvalSuites,
  getObservabilitySummary,
  runEvalSuite,
} from "../lib/api";
import { formatDate } from "../lib/format";
import type { EvalRun, EvalSuite, ObservabilitySummary } from "../types";

export function EvalDashboardPage() {
  const [suites, setSuites] = useState<EvalSuite[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvalRun | null>(null);
  const [observability, setObservability] = useState<ObservabilitySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningSuiteId, setRunningSuiteId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadAll() {
      try {
        const [nextSuites, nextRuns, nextObservability] = await Promise.all([
          getEvalSuites(),
          getEvalRuns(),
          getObservabilitySummary(),
        ]);
        if (!active) {
          return;
        }
        setSuites(nextSuites);
        setRuns(nextRuns);
        setObservability(nextObservability);
        if (nextRuns[0]) {
          setSelectedRun(await getEvalRun(nextRuns[0].eval_run_id));
        } else {
          setSelectedRun(null);
        }
        setError(null);
      } catch (caught: unknown) {
        if (!active) {
          return;
        }
        setError(getApiErrorMessage(caught, "加载评测仪表盘失败。"));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadAll();
    return () => {
      active = false;
    };
  }, []);

  async function handleRunSuite(suiteId: string) {
    setRunningSuiteId(suiteId);
    try {
      const evalRun = await runEvalSuite(suiteId);
      const [nextRuns, nextObservability, detail] = await Promise.all([
        getEvalRuns(),
        getObservabilitySummary(),
        getEvalRun(evalRun.eval_run_id),
      ]);
      setRuns(nextRuns);
      setObservability(nextObservability);
      setSelectedRun(detail);
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "执行评测失败。"));
    } finally {
      setRunningSuiteId(null);
    }
  }

  async function handleSelectRun(evalRunId: string) {
    try {
      setSelectedRun(await getEvalRun(evalRunId));
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "加载评测详情失败。"));
    }
  }

  const latestScore = runs[0]?.score ?? 0;
  const passedRuns = runs.filter((item) => item.status === "succeeded").length;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="质量闭环"
        title="评测仪表盘"
      />
      {loading ? <StatusBanner message="评测仪表盘加载中..." /> : null}
      {error ? <StatusBanner variant="error" message={error} /> : null}

      <MetricGrid
        items={[
          { label: "评测套件", value: suites.length },
          { label: "历史评测", value: runs.length },
          { label: "通过运行", value: passedRuns },
          { label: "最新分数", value: latestScore ? `${Math.round(latestScore * 100)}%` : "0%" },
        ]}
      />

      <section className="panel-grid two-up">
        <article className="content-panel">
          <div className="section-head">
            <h3>评测套件</h3>
          </div>
          <div className="stack-list">
            {suites.map((suite) => (
              <div key={suite.suite_id} className="preview-card">
                <strong>{suite.title}</strong>
                <p className="inline-note">
                  {suite.suite_id} | v{suite.version} | {suite.item_count} items
                </p>
                <p>{suite.description || "--"}</p>
                <button
                  className="action-button"
                  type="button"
                  disabled={runningSuiteId === suite.suite_id}
                  onClick={() => void handleRunSuite(suite.suite_id)}
                >
                  {runningSuiteId === suite.suite_id ? "运行中..." : "运行套件"}
                </button>
              </div>
            ))}
          </div>
        </article>

        <article className="content-panel">
          <div className="section-head">
            <h3>观测摘要</h3>
          </div>
          {observability ? (
            <div className="stack-list">
              <p className="inline-note">最近事件数：{observability.event_count}</p>
              <pre className="json-panel">{JSON.stringify(observability.counts_by_type, null, 2)}</pre>
            </div>
          ) : (
            <p className="inline-note">暂无观测摘要。</p>
          )}
        </article>
      </section>

      <section className="panel-grid two-up">
        <article className="content-panel">
          <div className="section-head">
            <h3>历史运行</h3>
          </div>
          <div className="stack-list">
            {runs.map((run) => (
              <button key={run.eval_run_id} type="button" className="choice-card" onClick={() => void handleSelectRun(run.eval_run_id)}>
                <strong>{run.suite_id}</strong>
                <p>
                  {run.status} | {run.score !== null && run.score !== undefined ? `${Math.round(run.score * 100)}%` : "--"}
                </p>
                <small>{formatDate(run.started_at)}</small>
              </button>
            ))}
          </div>
        </article>

        <article className="content-panel">
          <div className="section-head">
            <h3>运行详情</h3>
          </div>
          {selectedRun ? (
            <div className="stack-list">
              <dl className="meta-grid">
                <div>
                  <dt>eval_run_id</dt>
                  <dd>{selectedRun.eval_run_id}</dd>
                </div>
                <div>
                  <dt>suite</dt>
                  <dd>{selectedRun.suite_id}</dd>
                </div>
                <div>
                  <dt>status</dt>
                  <dd>{selectedRun.status}</dd>
                </div>
                <div>
                  <dt>score</dt>
                  <dd>{selectedRun.score !== null && selectedRun.score !== undefined ? `${Math.round(selectedRun.score * 100)}%` : "--"}</dd>
                </div>
              </dl>
              <div className="stack-list">
                {(selectedRun.items || []).map((item) => (
                  <div key={item.eval_item_id} className="preview-card">
                    <strong>{item.item_key}</strong>
                    <p className="inline-note">{item.status}</p>
                    <pre className="json-panel">{JSON.stringify(item.details || {}, null, 2)}</pre>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="inline-note">请选择一个评测运行查看详情。</p>
          )}
        </article>
      </section>
    </div>
  );
}
