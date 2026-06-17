import { riskLabel } from "../lib/format";

export function RiskBadge({ value }: { value?: string | null }) {
  const kind = value || "unknown";
  return <span className={`risk-badge ${kind}`}>{riskLabel(value)}</span>;
}
