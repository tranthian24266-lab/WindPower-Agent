import { useEffect, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { getApiErrorMessage, getAuditLogs } from "../lib/api";
import type { AuditLog } from "../types";

export function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setLogs(await getAuditLogs(100));
      setError(null);
    } catch (caught) {
      setError(getApiErrorMessage(caught, "加载审计日志失败。"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="审计治理"
        title="审计日志"
        action={
          <button className="ghost-button" type="button" onClick={() => void refresh()}>
            刷新日志
          </button>
        }
      />

      {error ? <StatusBanner variant="error" message={error} /> : null}
      {loading ? <StatusBanner message="正在加载审计日志..." /> : null}

      {!loading && !error ? (
        <section className="content-panel">
          <div className="section-head">
            <h3>最新审计记录</h3>
            <span className="pill">{logs.length} 条记录</span>
          </div>

          <div className="stack-list">
            {logs.length === 0 ? <p className="inline-note">暂无审计日志。</p> : null}
            {logs.map((log) => (
              <div key={log.audit_id} className="preview-card">
                <div className="section-head">
                  <div>
                    <strong>{log.action}</strong>
                    <p className="inline-note">
                      {log.created_at} | {log.actor_id} | {log.role}
                    </p>
                  </div>
                  <span className="pill">{log.resource_type}</span>
                </div>
                <dl className="meta-grid">
                  <div>
                    <dt>audit_id</dt>
                    <dd>{log.audit_id}</dd>
                  </div>
                  <div>
                    <dt>resource_id</dt>
                    <dd>{log.resource_id || "--"}</dd>
                  </div>
                  <div>
                    <dt>run_id</dt>
                    <dd>{log.run_id || "--"}</dd>
                  </div>
                  <div>
                    <dt>trace_id</dt>
                    <dd>{log.trace_id || "--"}</dd>
                  </div>
                </dl>
                <pre className="json-panel">{JSON.stringify(log.details || {}, null, 2)}</pre>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
