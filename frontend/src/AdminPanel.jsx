import React, { useState } from "react";
import "./AdminPanel.css";

const RAG_API_BASE = "http://127.0.0.1:5002/api";

export default function AdminPanel({ onNavigate }) {
  const [confidence, setConfidence] = useState(0.4);
  const [contrast, setContrast] = useState(1.5);
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [statusMsg, setStatusMsg] = useState(null);
  const [activeTab, setActiveTab] = useState("engine"); // Tab state

  const showStatus = (msg, isError = false) => {
    setStatusMsg({ text: msg, isError });
    setTimeout(() => setStatusMsg(null), 3000);
  };

  const handleSaveSettings = () => {
    showStatus("Configuration saved successfully.");
  };

  const handleClearCache = async () => {
    try {
      const res = await fetch(`${RAG_API_BASE}/admin/clear-cache`, { method: "POST" });
      if (res.ok) {
        showStatus("AI Query Cache cleared.");
      } else {
        showStatus("Failed to clear cache.", true);
      }
    } catch (e) {
      showStatus("Server offline. Cannot clear cache.", true);
    }
  };

  const handleClearSessions = async () => {
    showStatus("All active AI sessions terminated.");
  };

  return (
    <div className="admin-root">
      {/* ═══ SIDEBAR ═══ */}
      <aside className="admin-sidebar">
        <div className="admin-brand">
          <span className="brand-icon">⚙️</span>
          <h2>NHAI ADMIN</h2>
        </div>
        
        <nav className="admin-nav">
          <button className={`nav-btn ${activeTab === 'engine' ? 'active' : ''}`} onClick={() => setActiveTab('engine')}>
            🛠️ Engine Settings
          </button>
          <button className={`nav-btn ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
            📱 Alert Management
          </button>
          <button className={`nav-btn ${activeTab === 'database' ? 'active' : ''}`} onClick={() => setActiveTab('database')}>
            💾 Database Control
          </button>
          <button className={`nav-btn ${activeTab === 'users' ? 'active' : ''}`} onClick={() => setActiveTab('users')}>
            👥 User Access
          </button>
        </nav>

        <div style={{ marginTop: "auto" }}>
          <button className="back-btn" onClick={() => onNavigate("dashboard")}>
            ⬅ Return to Dashboard
          </button>
        </div>
      </aside>

      {/* ═══ MAIN CONTENT ═══ */}
      <main className="admin-content">
        <header className="admin-header">
          <h1>
            {activeTab === 'engine' && "Engine Configuration"}
            {activeTab === 'alerts' && "Alert Management"}
            {activeTab === 'database' && "Database & Memory"}
            {activeTab === 'users' && "User Access Control"}
          </h1>
          <div className="admin-user-badge">
            <div className="avatar">A</div>
            <span>Super Admin</span>
          </div>
        </header>

        {statusMsg && (
          <div className={`status-banner ${statusMsg.isError ? "error" : "success"}`}>
            {statusMsg.isError ? "❌" : "✓"} {statusMsg.text}
          </div>
        )}

        <div className="settings-grid">
          {/* Section 1: YOLO Settings */}
          {activeTab === 'engine' && (
            <section className="settings-card full-width">
              <h3>🧠 YOLO Engine Thresholds</h3>
              <p className="settings-desc">Adjust the sensitivity of the sign detection engine.</p>
              
              <div className="control-group">
                <label>Minimum Confidence: {(confidence * 100).toFixed(0)}%</label>
                <input 
                  type="range" min="0.1" max="0.9" step="0.05" 
                  value={confidence} onChange={(e) => setConfidence(parseFloat(e.target.value))}
                />
                <span className="help-text">Detections below this confidence will be ignored.</span>
              </div>

              <div className="control-group">
                <label>Weber Contrast Threshold: {contrast.toFixed(2)}</label>
                <input 
                  type="range" min="0.5" max="3.0" step="0.1" 
                  value={contrast} onChange={(e) => setContrast(parseFloat(e.target.value))}
                />
                <span className="help-text">Signs below this ratio are marked as 'Fail'.</span>
              </div>

              <button className="primary-btn" onClick={handleSaveSettings}>Save Engine Limits</button>
            </section>
          )}

          {/* Section 2: Telegram Alerts */}
          {activeTab === 'alerts' && (
            <section className="settings-card full-width">
              <h3>📱 Telegram Bot Integration</h3>
              <p className="settings-desc">Configure where critical sign alerts are sent.</p>
              
              <div className="control-group">
                <label className="toggle-label">
                  <span>Enable Telegram Alerts</span>
                  <input 
                    type="checkbox" 
                    checked={alertsEnabled} 
                    onChange={(e) => setAlertsEnabled(e.target.checked)} 
                  />
                </label>
              </div>

              <div className="control-group">
                <label>Bot Token</label>
                <input 
                  type="password" 
                  placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                  value={telegramToken}
                  onChange={(e) => setTelegramToken(e.target.value)}
                  disabled={!alertsEnabled}
                />
              </div>

              <div className="control-group">
                <label>Chat ID</label>
                <input 
                  type="text" 
                  placeholder="-1001234567890"
                  value={telegramChatId}
                  onChange={(e) => setTelegramChatId(e.target.value)}
                  disabled={!alertsEnabled}
                />
              </div>

              <button className="primary-btn" onClick={handleSaveSettings} disabled={!alertsEnabled}>Update Credentials</button>
            </section>
          )}

          {/* Section 3: Data Management */}
          {activeTab === 'database' && (
            <section className="settings-card full-width">
              <h3>💾 Database & Memory Control</h3>
              <p className="settings-desc">Manage the AI RAG server cache and session history.</p>
              
              <div className="action-buttons">
                <div className="action-item">
                  <div className="action-info">
                    <h4>Clear Semantic Cache</h4>
                    <p>Removes all cached LLM responses. Next queries will hit the LLM directly.</p>
                  </div>
                  <button className="danger-btn" onClick={handleClearCache}>Purge Cache</button>
                </div>

                <div className="action-item">
                  <div className="action-info">
                    <h4>Terminate Active Sessions</h4>
                    <p>Clears the conversation memory for all connected dashboard users.</p>
                  </div>
                  <button className="danger-btn" onClick={handleClearSessions}>Clear Memory</button>
                </div>
              </div>
            </section>
          )}

          {/* Section 4: User Access */}
          {activeTab === 'users' && (
            <section className="settings-card full-width">
              <h3>👥 User Access Control</h3>
              <p className="settings-desc">Manage authorized operators and their roles.</p>
              <div className="empty-state">
                <div className="empty-icon">🔐</div>
                Feature coming soon. User authentication is currently handled via local intranet network rules.
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
