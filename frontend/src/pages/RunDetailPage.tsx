import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { cancelAgentRun, getAgentRun, getAgentRunTimeline, getApiErrorMessage, resumeAgentRun } from "../lib/api";
import type { AgentRun, AgentRunTimelineItem } from "../types";

function renderJson(value: unknown): string {
  if (value === null || value === undefined) {
    return "null";
  }
  return JSON.stringify(value, null, 2);
}

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<AgentRun | null>(null);
  const [timeline, setTimeline] = useState<AgentRunTimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadRun() {
      try {
        const [runPayload, timelinePayload] = await Promise.all([getAgentRun(runId), getAgentRunTimeline(runId)]);
        if (!active) {
          return;
        }
        setRun(runPayload);
        setTimeline(timelinePayload.timeline);
        setError(null);
      } catch (caught) {
        if (!active) {
          return;
        }
        setRun(null);
        setTimeline([]);
        setError(getApiErrorMessage(caught, "加载运行详情失败。"));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadRun();
    const timer = window.setInterval(() => {
      if (run?.status === "queued" || run?.status === "running" || run?.status === "waiting_review") {
        void loadRun();
      }
    }, 1500);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [runId, run?.status]);

  const handoffTimeline = useMemo(
    () => timeline.filter((item) => item.kind === "telemetry" && item.name === "agent_handoff"),
    [timeline],
  );

  async function handleCancel() {
    if (!run) {
      return;
    }
    setIsMutating(true);
    try {
      await cancelAgentRun(run.run_id);
      setRun(await getAgentRun(run.run_id));
      setTimeline((await getAgentRunTimeline(run.run_id)).timeline);
      setError(null);
    } catch (caught) {
      setError(getApiErrorMessage(caught, "取消运行失败。"));
    } finally {
      setIsMutating(false);
    }
  }

  async function handleResume() {
    if (!run) {
      return;
    }
    setIsMutating(true);
    try {
      await resumeAgentRun(run.run_id);
      setRun(await getAgentRun(run.run_id));
      setTimeline((await getAgentRunTimeline(run.run_id)).timeline);
      setError(null);
    } catch (caught) {
      setError(getApiErrorMessage(caught, "恢复运行失败。"));
    } finally {
      setIsMutating(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="运行详情"
        title="智能体运行详情"
        action={
          <div className="button-row">
            {run?.status === "queued" ? (
              <button className="ghost-button" type="button" onClick={() => void handleCancel()} disabled={isMutating}>
                取消排队
              </button>
            ) : null}
            {run && (run.status === "failed" || run.status === "cancelled") ? (
              <button className="ghost-button" type="button" onClick={() => void handleResume()} disabled={isMutating}>
                重新入队
              </button>
            ) : null}
            {run?.review_tasks?.[0] ? (
              <Link className="ghost-button" to="/reviews">
                打开审核队列
              </Link>
            ) : null}
          </div>
        }
      />

      {loading ? <StatusBanner message="运行详情加载中..." /> : null}
      {run?.status === "queued" || run?.status === "running" || run?.status === "waiting_review" ? (
        <StatusBanner message={`运行状态：${run.status}，页面会自动刷新。`} />
      ) : null}
      {error ? <StatusBanner variant="error" message={error} /> : null}

      {run ? (
        <>
          <section className="content-panel">
            <div className="section-head">
              <h3>运行概览</h3>
              <span className="pill">{run.status}</span>
            </div>
            <dl className="meta-grid">
              <div>
                <dt>run_id</dt>
                <dd>{run.run_id}</dd>
              </div>
              <div>
                <dt>trace_id</dt>
                <dd>{run.trace_id || "--"}</dd>
              </div>
              <div>
                <dt>run_type</dt>
                <dd>{run.run_type}</dd>
              </div>
              <div>
                <dt>case_id</dt>
                <dd>{run.case_id || "--"}</dd>
              </div>
              <div>
                <dt>session_id</dt>
                <dd>{run.session_id || "--"}</dd>
              </div>
              <div>
                <dt>current_step</dt>
                <dd>{run.current_step || "--"}</dd>
              </div>
              <div>
                <dt>step_count</dt>
                <dd>{run.step_count ?? run.steps.length}</dd>
              </div>
              <div>
                <dt>tool_call_count</dt>
                <dd>{run.tool_call_count ?? run.steps.reduce((sum, step) => sum + step.tool_calls.length, 0)}</dd>
              </div>
              <div>
                <dt>triggered_by</dt>
                <dd>{run.triggered_by || "--"}</dd>
              </div>
              <div>
                <dt>started_at</dt>
                <dd>{run.started_at}</dd>
              </div>
              <div>
                <dt>finished_at</dt>
                <dd>{run.finished_at || "--"}</dd>
              </div>
            </dl>
          </section>

          {run.job ? (
            <section className="content-panel">
              <div className="section-head">
                <h3>队列状态</h3>
              </div>
              <dl className="meta-grid">
                <div>
                  <dt>job_id</dt>
                  <dd>{run.job.job_id}</dd>
                </div>
                <div>
                  <dt>job_status</dt>
                  <dd>{run.job.status}</dd>
                </div>
                <div>
                  <dt>attempt_count</dt>
                  <dd>
                    {run.job.attempt_count} / {run.job.max_attempts}
                  </dd>
                </div>
                <div>
                  <dt>worker_id</dt>
                  <dd>{run.job.worker_id || "--"}</dd>
                </div>
              </dl>
            </section>
          ) : null}

          <section className="panel-grid two-up">
            <article className="content-panel">
              <div className="section-head">
                <h3>运行输入</h3>
              </div>
              <pre className="json-panel">{renderJson(run.input)}</pre>
            </article>
            <article className="content-panel">
              <div className="section-head">
                <h3>运行输出 / 错误</h3>
              </div>
              <pre className="json-panel">{renderJson(run.output ?? run.error ?? run.job?.last_error)}</pre>
            </article>
          </section>

          <section className="content-panel">
            <div className="section-head">
              <h3>Specialist Handoffs</h3>
              <span className="pill">{handoffTimeline.length} 条</span>
            </div>
            <div className="stack-list">
              {handoffTimeline.length === 0 ? <p className="inline-note">暂无 specialist handoff 记录。</p> : null}
              {handoffTimeline.map((item, index) => (
                <div key={`${item.timestamp}-${index}`} className="preview-card">
                  <strong>
                    {String(item.details?.from_agent || "orchestrator")} → {String(item.details?.to_agent || "unknown")}
                  </strong>
                  <p className="inline-note">
                    {String(item.details?.capability || "--")} | {item.status} | {item.timestamp}
                  </p>
                  <pre className="json-panel">{renderJson(item.details || {})}</pre>
                </div>
              ))}
            </div>
          </section>

          {run.review_tasks && run.review_tasks.length > 0 ? (
            <section className="content-panel">
              <div className="section-head">
                <h3>审核任务</h3>
              </div>
              <div className="stack-list">
                {run.review_tasks.map((task) => (
                  <div key={task.review_task_id} className="preview-card">
                    <strong>{task.summary || task.review_type}</strong>
                    <p className="inline-note">
                      {task.status} | {task.priority} | {task.requested_at}
                    </p>
                    <p>{task.review_task_id}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="content-panel">
            <div className="section-head">
              <h3>Step Timeline</h3>
            </div>
            <div className="stack-list">
              {run.steps.length === 0 ? <p className="inline-note">当前还没有可展示的 step 记录。</p> : null}
              {run.steps.map((step) => (
                <article key={step.step_id} className="list-card">
                  <div className="section-head">
                    <div>
                      <strong>
                        {step.sequence_no}. {step.step_name}
                      </strong>
                      <p className="inline-note">
                        {step.step_type} | {step.status} | {step.duration_ms ?? "--"} ms
                      </p>
                    </div>
                    <span className="pill">{step.tool_calls.length} 个 tool call</span>
                  </div>
                  <pre className="json-panel">{renderJson(step.output ?? step.error ?? step.input)}</pre>
                  {step.tool_calls.length > 0 ? (
                    <div className="stack-list">
                      {step.tool_calls.map((toolCall) => (
                        <div key={toolCall.tool_call_id} className="preview-card">
                          <strong>{toolCall.tool_name}</strong>
                          <p className="inline-note">
                            {toolCall.status} | {toolCall.duration_ms ?? "--"} ms
                          </p>
                          <pre className="json-panel">{renderJson(toolCall.response ?? toolCall.request)}</pre>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </section>

          <section className="content-panel">
            <div className="section-head">
              <h3>Full Timeline</h3>
            </div>
            <div className="stack-list">
              {timeline.length === 0 ? <p className="inline-note">暂无 timeline 事件。</p> : null}
              {timeline.map((item, index) => (
                <div key={`${item.timestamp}-${item.name}-${index}`} className="preview-card">
                  <strong>
                    {item.kind} / {item.name}
                  </strong>
                  <p className="inline-note">
                    {item.status} | {item.timestamp}
                  </p>
                  <pre className="json-panel">{renderJson(item.details || {})}</pre>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
