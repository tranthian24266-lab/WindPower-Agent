import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { getAgentRuns, getApiErrorMessage, getSpecialistSummary } from "../lib/api";
import type { AgentRunSummary, SpecialistSummary } from "../types";

function formatCountMap(value: Record<string, number>): Array<[string, number]> {
  return Object.entries(value).sort((a, b) => b[1] - a[1]);
}

export function SpecialistDashboardPage() {
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [summary, setSummary] = useState<SpecialistSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const [chatRuns, reportRuns, specialistSummary] = await Promise.all([
        getAgentRuns({ runType: "chat_answer", limit: 20 }),
        getAgentRuns({ runType: "enhanced_report", limit: 20 }),
        getSpecialistSummary(),
      ]);
      setRuns(
        [...chatRuns, ...reportRuns].sort(
          (left, right) => new Date(right.started_at).getTime() - new Date(left.started_at).getTime(),
        ),
      );
      setSummary(specialistSummary);
      setError(null);
    } catch (caught) {
      setError(getApiErrorMessage(caught, "加载专家治理视图失败。"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const chatRuns = runs.filter((item) => item.run_type === "chat_answer");
  const reportRuns = runs.filter((item) => item.run_type === "enhanced_report");
  const specialistCounts = formatCountMap(summary?.counts_by_specialist || {});
  const workflowCounts = formatCountMap(summary?.counts_by_workflow || {});

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="专家治理"
        title="专家智能体监控"
        action={
          <button className="ghost-button" type="button" onClick={() => void refresh()}>
            刷新数据
          </button>
        }
      />

      {error ? <StatusBanner variant="error" message={error} /> : null}
      {loading ? <StatusBanner message="正在加载专家治理视图..." /> : null}

      {!loading && !error ? (
        <>
          <section className="panel-grid three-up">
            <article className="content-panel">
              <div className="section-head">
                <h3>Specialists</h3>
              </div>
              <div className="stack-list">
                {specialistCounts.length === 0 ? <p className="inline-note">暂无 handoff 统计。</p> : null}
                {specialistCounts.map(([name, count]) => (
                  <div key={name} className="preview-card">
                    <strong>{name}</strong>
                    <p className="inline-note">{count} 次 handoff</p>
                  </div>
                ))}
              </div>
            </article>

            <article className="content-panel">
              <div className="section-head">
                <h3>Workflows</h3>
              </div>
              <div className="stack-list">
                {workflowCounts.length === 0 ? <p className="inline-note">暂无 orchestration 汇总。</p> : null}
                {workflowCounts.map(([name, count]) => (
                  <div key={name} className="preview-card">
                    <strong>{name}</strong>
                    <p className="inline-note">{count} 次完成记录</p>
                  </div>
                ))}
              </div>
            </article>

            <article className="content-panel">
              <div className="section-head">
                <h3>Recent Runs</h3>
              </div>
              <div className="stack-list">
                <div className="preview-card">
                  <strong>Chat Specialist</strong>
                  <p className="inline-note">{chatRuns.length} 条近期 run</p>
                </div>
                <div className="preview-card">
                  <strong>Report Specialist</strong>
                  <p className="inline-note">{reportRuns.length} 条近期 run</p>
                </div>
              </div>
            </article>
          </section>

          <section className="content-panel">
            <div className="section-head">
              <h3>Recent Handoffs</h3>
            </div>
            <div className="stack-list">
              {(summary?.recent_handoffs || []).length === 0 ? (
                <p className="inline-note">暂无可展示的 handoff 事件。</p>
              ) : null}
              {(summary?.recent_handoffs || []).map((item) => (
                <div key={item.event_id} className="preview-card">
                  <strong>
                    {item.from_agent || "orchestrator"} → {item.to_agent || "unknown"}
                  </strong>
                  <p className="inline-note">
                    {item.capability || "--"} | {item.status || "--"} | {item.created_at}
                  </p>
                  <div className="button-row">
                    {item.run_id ? (
                      <Link className="ghost-button" to={`/runs/${item.run_id}`}>
                        打开 Run 详情
                      </Link>
                    ) : null}
                    {item.trace_id ? <span className="inline-note">trace_id: {item.trace_id}</span> : null}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="panel-grid two-up">
            <article className="content-panel">
              <div className="section-head">
                <h3>Chat Specialist Runs</h3>
              </div>
              <div className="stack-list">
                {chatRuns.length === 0 ? <p className="inline-note">暂无问答类 run。</p> : null}
                {chatRuns.map((run) => (
                  <div key={run.run_id} className="preview-card">
                    <strong>{run.run_id}</strong>
                    <p className="inline-note">
                      {run.status} | {run.current_step || "--"} | {run.started_at}
                    </p>
                    <div className="button-row">
                      <Link className="ghost-button" to={`/runs/${run.run_id}`}>
                        查看 handoff / step
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="content-panel">
              <div className="section-head">
                <h3>Report Specialist Runs</h3>
              </div>
              <div className="stack-list">
                {reportRuns.length === 0 ? <p className="inline-note">暂无增强报告类 run。</p> : null}
                {reportRuns.map((run) => (
                  <div key={run.run_id} className="preview-card">
                    <strong>{run.run_id}</strong>
                    <p className="inline-note">
                      {run.status} | {run.current_step || "--"} | {run.started_at}
                    </p>
                    <div className="button-row">
                      <Link className="ghost-button" to={`/runs/${run.run_id}`}>
                        查看 handoff / step
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>
        </>
      ) : null}
    </div>
  );
}
