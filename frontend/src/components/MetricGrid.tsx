import { formatValue } from "../lib/format";
import React from "react";

export type MetricVariant = "large" | "standard" | "trend";

export interface MetricItem {
  label: string;
  value: unknown;
  variant?: MetricVariant;
  icon?: React.ReactNode;
  trend?: {
    value: string;
    isUp?: boolean;
    isGood?: boolean;
  };
  status?: "normal" | "warning" | "danger" | "running";
}

export function MetricGrid({ items }: { items: MetricItem[] }) {
  return (
    <div className="metric-grid">
      {items.map((item) => {
        const variant = item.variant || "standard";
        
        let cardClass = "metric-card";
        if (variant === "large") cardClass += " row-span-2 col-span-2 p-8";
        
        return (
          <article key={item.label} className={cardClass}>
            <div className="flex justify-between items-start mb-2">
              <span className="metric-label mb-0">{item.label}</span>
              {item.icon && <div className="text-emerald-500 opacity-80">{item.icon}</div>}
            </div>
            
            <strong className={`metric-value ${variant === "large" ? "text-5xl my-4" : ""}`}>
              {formatValue(item.value)}
            </strong>
            
            {item.trend && (
              <div className="mt-auto pt-2 flex items-center gap-2 text-sm">
                <span className={
                  item.trend.isGood === false ? "text-rose-500 font-medium" : 
                  item.trend.isGood === true ? "text-emerald-500 font-medium" : 
                  "text-slate-500"
                }>
                  {item.trend.isUp ? "↑" : "↓"} {item.trend.value}
                </span>
                <span className="text-slate-400 text-xs">较上周期</span>
              </div>
            )}
            
            {item.status && (
              <div className="mt-auto pt-2">
                <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                  item.status === 'normal' ? 'bg-emerald-50 text-emerald-600' :
                  item.status === 'warning' ? 'bg-amber-50 text-amber-600' :
                  item.status === 'danger' ? 'bg-rose-50 text-rose-600' :
                  'bg-blue-50 text-blue-600'
                }`}>
                  {item.status === 'normal' ? '运行正常' :
                   item.status === 'warning' ? '需要关注' :
                   item.status === 'danger' ? '存在风险' : '系统计算中'}
                </span>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
