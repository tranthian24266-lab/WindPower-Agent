import type { TaskType } from "../types";

interface ResultChartProps {
  taskType: TaskType;
  result: Record<string, unknown>;
}

interface PieSegment {
  label: string;
  value: number;
  color: string;
}

interface BarMetric {
  label: string;
  value: number;
  accent: string;
}

const PIE_COLORS = ["#2c8f5b", "#df6f4b", "#d3a64f", "#5b7be0"];
const BAR_COLOR = "#2c8f5b";
const ALERT_BAR_COLOR = "#df6f4b";

function toFiniteNumber(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatChartNumber(value: number): string {
  if (!Number.isFinite(value)) {
    return "--";
  }
  if (Math.abs(value) >= 100 || Number.isInteger(value)) {
    return String(Math.round(value * 1000) / 1000);
  }
  return value.toFixed(3);
}

function renderPieChart(segments: PieSegment[]) {
  const total = segments.reduce((sum, item) => sum + item.value, 0);

  if (total <= 0) {
    return <p className="inline-note">当前结果没有可展示的概率图。</p>;
  }

  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="result-chart-shell">
      <div className="result-chart-donut">
        <svg viewBox="0 0 120 120" aria-label="诊断概率图" role="img">
          <circle className="result-chart-ring-bg" cx="60" cy="60" r={radius} />
          {segments.map((segment) => {
            const arcLength = (segment.value / total) * circumference;
            const strokeDasharray = `${arcLength} ${circumference}`;
            const strokeDashoffset = -offset;
            offset += arcLength;
            return (
              <circle
                key={segment.label}
                className="result-chart-ring"
                cx="60"
                cy="60"
                r={radius}
                stroke={segment.color}
                strokeDasharray={strokeDasharray}
                strokeDashoffset={strokeDashoffset}
              />
            );
          })}
          <g className="result-chart-center-copy">
            <text x="60" y="56">
              概率
            </text>
            <text x="60" y="72">
              分布
            </text>
          </g>
        </svg>
      </div>
      <div className="result-chart-legend">
        {segments.map((segment) => (
          <div className="result-chart-legend-item" key={segment.label}>
            <span className="result-chart-swatch" style={{ backgroundColor: segment.color }} />
            <div>
              <strong>{segment.label}</strong>
              <p>{(segment.value * 100).toFixed(1)}%</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderBarChart(metrics: BarMetric[]) {
  const maxValue = Math.max(...metrics.map((item) => item.value), 0);

  return (
    <div className="result-chart-bars">
      {metrics.map((metric) => {
        const width = maxValue > 0 ? `${(metric.value / maxValue) * 100}%` : "0%";
        return (
          <div className="result-chart-bar-row" key={metric.label}>
            <div className="result-chart-bar-head">
              <strong>{metric.label}</strong>
              <span>{formatChartNumber(metric.value)}</span>
            </div>
            <div className="result-chart-bar-track">
              <div className="result-chart-bar-fill" style={{ width, backgroundColor: metric.accent }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ResultChart({ taskType, result }: ResultChartProps) {
  if (taskType === "fault_diagnosis") {
    const probabilities = (result.class_probabilities as Record<string, number> | undefined) || {};
    const nameMap: Record<string, string> = {
      healthy: "健康",
      damaged: "受损",
    };
    const segments = Object.entries(probabilities).map(([name, value], index) => ({
      label: nameMap[name] || name,
      value: toFiniteNumber(value),
      color: PIE_COLORS[index % PIE_COLORS.length],
    }));
    return renderPieChart(segments);
  }

  if (taskType === "rul_prediction") {
    return renderBarChart([
      { label: "原始 RUL", value: toFiniteNumber(result.rul_raw), accent: BAR_COLOR },
      { label: "展示用 RUL", value: toFiniteNumber(result.rul_clipped), accent: "#56a973" },
    ]);
  }

  return renderBarChart([
    { label: "阈值", value: toFiniteNumber(result.threshold), accent: ALERT_BAR_COLOR },
    { label: "平均异常分数", value: toFiniteNumber(result.mean_anomaly_score), accent: "#e28963" },
    { label: "最大异常分数", value: toFiniteNumber(result.max_anomaly_score), accent: "#d3a64f" },
    { label: "异常比例", value: toFiniteNumber(result.anomaly_ratio), accent: "#bb5b43" },
  ]);
}
