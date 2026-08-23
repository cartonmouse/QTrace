import type { ReactNode } from "react";

type PageHeaderProps = {
  kicker: string;
  title: string;
  description?: string;
  meta?: ReactNode;
  actions?: ReactNode;
};

export function PageHeader({ kicker, title, description, meta, actions }: PageHeaderProps) {
  return (
    <header className="product-page-header" data-product-page-header="true">
      <div className="product-page-heading">
        <p className="product-kicker">{kicker}</p>
        <h1>{title}</h1>
        {description && <p className="product-page-description">{description}</p>}
      </div>
      {(meta || actions) && <div className="product-page-tools">{meta}{actions}</div>}
    </header>
  );
}

type SurfaceProps = {
  children: ReactNode;
  className?: string;
  as?: "section" | "aside" | "article" | "div";
};

export function Surface({ children, className = "", as = "section" }: SurfaceProps) {
  const Component = as;
  return <Component className={`product-surface ${className}`.trim()}>{children}</Component>;
}

type StatusBadgeProps = {
  children: ReactNode;
  tone?: "neutral" | "positive" | "warning" | "danger";
};

export function StatusBadge({ children, tone = "neutral" }: StatusBadgeProps) {
  return <span className={`product-status-badge product-status-badge--${tone}`}>{children}</span>;
}

type StatePanelProps = {
  title: string;
  description?: string;
  tone?: "loading" | "empty" | "error";
  action?: ReactNode;
};

export function StatePanel({ title, description, tone = "empty", action }: StatePanelProps) {
  return (
    <div className={`product-state-panel product-state-panel--${tone}`} role={tone === "error" ? "alert" : undefined}>
      <span className="product-state-mark" aria-hidden="true">{tone === "loading" ? "···" : tone === "error" ? "!" : "—"}</span>
      <div>
        <strong>{title}</strong>
        {description && <p>{description}</p>}
        {action && <div className="product-state-action">{action}</div>}
      </div>
    </div>
  );
}
