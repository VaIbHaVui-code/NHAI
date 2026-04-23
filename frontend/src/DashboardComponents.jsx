import React from "react";

export const STATUS_CONFIG = {
  Pass: { hex: "#10b981", label: "Operational" },
  Fail: { hex: "#f59e0b", label: "Degraded" },
  Critical: { hex: "#ef4444", label: "Urgent" },
};

export function MetricCard({ label, value, color, sub, delay = 0 }) {
  return (
    <div className="metric-card" style={{ animationDelay: `${delay}ms` }}>
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color: color || "#f1f5f9" }}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export function SignCard({ record, isSelected, onSelect, onResolve }) {
  const cfg = STATUS_CONFIG[record.status] || { hex: "#94a3b8" };
  const isCritical = record.reflectivity_score < 0.5;
  return (
    <div
      className={`sign-card ${isSelected ? "selected" : ""} ${isCritical ? "critical" : ""}`}
      onClick={() => onSelect(record._id)}
      style={{ position: "relative" }}
    >
      <div className="sign-card-header">
        <span className="sign-type-name">{record.sign_type}</span>
        <button className="resolve-btn" onClick={(e) => { e.stopPropagation(); onResolve(record._id); }}>
          Resolve
        </button>
      </div>
      <div className="sign-meta">
        ID: {record.sign_id || "—"} • {new Date(record.timestamp).toLocaleTimeString()}
      </div>
      <div className="sign-stats">
        <span className="weber-score" style={{ color: cfg.hex }}>
          Weber: {typeof record.reflectivity_score === "number" ? record.reflectivity_score.toFixed(2) : "—"}
        </span>
        <span className="status-pill" style={{
          background: `${cfg.hex}15`, color: cfg.hex, border: `1px solid ${cfg.hex}40`
        }}>
          {record.status}
        </span>
      </div>
      <div className="sign-details-row">
        <span className="detail-chip">🎯 {record.confidence ? (record.confidence * 100).toFixed(0) + "%" : "—"}</span>
        <span className="detail-chip">{record.lighting === "night" ? "🌙" : "☀️"} {record.lighting || "day"}</span>
        {record.months_remaining != null && (
          <span className="detail-chip">⏳ {record.months_remaining}mo</span>
        )}
      </div>
    </div>
  );
}

export function ChatBubble({ role, text, meta, onPlayTTS }) {
  const isUser = role === "user";
  return (
    <div className={`chat-bubble ${isUser ? "user" : "ai"}`}>
      <div className="chat-role">{isUser ? "👤 You" : "🤖 AI Assistant"}</div>
      <div className="chat-text">{text}</div>
      {meta && (
        <div className="chat-meta">
          {meta.lang && <span className="ai-badge lang">{meta.langFlag} {meta.lang}</span>}
          {meta.cached && <span className="ai-badge cached">⚡ Cached</span>}
          {meta.time && <span className="ai-badge time">⏱ {meta.time}ms</span>}
          {meta.ttsUrl && (
            <button className="tts-btn" onClick={onPlayTTS}>🔊 Play</button>
          )}
        </div>
      )}
    </div>
  );
}

export function DonutChart({ passCount, failCount }) {
  const total = passCount + failCount;
  const passRate = total > 0 ? Math.round((passCount / total) * 100) : 0;
  const deg = total > 0 ? (passCount / total) * 360 : 0;
  return (
    <div className="donut-container">
      <div className="donut-ring" style={{
        background: `conic-gradient(#10b981 0deg ${deg}deg, #ef4444 ${deg}deg 360deg)`
      }}>
        <div className="donut-center">{passRate}%</div>
      </div>
      <div className="donut-legend">
        <div className="legend-item"><span className="legend-dot" style={{ background: "#10b981" }}></span> Pass: {passCount}</div>
        <div className="legend-item"><span className="legend-dot" style={{ background: "#ef4444" }}></span> Fail: {failCount}</div>
        <div className="legend-item" style={{ color: "#64748b", fontSize: 10 }}>Total: {total}</div>
      </div>
    </div>
  );
}

export function BarChart({ items, color }) {
  if (!items || items.length === 0) return <div className="empty-state">No data</div>;
  const maxVal = Math.max(...items.map(i => i.count), 1);
  return (
    <div className="bar-chart">
      {items.slice(0, 8).map((item, idx) => (
        <div className="bar-row" key={idx}>
          <span className="bar-label">{item.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{
              width: `${(item.count / maxVal) * 100}%`,
              background: color || "var(--accent-cyan)"
            }}></div>
          </div>
          <span className="bar-count">{item.count}</span>
        </div>
      ))}
    </div>
  );
}

export function QueryHistoryTable({ queries }) {
  if (!queries || queries.length === 0) return <div className="empty-state"><div className="empty-icon">📋</div>No queries yet</div>;
  return (
    <table className="history-table">
      <thead>
        <tr><th>Query</th><th>Lang</th><th>Time</th><th>Via</th></tr>
      </thead>
      <tbody>
        {queries.slice(0, 30).map((q, i) => (
          <tr key={i}>
            <td style={{ maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {q.raw_query}
            </td>
            <td>{q.detected_lang || "—"}</td>
            <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
              {q.response_time_ms ? `${q.response_time_ms}ms` : "—"}
            </td>
            <td>{q.input_method === "voice" ? "🎙" : "⌨️"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ReportCenter({ ragBase }) {
  const reports = [
    { icon: "📄", label: "PDF Report", url: `${ragBase}/download/report` },
    { icon: "🗺️", label: "Heatmap", url: `${ragBase}/download/heatmap` },
    { icon: "📊", label: "CSV Data", url: `${ragBase}/download/csv` },
  ];
  return (
    <div className="report-grid">
      {reports.map((r, i) => (
        <a key={i} href={r.url} target="_blank" rel="noreferrer" className="report-btn">
          <span className="report-icon">{r.icon}</span>
          {r.label}
        </a>
      ))}
    </div>
  );
}
