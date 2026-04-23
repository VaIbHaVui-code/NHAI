import React, { useState, useEffect, useCallback, useRef } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./HighwayDashboard.css";
import {
  STATUS_CONFIG, MetricCard, SignCard, ChatBubble,
  DonutChart, BarChart, QueryHistoryTable, ReportCenter
} from "./DashboardComponents";

const API_BASE = "http://127.0.0.1:5000/api";
const RAG_API_BASE = "http://127.0.0.1:5002/api";
const RAG_ROOT = "http://127.0.0.1:5002";
const POLL_MS = 3000;

function MapFollower({ selectedPos }) {
  const map = useMap();
  useEffect(() => {
    if (selectedPos) map.setView(selectedPos, 17, { animate: true });
  }, [selectedPos, map]);
  return null;
}

export default function HighwayDashboard({ onNavigate }) {
  const [records, setRecords] = useState([]);
  const [filteredRecords, setFilteredRecords] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [textQuery, setTextQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState(null);
  const [activeTab, setActiveTab] = useState("feed");
  const [chatHistory, setChatHistory] = useState([]);
  const [healthData, setHealthData] = useState(null);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [queryHistory, setQueryHistory] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [selectedLang, setSelectedLang] = useState("en");
  const [confirmMsg, setConfirmMsg] = useState(null);
  const chatEndRef = useRef(null);

  // Poll sign data
  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/signs`);
      const data = await res.json();
      const r = data.records || [];
      setRecords(r);
      if (!activeFilter) setFilteredRecords(r);
      setLoading(false);
    } catch (e) { console.error("Backend offline"); }
  }, [activeFilter]);

  useEffect(() => { fetchData(); const iv = setInterval(fetchData, POLL_MS); return () => clearInterval(iv); }, [fetchData]);

  // Fetch health
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${RAG_ROOT}/health`);
        setHealthData(await res.json());
      } catch (e) {}
    };
    fetchHealth();
    const iv = setInterval(fetchHealth, 15000);
    return () => clearInterval(iv);
  }, []);

  // Fetch analytics
  useEffect(() => {
    if (activeTab !== "analytics") return;
    (async () => {
      try {
        const res = await fetch(`${RAG_API_BASE}/analytics`);
        setAnalyticsData(await res.json());
      } catch (e) {}
    })();
  }, [activeTab]);

  // Fetch query history
  useEffect(() => {
    if (activeTab !== "history") return;
    (async () => {
      try {
        const res = await fetch(`${RAG_API_BASE}/query-history?limit=50`);
        const d = await res.json();
        setQueryHistory(d.queries || []);
      } catch (e) {}
    })();
  }, [activeTab]);

  // Fetch languages
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${RAG_API_BASE}/languages`);
        const d = await res.json();
        setLanguages(d.languages || []);
      } catch (e) {}
    })();
  }, []);

  // Scroll chat
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatHistory]);

  // Apply AI filter
  const applyAIResult = useCallback((data) => {
    const q = data.mongo_query;
    if (!q || Object.keys(q).length === 0) {
      setFilteredRecords(records);
      setActiveFilter(null);
      return;
    }
    const filtered = records.filter((rec) => {
      for (const key in q) {
        const val = q[key];
        if (typeof val === "object" && val.$in) {
          if (!val.$in.includes(rec[key])) return false;
        } else if (rec[key] !== val) return false;
      }
      return true;
    });
    setFilteredRecords(filtered);
    setActiveFilter(data.ui_message);
  }, [records]);

  // Text search
  const handleTextSearch = async () => {
    if (!textQuery.trim()) return;
    const query = textQuery;
    setTextQuery("");
    setChatHistory(prev => [...prev, { role: "user", text: query }]);
    try {
      const res = await fetch(`${RAG_API_BASE}/rag-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, session_id: "dashboard", want_audio: false }),
      });
      const data = await res.json();
      if (data.error) {
        setChatHistory(prev => [...prev, { role: "ai", text: data.error.message, meta: {} }]);
        return;
      }
      applyAIResult(data);
      const badge = data.language_badge || {};
      setChatHistory(prev => [...prev, {
        role: "ai", text: data.ui_message || "Query processed.",
        meta: {
          lang: badge.name, langFlag: badge.flag,
          cached: data.cached, time: data.response_time_ms,
          ttsUrl: data.tts_audio_url,
        }
      }]);
    } catch (e) {
      setChatHistory(prev => [...prev, { role: "ai", text: "RAG server offline.", meta: {} }]);
    }
  };

  // Voice search
  const handleVoiceSearch = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setChatHistory(prev => [...prev, { role: "ai", text: "Speech recognition not supported in this browser." }]);
      return;
    }
    const recognition = new SR();
    recognition.lang = selectedLang === "hi" ? "hi-IN" : selectedLang === "mr" ? "mr-IN" : "en-IN";
    setIsListening(true);
    recognition.onresult = async (event) => {
      const transcript = event.results[0][0].transcript;
      setIsListening(false);
      setChatHistory(prev => [...prev, { role: "user", text: `🎙 ${transcript}` }]);
      try {
        const res = await fetch(`${RAG_API_BASE}/rag-query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: transcript, session_id: "dashboard", want_audio: true }),
        });
        const data = await res.json();
        if (data.error) {
          setChatHistory(prev => [...prev, { role: "ai", text: data.error.message }]);
          return;
        }
        applyAIResult(data);
        const badge = data.language_badge || {};
        setChatHistory(prev => [...prev, {
          role: "ai", text: data.ui_message || "Processed.",
          meta: {
            lang: badge.name, langFlag: badge.flag,
            cached: data.cached, time: data.response_time_ms,
            ttsUrl: data.tts_audio_url,
          }
        }]);
        if (data.tts_audio_url) {
          new Audio(`${RAG_ROOT}${data.tts_audio_url}`).play().catch(() => {});
        }
      } catch (e) {
        setIsListening(false);
        setChatHistory(prev => [...prev, { role: "ai", text: "Voice query failed." }]);
      }
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognition.start();
  };

  // Resolve sign
  const markDone = async (id) => {
    try {
      await fetch(`${API_BASE}/signs/${id}`, { method: "DELETE" });
      setRecords(prev => prev.filter(r => r._id !== id));
      setFilteredRecords(prev => prev.filter(r => r._id !== id));
      if (selectedId === id) setSelectedId(null);
      setConfirmMsg("Sign resolved successfully.");
      setTimeout(() => setConfirmMsg(null), 3000);
    } catch (e) {
      setConfirmMsg("Failed to resolve sign.");
      setTimeout(() => setConfirmMsg(null), 3000);
    }
  };

  // Play TTS
  const playTTS = (url) => {
    if (url) new Audio(`${RAG_ROOT}${url}`).play().catch(() => {});
  };

  // Computed values
  const selectedRecord = filteredRecords.find(r => r._id === selectedId);
  const passCount = filteredRecords.filter(r => r.status === "Pass").length;
  const failCount = filteredRecords.filter(r => r.status === "Fail").length;
  const totalCount = filteredRecords.length;
  const avgConf = totalCount > 0 ? (filteredRecords.reduce((a, r) => a + (r.confidence || 0), 0) / totalCount * 100).toFixed(1) : "—";
  const uptime = healthData ? `${Math.floor(healthData.uptime_seconds / 60)}m` : "—";

  // Analytics derived
  const langBars = (analyticsData?.language_distribution || []).map(l => ({ label: `${l.flag} ${l.name}`, count: l.count }));
  const signTypeBars = (analyticsData?.top_sign_types || []).map(s => ({ label: s.sign_type, count: s.count }));

  const tabs = [
    { id: "feed", label: "Live Feed" },
    { id: "chat", label: "AI Chat" },
    { id: "analytics", label: "Analytics" },
    { id: "history", label: "History" },
    { id: "reports", label: "Reports" },
  ];

  return (
    <div className="dashboard-root">
      {/* ═══ SIDEBAR ═══ */}
      <aside className="sidebar">
        <div className="sidebar-header" style={{ position: "relative" }}>
          <div className="sidebar-brand">
            <span className="brand-icon">🛡️</span>
            <h2>NHAI AI COMMAND</h2>
          </div>
          <button 
            onClick={() => onNavigate && onNavigate("admin")}
            style={{ position: "absolute", top: 18, right: 20, background: "transparent", border: "1px solid var(--border-bright)", color: "var(--accent-cyan)", padding: "4px 8px", borderRadius: "6px", cursor: "pointer", fontSize: "10px", fontWeight: "bold" }}
          >
            ⚙️ ADMIN
          </button>
          <div className="system-status">
            <div className={`status-dot ${healthData?.status === "ok" ? "" : "offline"}`}></div>
            <span>System {healthData?.status === "ok" ? "Live" : "Connecting..."} • {healthData?.active_sessions || 0} sessions</span>
          </div>

          <button className={`voice-btn ${isListening ? "listening" : "idle"}`} onClick={handleVoiceSearch}>
            {isListening ? "🎙️ Listening..." : "🎙️ Voice Command"}
          </button>

          <div className="search-row">
            <input
              className="search-input"
              type="text"
              value={textQuery}
              onChange={e => setTextQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleTextSearch()}
              placeholder="Ask AI (e.g. 'Show failed signs')"
            />
            <button className="send-btn" onClick={handleTextSearch}>SEND</button>
          </div>

          {languages.length > 0 && (
            <select className="lang-selector" value={selectedLang} onChange={e => setSelectedLang(e.target.value)}>
              {languages.map(l => (
                <option key={l.code} value={l.code}>{l.flag} {l.name} ({l.native_name})</option>
              ))}
            </select>
          )}

          {activeFilter && (
            <div className="ai-response-panel">
              <p className="ai-msg">🤖 {activeFilter}</p>
              <div className="ai-meta">
                <span className="ai-badge cached">Filtered: {filteredRecords.length} results</span>
              </div>
              <button className="reset-filter-btn" onClick={() => applyAIResult({})}>Reset Filter</button>
            </div>
          )}
        </div>

        {/* Sidebar Metrics */}
        <div style={{ padding: "12px 22px", borderBottom: "1px solid var(--border-dim)" }}>
          <div className="section-label">Engine Performance</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <div className="analytics-card">
              <div className="card-label">RAG Latency</div>
              <div className="card-value" style={{ color: "var(--accent-blue)", fontSize: 15 }}>
                {analyticsData?.avg_response_time_ms ? `${Math.round(analyticsData.avg_response_time_ms)}ms` : "—"}
              </div>
            </div>
            <div className="analytics-card">
              <div className="card-label">YOLO Avg Conf</div>
              <div className="card-value" style={{ color: "var(--accent-emerald)", fontSize: 15 }}>
                {avgConf}%
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar Feed */}
        <div className="sidebar-feed">
          <div className="section-label">Live Inspection Feed</div>
          {confirmMsg && <div className="confirm-banner">✓ {confirmMsg}</div>}
          {filteredRecords.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📡</div>
              {loading ? "Establishing uplink..." : "No records match filters."}
            </div>
          ) : (
            filteredRecords.slice(0, 50).map(record => (
              <SignCard
                key={record._id}
                record={record}
                isSelected={selectedId === record._id}
                onSelect={setSelectedId}
                onResolve={markDone}
              />
            ))
          )}
        </div>
      </aside>

      {/* ═══ CENTER ═══ */}
      <div className="center-content">
        {/* Top Metrics Bar */}
        <div className="metrics-bar">
          <MetricCard label="Total Signs" value={totalCount} color="var(--accent-cyan)" sub="detected" delay={0} />
          <MetricCard label="Pass Rate" value={totalCount > 0 ? `${Math.round(passCount / totalCount * 100)}%` : "—"} color="var(--accent-emerald)" sub={`${passCount} passed`} delay={50} />
          <MetricCard label="Failed" value={failCount} color="var(--accent-red)" sub="need attention" delay={100} />
          <MetricCard label="LLM Status" value={healthData?.llm_reachable ? "Online" : "Offline"} color={healthData?.llm_reachable ? "var(--accent-emerald)" : "var(--accent-red)"} sub="Groq Llama 3.1" delay={150} />
          <MetricCard label="Cache Hit" value={healthData?.cache_stats?.hit_rate_percent != null ? `${healthData.cache_stats.hit_rate_percent}%` : "—"} color="var(--accent-purple)" sub={`${healthData?.cache_stats?.size || 0} cached`} delay={200} />
          <MetricCard label="Uptime" value={uptime} color="var(--accent-amber)" sub="RAG server" delay={250} />
        </div>

        {/* Map */}
        <div className="map-container">
          <MapContainer center={[23.0225, 72.5714]} zoom={13} style={{ height: "100%", width: "100%" }} zoomControl={false}>
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
            <MapFollower selectedPos={selectedRecord ? [selectedRecord.gps.lat, selectedRecord.gps.lng] : null} />
            {filteredRecords.map(record => {
              const cfg = STATUS_CONFIG[record.status] || { hex: "#94a3b8" };
              const isSel = selectedId === record._id;
              return (
                <CircleMarker
                  key={record._id}
                  center={[record.gps.lat, record.gps.lng]}
                  radius={isSel ? 14 : 7}
                  pathOptions={{ color: cfg.hex, fillColor: cfg.hex, fillOpacity: 0.8, weight: isSel ? 3 : 2 }}
                  eventHandlers={{ click: () => setSelectedId(record._id) }}
                >
                  <Popup>
                    <div style={{ minWidth: 180, color: "#f1f5f9" }}>
                      <h4 style={{ margin: "0 0 6px", textTransform: "capitalize", fontSize: 14 }}>{record.sign_type}</h4>
                      <p style={{ margin: "2px 0", fontSize: 11 }}>Status: <b style={{ color: cfg.hex }}>{record.status}</b></p>
                      <p style={{ margin: "2px 0", fontSize: 11 }}>Confidence: {record.confidence ? (record.confidence * 100).toFixed(1) + "%" : "—"}</p>
                      <p style={{ margin: "2px 0", fontSize: 11 }}>Weber CR: {typeof record.reflectivity_score === "number" ? record.reflectivity_score.toFixed(3) : "—"}</p>
                      <p style={{ margin: "2px 0", fontSize: 11 }}>Lighting: {record.lighting || "day"}</p>
                      <p style={{ margin: "2px 0", fontSize: 11 }}>Months Left: {record.months_remaining ?? "—"}</p>
                      <p style={{ margin: "2px 0", fontSize: 11, color: "#94a3b8" }}>
                        GPS: {record.gps.lat.toFixed(4)}, {record.gps.lng.toFixed(4)}
                      </p>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>

        {/* Bottom Status Bar */}
        <div className="status-bar">
          <div className="status-bar-item"><span className="dot-live"></span> Connected</div>
          <div className="status-bar-item">Records: {records.length}</div>
          <div className="status-bar-item">Filtered: {filteredRecords.length}</div>
          {healthData && <div className="status-bar-item">Sessions: {healthData.active_sessions}</div>}
          {healthData && <div className="status-bar-item">Cache: {healthData.cache_stats?.size || 0}/{healthData.cache_stats?.max_size || 200}</div>}
          <div className="status-bar-item" style={{ marginLeft: "auto" }}>
            Last: {new Date().toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* ═══ RIGHT PANEL ═══ */}
      <div className="right-panel">
        <div className="tab-bar">
          {tabs.map(t => (
            <button key={t.id} className={`tab-btn ${activeTab === t.id ? "active" : ""}`} onClick={() => setActiveTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>

        <div className="tab-content">
          {/* ── Tab: Live Feed ── */}
          {activeTab === "feed" && (
            <>
              <div className="section-label">Recent Detections</div>
              {filteredRecords.length === 0 ? (
                <div className="empty-state"><div className="empty-icon">📡</div>No detections</div>
              ) : (
                filteredRecords.slice(0, 30).map(record => (
                  <SignCard key={record._id} record={record} isSelected={selectedId === record._id} onSelect={setSelectedId} onResolve={markDone} />
                ))
              )}
            </>
          )}

          {/* ── Tab: AI Chat ── */}
          {activeTab === "chat" && (
            <>
              <div className="section-label">Conversation</div>
              {chatHistory.length === 0 ? (
                <div className="empty-state"><div className="empty-icon">💬</div>Start a conversation using the search bar or voice command</div>
              ) : (
                chatHistory.map((msg, i) => (
                  <ChatBubble key={i} role={msg.role} text={msg.text} meta={msg.meta} onPlayTTS={() => playTTS(msg.meta?.ttsUrl)} />
                ))
              )}
              <div ref={chatEndRef} />
            </>
          )}

          {/* ── Tab: Analytics ── */}
          {activeTab === "analytics" && (
            <>
              <div className="section-label">Sign Status Distribution</div>
              <DonutChart passCount={passCount} failCount={failCount} />

              <div className="section-label" style={{ marginTop: 16 }}>Query Statistics</div>
              <div className="analytics-grid">
                <div className="analytics-card">
                  <div className="card-label">Total Queries</div>
                  <div className="card-value" style={{ color: "var(--accent-cyan)" }}>{analyticsData?.total_queries ?? "—"}</div>
                </div>
                <div className="analytics-card">
                  <div className="card-label">Avg Response</div>
                  <div className="card-value" style={{ color: "var(--accent-blue)" }}>
                    {analyticsData?.avg_response_time_ms ? `${Math.round(analyticsData.avg_response_time_ms)}ms` : "—"}
                  </div>
                </div>
                <div className="analytics-card">
                  <div className="card-label">Cache Ratio</div>
                  <div className="card-value" style={{ color: "var(--accent-emerald)" }}>
                    {analyticsData?.cache_hit_ratio_percent != null ? `${analyticsData.cache_hit_ratio_percent}%` : "—"}
                  </div>
                </div>
                <div className="analytics-card">
                  <div className="card-label">Languages</div>
                  <div className="card-value" style={{ color: "var(--accent-purple)" }}>{languages.length}</div>
                </div>
              </div>

              {langBars.length > 0 && (
                <>
                  <div className="section-label" style={{ marginTop: 16 }}>Language Distribution</div>
                  <BarChart items={langBars} color="var(--accent-purple)" />
                </>
              )}

              {signTypeBars.length > 0 && (
                <>
                  <div className="section-label" style={{ marginTop: 16 }}>Top Sign Types Queried</div>
                  <BarChart items={signTypeBars} color="var(--accent-cyan)" />
                </>
              )}
            </>
          )}

          {/* ── Tab: History ── */}
          {activeTab === "history" && (
            <>
              <div className="section-label">Recent RAG Queries</div>
              <QueryHistoryTable queries={queryHistory} />
            </>
          )}

          {/* ── Tab: Reports ── */}
          {activeTab === "reports" && (
            <>
              <div className="section-label">Download Reports</div>
              <ReportCenter ragBase={RAG_API_BASE} />
              <div className="section-label" style={{ marginTop: 20 }}>Features Active</div>
              {(healthData?.features || []).map((f, i) => (
                <span key={i} className="ai-badge lang" style={{ marginRight: 4, marginBottom: 4, display: "inline-block" }}>
                  ✓ {f}
                </span>
              ))}
              <div className="section-label" style={{ marginTop: 20 }}>Supported Languages</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {languages.map(l => (
                  <span key={l.code} className="ai-badge lang" style={{ display: "inline-block" }}>
                    {l.flag} {l.native_name}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}