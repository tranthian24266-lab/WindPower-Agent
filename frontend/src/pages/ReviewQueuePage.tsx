import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  approveReviewTask,
  getApiErrorMessage,
  getReviewTask,
  getReviewTasks,
  rejectReviewTask,
  requestReviewChanges,
} from "../lib/api";
import type { ReviewTaskDetail, ReviewTaskSummary } from "../types";

export function ReviewQueuePage() {
  const [tasks, setTasks] = useState<ReviewTaskSummary[]>([]);
  const [selectedTask, setSelectedTask] = useState<ReviewTaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("pending");
  const [reviewer, setReviewer] = useState("ops-review");
  const [comment, setComment] = useState("");
  const [isMutating, setIsMutating] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadQueue() {
      try {
        const queue = await getReviewTasks({ status: filter || undefined, limit: 50 });
        if (!active) {
          return;
        }
        setTasks(queue);
        const nextSelectedId = selectedTask?.review_task_id && queue.some((item) => item.review_task_id === selectedTask.review_task_id)
          ? selectedTask.review_task_id
          : queue[0]?.review_task_id;
        if (nextSelectedId) {
          const detail = await getReviewTask(nextSelectedId);
          if (!active) {
            return;
          }
          setSelectedTask(detail);
        } else {
          setSelectedTask(null);
        }
        setError(null);
      } catch (caught: unknown) {
        if (!active) {
          return;
        }
        setError(getApiErrorMessage(caught, "加载审核队列失败。"));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadQueue();
    return () => {
      active = false;
    };
  }, [filter]);

  async function selectTask(reviewTaskId: string) {
    try {
      setSelectedTask(await getReviewTask(reviewTaskId));
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "加载审核详情失败。"));
    }
  }

  async function refreshCurrent(reviewTaskId?: string) {
    const queue = await getReviewTasks({ status: filter || undefined, limit: 50 });
    setTasks(queue);
    const nextId = reviewTaskId && queue.some((item) => item.review_task_id === reviewTaskId)
      ? reviewTaskId
      : queue[0]?.review_task_id;
    setSelectedTask(nextId ? await getReviewTask(nextId) : null);
  }

  async function handleDecision(action: "approve" | "reject" | "changes_requested") {
    if (!selectedTask) {
      return;
    }
    setIsMutating(true);
    try {
      const payload = {
        reviewer: reviewer.trim() || undefined,
        comment: comment.trim() || undefined,
      };
      let nextTask: ReviewTaskDetail;
      if (action === "approve") {
        nextTask = await approveReviewTask(selectedTask.review_task_id, payload);
      } else if (action === "reject") {
        nextTask = await rejectReviewTask(selectedTask.review_task_id, payload);
      } else {
        nextTask = await requestReviewChanges(selectedTask.review_task_id, payload);
      }
      setSelectedTask(nextTask);
      await refreshCurrent(nextTask.review_task_id);
      setComment("");
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "提交审核动作失败。"));
    } finally {
      setIsMutating(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="人工审核"
        title="审核队列"
      />

      {loading ? <StatusBanner message="审核队列加载中..." /> : null}
      {error ? <StatusBanner variant="error" message={error} /> : null}

      <section className="panel-grid two-up">
        <article className="content-panel">
          <div className="section-head">
            <h3>待审队列</h3>
            <select value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option value="pending">pending</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
              <option value="changes_requested">changes_requested</option>
            </select>
          </div>
          <div className="stack-list">
            {tasks.length === 0 ? <p className="inline-note">当前筛选条件下没有审核任务。</p> : null}
            {tasks.map((task) => (
              <button
                key={task.review_task_id}
                type="button"
                className={`choice-card${selectedTask?.review_task_id === task.review_task_id ? " selected" : ""}`}
                onClick={() => void selectTask(task.review_task_id)}
              >
                <strong>{task.summary || task.review_type}</strong>
                <p>
                  {task.status} | {task.priority} | {task.case_id || "--"}
                </p>
                <small>{task.report_version_id || task.run_id || task.review_task_id}</small>
              </button>
            ))}
          </div>
        </article>

        <article className="content-panel">
          <div className="section-head">
            <h3>审核详情</h3>
            <span className="pill">{selectedTask?.status || "--"}</span>
          </div>

          {selectedTask ? (
            <div className="stack-list">
              <dl className="meta-grid">
                <div>
                  <dt>review_task_id</dt>
                  <dd>{selectedTask.review_task_id}</dd>
                </div>
                <div>
                  <dt>run_id</dt>
                  <dd>{selectedTask.run_id || "--"}</dd>
                </div>
                <div>
                  <dt>case_id</dt>
                  <dd>{selectedTask.case_id || "--"}</dd>
                </div>
                <div>
                  <dt>report_version_id</dt>
                  <dd>{selectedTask.report_version_id || "--"}</dd>
                </div>
                <div>
                  <dt>requested_at</dt>
                  <dd>{selectedTask.requested_at}</dd>
                </div>
                <div>
                  <dt>decided_at</dt>
                  <dd>{selectedTask.decided_at || "--"}</dd>
                </div>
              </dl>

              <div className="preview-card">
                <strong>摘要</strong>
                <p>{selectedTask.summary || "--"}</p>
                <pre className="json-panel">{JSON.stringify(selectedTask.metadata || {}, null, 2)}</pre>
              </div>

              {selectedTask.status === "pending" ? (
                <div className="stack-list">
                  <label className="stack-list">
                    <span className="inline-note">Reviewer</span>
                    <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} type="text" />
                  </label>
                  <label className="stack-list">
                    <span className="inline-note">Comment</span>
                    <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={4} />
                  </label>
                  <div className="button-row">
                    <button className="action-button" type="button" disabled={isMutating} onClick={() => void handleDecision("approve")}>
                      批准并恢复
                    </button>
                    <button className="ghost-button" type="button" disabled={isMutating} onClick={() => void handleDecision("changes_requested")}>
                      要求修改
                    </button>
                    <button className="ghost-button" type="button" disabled={isMutating} onClick={() => void handleDecision("reject")}>
                      驳回
                    </button>
                  </div>
                </div>
              ) : null}

              <div className="button-row">
                {selectedTask.run_id ? (
                  <Link className="ghost-button" to={`/runs/${selectedTask.run_id}`}>
                    打开关联 Run
                  </Link>
                ) : null}
                {selectedTask.case_id ? (
                  <Link className="ghost-button" to={`/reports/${selectedTask.case_id}`}>
                    打开关联报告
                  </Link>
                ) : null}
              </div>

              <div className="stack-list">
                <strong>审核动作</strong>
                {selectedTask.actions.map((action) => (
                  <div key={action.review_action_id} className="preview-card">
                    <strong>{action.action}</strong>
                    <p className="inline-note">
                      {action.actor || "system"} | {action.created_at}
                    </p>
                    <p>{action.comment || "--"}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="inline-note">请选择一个审核任务查看详情。</p>
          )}
        </article>
      </section>
    </div>
  );
}
