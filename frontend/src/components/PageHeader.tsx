import React from "react";

export type PageHeaderVariant = "overview" | "workspace" | "operations" | "detail";

interface PageHeaderProps {
  variant?: PageHeaderVariant;
  eyebrow: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  statusArea?: React.ReactNode;
}

export function PageHeader({ 
  variant = "overview", 
  eyebrow, 
  title, 
  action,
  statusArea
}: PageHeaderProps) {
  // Define variant-specific classes
  const variantClasses = {
    overview: "hero-panel",
    workspace: "content-panel flex justify-between items-start",
    operations: "content-panel flex justify-between items-center bg-transparent border-none shadow-none px-0 py-2",
    detail: "content-panel flex flex-col gap-4",
  };

  const titleClasses = {
    overview: "page-title text-4xl mb-2",
    workspace: "page-title text-3xl mb-1",
    operations: "page-title text-2xl",
    detail: "page-title text-3xl mb-2",
  };

  return (
    <section className={variantClasses[variant]}>
      <div className={variant === "detail" ? "flex justify-between items-start w-full" : "flex flex-col"}>
        <div>
          <p className="eyebrow mb-2">{eyebrow}</p>
          <h2 className={titleClasses[variant]}>{title}</h2>
        </div>
        {action && variant === "detail" && <div className="shrink-0">{action}</div>}
      </div>
      
      {statusArea && (
        <div className="mt-4 flex gap-4 items-center">
          {statusArea}
        </div>
      )}

      {action && variant !== "detail" && (
        <div className="shrink-0 flex items-center gap-3">
          {action}
        </div>
      )}
    </section>
  );
}
