import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  buildApiUrl,
  createAgentRun,
  generateReport,
  getAgentRun,
  getApiErrorMessage,
  getEnhancedReport,
  getEnhancedReportVersions,
  getReport,
} from "../lib/api";
import type { EnhancedReportPayload, EnhancedReportVersion, ReportPayload } from "../types";

type ReportTab = "base" | "enhanced";

function isNotFoundError(caught: unknown): boolean {
  return axios.isAxiosError(caught) && caught.response?.status === 404;
}

export function ReportsPage() {
  const { caseId = "" } = useParams();
  const [baseReport, setBaseReport] = useState<ReportPayload | null>(null);
  const [enhancedReport, setEnhancedReport] = useState<EnhancedReportPayload | null>(null);
  const [enhancedVersions, setEnhancedVersions] = useState<EnhancedReportVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [activeTab, setActiveTab] = useState<ReportTab>("base");
  const [loading, setLoading] = useState(true);
  const [versionLoading, setVersionLoading] = useState(false);
  const [generatingBase, setGeneratingBase] = useState(false);
  const [generatingEnhanced, setGeneratingEnhanced] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);

  async function loadReports(preferredVersionId?: string) {
    setLoading(true);
    try {
      const [nextBase, latestEnhanced, nextVersions] = await Promise.all([
        getReport(caseId).catch((caught: unknown) => {
          if (isNotFoundError(caught)) {
            return null;
          }
          throw caught;
        }),
        getEnhancedReport(caseId).catch((caught: unknown) => {
          if (isNotFoundError(caught)) {
            return null;
          }
          throw caught;
        }),
        getEnhancedReportVersions(caseId).catch((caught: unknown) => {
          if (isNotFoundError(caught)) {
            return [];
          }
          throw caught;
        }),
      ]);

      const nextSelectedVersionId =
        preferredVersionId && nextVersions.some((item) => item.report_version_id === preferredVersionId)
          ? preferredVersionId
          : latestEnhanced?.report_version_id || nextVersions[0]?.report_version_id || "";
      const nextEnhanced =
        nextSelectedVersionId && latestEnhanced?.report_version_id !== nextSelectedVersionId
          ? await getEnhancedReport(caseId, nextSelectedVersionId)
          : latestEnhanced;

      setBaseReport(nextBase);
      setEnhancedReport(nextEnhanced);
      setEnhancedVersions(nextVersions);
      setSelectedVersionId(nextSelectedVersionId);
      setActiveTab(nextEnhanced ? "enhanced" : "base");
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "加载报告失败，请稍后重试。"));
      setBaseReport(null);
      setEnhancedReport(null);
      setEnhancedVersions([]);
      setSelectedVersionId("");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadReports();
  }, [caseId]);

  useEffect(() => {
    if (!pendingRunId) {
      return;
    }
    const activeRunId = pendingRunId;
    async function pollRun() {
      try {
        const run = await getAgentRun(activeRunId);
        if (run.status === "succeeded") {
          setPendingRunId(null);
          setGeneratingEnhanced(false);
          await loadReports();
          setActiveTab("enhanced");
          return;
        }
        if (run.status === "failed" || run.status === "cancelled") {
          const message = typeof run.error?.message === "string" ? run.error.message : "增强报告运行失败。";
          setError(message);
          setPendingRunId(null);
          setGeneratingEnhanced(false);
        }
      } catch (caught: unknown) {
        setError(getApiErrorMessage(caught, "获取运行状态失败。"));
        setPendingRunId(null);
        setGeneratingEnhanced(false);
      }
    }

    void pollRun();
    const timer = window.setInterval(() => {
      void pollRun();
    }, 1500);
    return () => window.clearInterval(timer);
  }, [caseId, pendingRunId]);

  const previewUrl = useMemo(() => {
    if (activeTab === "enhanced" && enhancedReport?.preview_url) {
      return buildApiUrl(enhancedReport.preview_url);
    }
    if (activeTab === "base" && baseReport?.preview_url) {
      return buildApiUrl(baseReport.preview_url);
    }
    return null;
  }, [activeTab, baseReport, enhancedReport]);

  const baseDownloadUrl = useMemo(
    () =>
      baseReport?.download_html_url || baseReport?.download_url
        ? buildApiUrl(baseReport.download_html_url || baseReport.download_url || "")
        : null,
    [baseReport],
  );
  const basePdfUrl = useMemo(
    () => (baseReport?.download_pdf_url ? buildApiUrl(baseReport.download_pdf_url) : null),
    [baseReport],
  );
  const enhancedDocxUrl = useMemo(
    () => (enhancedReport?.download_docx_url ? buildApiUrl(enhancedReport.download_docx_url) : null),
    [enhancedReport],
  );
  const enhancedPdfUrl = useMemo(
    () => (enhancedReport?.download_pdf_url ? buildApiUrl(enhancedReport.download_pdf_url) : null),
    [enhancedReport],
  );

  async function handleGenerateBase() {
    setGeneratingBase(true);
    try {
      await generateReport(caseId);
      await loadReports(selectedVersionId || undefined);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "生成基础报告失败。"));
    } finally {
      setGeneratingBase(false);
    }
  }

  async function handleGenerateEnhanced() {
    setGeneratingEnhanced(true);
    try {
      const submission = await createAgentRun({
        runType: "enhanced_report",
        caseId,
        input: { case_id: caseId },
      });
      setPendingRunId(submission.run_id);
      setActiveTab("enhanced");
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "提交增强报告运行失败。"));
      setGeneratingEnhanced(false);
    }
  }

  async function handleSelectVersion(reportVersionId: string) {
    setSelectedVersionId(reportVersionId);
    setVersionLoading(true);
    try {
      const report = await getEnhancedReport(caseId, reportVersionId);
      setEnhancedReport(report);
      setActiveTab("enhanced");
      setError(null);
    } catch (caught: unknown) {
      setError(getApiErrorMessage(caught, "切换增强报告版本失败。"));
    } finally {
      setVersionLoading(false);
    }
  }

  const citations = enhancedReport?.report_json?.citations ?? [];
  const sections = enhancedReport?.report_json
    ? [
        enhancedReport.report_json.case_summary,
        enhancedReport.report_json.diagnosis_conclusion,
        enhancedReport.report_json.risk_assessment,
        enhancedReport.report_json.evidence_summary,
        enhancedReport.report_json.maintenance_actions,
        enhancedReport.report_json.applicability_and_limits,
      ]
    : [];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="报告预览"
        title="报告中心"
        action={
          <div className="button-row">
            <button className="action-button" type="button" onClick={handleGenerateBase} disabled={generatingBase}>
              {generatingBase ? "基础报告生成中..." : "生成基础报告"}
            </button>
            <button
              className="action-button"
              type="button"
              onClick={handleGenerateEnhanced}
              disabled={generatingEnhanced}
            >
              {generatingEnhanced ? "增强报告排队中..." : "提交增强报告运行"}
            </button>
            {pendingRunId ? (
              <Link className="ghost-button" to={`/runs/${pendingRunId}`}>
                查看当前运行
              </Link>
            ) : enhancedReport?.run_id ? (
              <Link className="ghost-button" to={`/runs/${enhancedReport.run_id}`}>
                查看增强报告运行记录
              </Link>
            ) : null}
            {previewUrl ? (
              <a className="ghost-button" href={previewUrl} target="_blank" rel="noreferrer">
                打开预览
              </a>
            ) : null}
            {activeTab === "base" && baseDownloadUrl ? (
              <a className="ghost-button" href={baseDownloadUrl} target="_blank" rel="noreferrer">
                下载基础 HTML
              </a>
            ) : null}
            {activeTab === "base" && basePdfUrl ? (
              <a className="ghost-button" href={basePdfUrl} target="_blank" rel="noreferrer">
                下载基础 PDF
              </a>
            ) : null}
            {activeTab === "enhanced" && enhancedDocxUrl ? (
              <a className="ghost-button" href={enhancedDocxUrl} target="_blank" rel="noreferrer">
                下载增强 DOCX
              </a>
            ) : null}
            {activeTab === "enhanced" && enhancedPdfUrl ? (
              <a className="ghost-button" href={enhancedPdfUrl} target="_blank" rel="noreferrer">
                下载增强 PDF
              </a>
            ) : null}
          </div>
        }
      />

      <section className="content-panel">
        <div className="report-tab-row">
          <button
            className={`report-tab ${activeTab === "base" ? "active" : ""}`}
            type="button"
            onClick={() => setActiveTab("base")}
          >
            基础报告
          </button>
          <button
            className={`report-tab ${activeTab === "enhanced" ? "active" : ""}`}
            type="button"
            onClick={() => setActiveTab("enhanced")}
            disabled={!enhancedReport && !pendingRunId}
          >
            增强报告
          </button>
          <span className="inline-note inline-wrap">
            增强版本数：{enhancedVersions.length}
            {enhancedReport ? ` | 当前版本 ${enhancedReport.report_version_id}` : ""}
          </span>
        </div>
      </section>

      {pendingRunId ? <StatusBanner message={`增强报告运行中，run_id: ${pendingRunId}`} /> : null}
      {loading ? <StatusBanner message="报告加载中..." /> : null}
      {versionLoading ? <StatusBanner message="正在切换增强报告版本..." /> : null}
      {error ? <StatusBanner variant="error" message={error} /> : null}

      <section className="panel-grid report-layout">
        <section className="content-panel report-frame-wrap">
          {previewUrl ? (
            <iframe className="report-frame" src={previewUrl} title={`${activeTab}-report-${caseId}`} />
          ) : (
            <p className="inline-note">
              {activeTab === "base" ? "当前案例还没有生成基础报告。" : "当前案例还没有生成增强报告。"}
            </p>
          )}
        </section>

        <aside className="content-panel report-sidebar">
          {activeTab === "enhanced" ? (
            <div className="stack-list">
              <div className="preview-card">
                <strong>版本历史</strong>
                <p className="inline-note">切换版本后，右侧预览、结构化摘要和下载链接都会同步更新。</p>
                {enhancedVersions.length ? (
                  <div className="stack-list">
                    {enhancedVersions.map((version) => (
                      <button
                        key={version.report_version_id}
                        type="button"
                        className={`choice-card${
                          selectedVersionId === version.report_version_id ? " selected" : ""
                        }`}
                        onClick={() => void handleSelectVersion(version.report_version_id)}
                      >
                        <strong className="inline-wrap">{version.report_version_id}</strong>
                        <p className="inline-wrap">
                          {version.source_mode} | {version.created_at}
                        </p>
                        {version.run_id ? <span className="pill">run_id 已关联</span> : null}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="inline-note">当前还没有增强报告版本。</p>
                )}
              </div>

              {enhancedReport?.report_json ? (
                <>
                  <div className="preview-card">
                    <strong>结构化章节</strong>
                    <p className="inline-note">这里展示的是增强报告结构化 JSON 的主要内容。</p>
                    {enhancedReport.run_id ? (
                      <p className="helper-copy">
                        run_id: <Link to={`/runs/${enhancedReport.run_id}`}>{enhancedReport.run_id}</Link>
                      </p>
                    ) : null}
                  </div>
                  {sections.map((section) => (
                    <div className="list-card" key={section.title}>
                      <strong>{section.title}</strong>
                      <p>{section.content}</p>
                      <span className="pill">置信度 {section.confidence}</span>
                    </div>
                  ))}
                  <div className="preview-card">
                    <strong>证据引用</strong>
                    <p className="inline-note">这里列出增强报告引用到的证据条目。</p>
                  </div>
                  {citations.length ? (
                    citations.map((item) => (
                      <div className="list-card" key={`${item.evidence_ref}-${item.title}`}>
                        <strong>{item.title}</strong>
                        <p>{item.excerpt}</p>
                        <span className="pill">
                          {item.evidence_type}
                          {item.score !== null && item.score !== undefined ? ` | score ${item.score.toFixed(3)}` : ""}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="inline-note">当前增强报告没有可展示的证据引用。</p>
                  )}
                </>
              ) : (
                <p className="inline-note">当前还没有可展示的增强报告内容。</p>
              )}
            </div>
          ) : (
            <div className="stack-list">
              <div className="preview-card">
                <strong>基础报告</strong>
                <p className="inline-note">基础报告保留现有 HTML 报告链路，同时显式展示 PDF 生成状态。</p>
              </div>
              {baseReport ? (
                <div className="preview-card">
                  <strong>PDF 状态</strong>
                  <p className="inline-note">
                    状态：{baseReport.pdf_status || "unknown"}
                    {baseReport.pdf_reason ? ` | ${baseReport.pdf_reason}` : ""}
                  </p>
                  <p className="inline-note">
                    {basePdfUrl ? "当前基础报告可以导出 PDF。" : "当前暂时不能导出 PDF，但 HTML 预览和 HTML 下载仍然可用。"}
                  </p>
                </div>
              ) : null}
              <div className="preview-card">
                <strong>切换说明</strong>
                <p className="inline-note">如果你需要证据支撑、更丰富的导出格式和结构化章节，请切换到增强报告页签。</p>
              </div>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}
