import React from 'react';

export function PageSection({ title, extra, children, className = '' }) {
  return (
    <section className={`desktop-section card ${className}`.trim()}>
      <div className="desktop-section-head">
        <h3>{title}</h3>
        {extra ? <div>{extra}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function ToolbarRow({ children, className = '' }) {
  return (
    <div className={`desktop-toolbar ${className}`.trim()}>
      {children}
    </div>
  );
}

export function MetricGrid({ children, className = '' }) {
  return (
    <div className={`desktop-metric-grid ${className}`.trim()}>
      {children}
    </div>
  );
}

export function MetricCard({ label, value, hint }) {
  return (
    <article className="desktop-metric-card">
      <p className="desktop-metric-label">{label}</p>
      <p className="desktop-metric-value">{value}</p>
      {hint ? <p className="desktop-metric-hint">{hint}</p> : null}
    </article>
  );
}
