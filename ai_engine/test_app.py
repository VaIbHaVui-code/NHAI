"""
NHAI Test Dashboard — Flask App
================================
A standalone test UI for all RAG + Scanning features.
Run alongside rag_server.py (port 5001).

Usage:
    1. Start RAG server:   python rag_server.py       (port 5001)
    2. Start test app:     python test_app.py          (port 5002)
    3. Open browser:       http://localhost:5002
"""

import os
import sys
import json
import glob
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_cors import CORS

# Fix Windows console Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = Flask(__name__)
CORS(app)

RAG_SERVER_URL = "http://localhost:5001"
SCANS_DIR = "scans"

# ─────────────────────────────────────────────────────────
# HTML TEMPLATE — Modern dark-themed test dashboard
# ─────────────────────────────────────────────────────────
DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NHAI AI Test Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #111827;
            --bg-card: rgba(17, 24, 39, 0.8);
            --bg-glass: rgba(255, 255, 255, 0.04);
            --border: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(99, 102, 241, 0.4);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.3);
            --success: #22c55e;
            --danger: #ef4444;
            --warning: #f59e0b;
            --info: #3b82f6;
            --radius: 12px;
            --radius-sm: 8px;
        }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }

        /* Gradient mesh background */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background:
                radial-gradient(ellipse at 20% 20%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(59, 130, 246, 0.04) 0%, transparent 60%);
            z-index: -1;
        }

        .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

        /* Header */
        .header {
            text-align: center;
            padding: 40px 0 30px;
        }
        .header h1 {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #6366f1, #8b5cf6, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        .header p { color: var(--text-secondary); font-size: 0.95rem; }

        .status-bar {
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-top: 16px;
            flex-wrap: wrap;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.82rem;
            color: var(--text-muted);
        }
        .status-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            background: var(--text-muted);
        }
        .status-dot.online { background: var(--success); box-shadow: 0 0 8px rgba(34,197,94,0.5); }
        .status-dot.offline { background: var(--danger); box-shadow: 0 0 8px rgba(239,68,68,0.5); }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 4px;
            padding: 4px;
            background: var(--bg-glass);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            margin-bottom: 24px;
            overflow-x: auto;
        }
        .tab {
            padding: 10px 20px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-muted);
            transition: all 0.2s;
            white-space: nowrap;
            border: none;
            background: none;
        }
        .tab:hover { color: var(--text-primary); background: rgba(255,255,255,0.05); }
        .tab.active {
            background: var(--accent);
            color: white;
            box-shadow: 0 2px 12px var(--accent-glow);
        }

        /* Cards */
        .card {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 20px;
            transition: border-color 0.3s;
        }
        .card:hover { border-color: var(--border-hover); }
        .card h3 {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Forms */
        .form-group { margin-bottom: 16px; }
        .form-group label {
            display: block;
            font-size: 0.82rem;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }
        input[type="text"], textarea, select {
            width: 100%;
            padding: 10px 14px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.9rem;
            transition: border-color 0.2s;
            outline: none;
        }
        input:focus, textarea:focus, select:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        textarea { resize: vertical; min-height: 80px; }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 20px;
            border-radius: var(--radius-sm);
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            font-family: inherit;
        }
        .btn-primary {
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: white;
            box-shadow: 0 2px 12px var(--accent-glow);
        }
        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px var(--accent-glow);
        }
        .btn-secondary {
            background: rgba(255,255,255,0.06);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover { background: rgba(255,255,255,0.1); color: var(--text-primary); }
        .btn-danger {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
        }
        .btn-success {
            background: linear-gradient(135deg, #22c55e, #16a34a);
            color: white;
        }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        .btn-group { display: flex; gap: 8px; flex-wrap: wrap; }

        /* Response box */
        .response-box {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 16px;
            margin-top: 16px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .response-box.success { border-color: rgba(34, 197, 94, 0.3); }
        .response-box.error { border-color: rgba(239, 68, 68, 0.3); }

        /* Badge */
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-pass { background: rgba(34,197,94,0.15); color: #4ade80; }
        .badge-fail { background: rgba(239,68,68,0.15); color: #f87171; }
        .badge-cached { background: rgba(99,102,241,0.15); color: #a5b4fc; }
        .badge-lang { background: rgba(59,130,246,0.15); color: #93c5fd; }

        /* Stats grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: var(--bg-glass);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 16px;
            text-align: center;
        }
        .stat-card .value {
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, #6366f1, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .label {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 4px;
        }

        /* Table */
        .table-wrap { overflow-x: auto; }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
        }
        th, td {
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th {
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        tr:hover td { background: rgba(255,255,255,0.02); }

        /* Recording indicator */
        .recording-indicator {
            display: none;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: var(--radius-sm);
            color: #f87171;
            font-size: 0.85rem;
            margin-top: 12px;
        }
        .recording-indicator.active { display: flex; }
        .recording-dot {
            width: 10px; height: 10px;
            background: #ef4444;
            border-radius: 50%;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        /* Audio player */
        audio {
            width: 100%;
            margin-top: 12px;
            border-radius: var(--radius-sm);
        }

        /* Sections */
        .section { display: none; }
        .section.active { display: block; }

        /* Grid layout */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        @media (max-width: 768px) {
            .grid-2 { grid-template-columns: 1fr; }
            .tabs { gap: 2px; }
            .tab { padding: 8px 12px; font-size: 0.78rem; }
        }

        /* File list */
        .file-list { list-style: none; }
        .file-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            margin-bottom: 8px;
            transition: background 0.2s;
        }
        .file-item:hover { background: rgba(255,255,255,0.03); }
        .file-name {
            font-size: 0.85rem;
            font-weight: 500;
        }
        .file-meta {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        /* Loading spinner */
        .spinner {
            width: 16px; height: 16px;
            border: 2px solid rgba(255,255,255,0.2);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
            display: none;
        }
        .spinner.active { display: inline-block; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Language grid */
        .lang-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }
        .lang-card {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px;
            background: var(--bg-glass);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
        }
        .lang-flag { font-size: 1.5rem; }
        .lang-info .lang-name { font-weight: 600; font-size: 0.85rem; }
        .lang-info .lang-native { font-size: 0.78rem; color: var(--text-muted); }
        .lang-info .lang-code {
            font-size: 0.7rem;
            color: var(--accent);
            font-family: monospace;
        }

        .toast {
            position: fixed; bottom: 24px; right: 24px;
            padding: 12px 20px;
            border-radius: var(--radius-sm);
            font-size: 0.85rem;
            z-index: 1000;
            animation: slideIn 0.3s;
            display: none;
        }
        .toast.show { display: block; }
        .toast.success { background: rgba(34,197,94,0.9); color: white; }
        .toast.error { background: rgba(239,68,68,0.9); color: white; }
        @keyframes slideIn { from { transform: translateX(100px); opacity:0; } }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🛣️ NHAI AI Test Dashboard</h1>
            <p>Test all RAG, Voice, TTS, and Scanning features before connecting to MERN</p>
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-dot" id="ragStatus"></div>
                    <span>RAG Server (5001)</span>
                </div>
                <div class="status-item">
                    <div class="status-dot" id="llmStatus"></div>
                    <span>LLM (OpenAI)</span>
                </div>
                <div class="status-item" id="uptimeItem">
                    <span>⏱️ Uptime: <span id="uptimeVal">--</span></span>
                </div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tabs" role="tablist">
            <button class="tab active" onclick="switchTab('text-query')">💬 Text Query</button>
            <button class="tab" onclick="switchTab('voice-query')">🎙️ Voice Query</button>
            <button class="tab" onclick="switchTab('tts')">🔊 TTS</button>
            <button class="tab" onclick="switchTab('languages')">🌐 Languages</button>
            <button class="tab" onclick="switchTab('history')">📋 History</button>
            <button class="tab" onclick="switchTab('analytics')">📊 Analytics</button>
            <button class="tab" onclick="switchTab('scans')">📡 Scan Results</button>
            <button class="tab" onclick="switchTab('health')">❤️ Health</button>
        </div>

        <!-- ═══════════ TEXT QUERY ═══════════ -->
        <div class="section active" id="section-text-query">
            <div class="grid-2">
                <div class="card">
                    <h3>💬 Text RAG Query</h3>
                    <div class="form-group">
                        <label>Session ID</label>
                        <input type="text" id="textSessionId" value="test-session" placeholder="Session identifier">
                    </div>
                    <div class="form-group">
                        <label>Query (English, Hindi, or any Indian language)</label>
                        <textarea id="textQuery" placeholder="e.g., Show me all failed signs&#10;e.g., असफल चिन्ह दिखाओ&#10;e.g., विफल संकेतों को दिखाएं"></textarea>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="wantAudio" style="margin-right: 6px;">
                            Also generate TTS audio response
                        </label>
                    </div>
                    <div class="btn-group">
                        <button class="btn btn-primary" id="btnTextQuery" onclick="sendTextQuery()">
                            <span class="spinner" id="textSpinner"></span>
                            Send Query
                        </button>
                        <button class="btn btn-secondary" onclick="document.getElementById('textQuery').value=''">Clear</button>
                    </div>
                    <div class="btn-group" style="margin-top: 10px;">
                        <button class="btn btn-secondary" onclick="setQuery('Show all failed signs')">🇬🇧 English</button>
                        <button class="btn btn-secondary" onclick="setQuery('सभी असफल चिन्ह दिखाओ')">🇮🇳 Hindi</button>
                        <button class="btn btn-secondary" onclick="setQuery('అన్ని విఫలమైన సంకేతాలను చూపించు')">🇮🇳 Telugu</button>
                        <button class="btn btn-secondary" onclick="setQuery('தோல்வியடைந்த அடையாளங்களை காட்டு')">🇮🇳 Tamil</button>
                    </div>
                </div>
                <div class="card">
                    <h3>📤 Response</h3>
                    <div id="textResponseMeta"></div>
                    <div class="response-box" id="textResponse">Send a query to see the response here...</div>
                    <div id="textAudioPlayer"></div>
                </div>
            </div>
        </div>

        <!-- ═══════════ VOICE QUERY ═══════════ -->
        <div class="section" id="section-voice-query">
            <div class="grid-2">
                <div class="card">
                    <h3>🎙️ Voice Query (Record or Upload)</h3>
                    <div class="form-group">
                        <label>Session ID</label>
                        <input type="text" id="voiceSessionId" value="voice-session" placeholder="Session identifier">
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-danger" id="btnRecord" onclick="toggleRecording()">
                            🎙️ Start Recording
                        </button>
                        <button class="btn btn-secondary" onclick="document.getElementById('audioUpload').click()">
                            📁 Upload Audio
                        </button>
                        <input type="file" id="audioUpload" accept=".wav,.mp3,.m4a,.ogg,.webm,.flac"
                               style="display:none" onchange="uploadAudio(this)">
                    </div>

                    <div class="recording-indicator" id="recordingIndicator">
                        <div class="recording-dot"></div>
                        <span>Recording... <span id="recordTimer">0s</span></span>
                    </div>

                    <div id="recordedAudioPreview" style="margin-top: 12px;"></div>
                </div>
                <div class="card">
                    <h3>📤 Voice Response</h3>
                    <div id="voiceResponseMeta"></div>
                    <div class="response-box" id="voiceResponse">Record or upload audio to see transcription and response...</div>
                    <div id="voiceAudioPlayer"></div>
                </div>
            </div>
        </div>

        <!-- ═══════════ TTS ═══════════ -->
        <div class="section" id="section-tts">
            <div class="card">
                <h3>🔊 Text-to-Speech Generator</h3>
                <div class="grid-2">
                    <div>
                        <div class="form-group">
                            <label>Text to speak</label>
                            <textarea id="ttsText" placeholder="Enter text in any language..."></textarea>
                        </div>
                        <div class="form-group">
                            <label>Language</label>
                            <select id="ttsLang">
                                <option value="en">English</option>
                                <option value="hi">Hindi (हिन्दी)</option>
                                <option value="mr">Marathi (मराठी)</option>
                                <option value="ta">Tamil (தமிழ்)</option>
                                <option value="te">Telugu (తెలుగు)</option>
                                <option value="kn">Kannada (ಕನ್ನಡ)</option>
                                <option value="ml">Malayalam (മലയാളം)</option>
                                <option value="bn">Bengali (বাংলা)</option>
                                <option value="gu">Gujarati (ગુજરાતી)</option>
                                <option value="pa">Punjabi (ਪੰਜਾਬੀ)</option>
                                <option value="ur">Urdu (اردو)</option>
                            </select>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-primary" onclick="generateTTS()">
                                <span class="spinner" id="ttsSpinner"></span>
                                🔊 Generate Speech
                            </button>
                            <button class="btn btn-secondary" onclick="setTTSText('यह एक सड़क चिन्ह निरीक्षण प्रणाली है', 'hi')">Hindi Sample</button>
                            <button class="btn btn-secondary" onclick="setTTSText('This is the NHAI road sign inspection system', 'en')">English Sample</button>
                        </div>
                    </div>
                    <div>
                        <div id="ttsResult" class="response-box">Generated audio will appear here...</div>
                        <div id="ttsAudioPlayer"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ═══════════ LANGUAGES ═══════════ -->
        <div class="section" id="section-languages">
            <div class="card">
                <h3>🌐 Supported Languages</h3>
                <div class="lang-grid" id="langGrid">Loading...</div>
            </div>
        </div>

        <!-- ═══════════ HISTORY ═══════════ -->
        <div class="section" id="section-history">
            <div class="card">
                <h3>📋 Query History</h3>
                <div class="btn-group" style="margin-bottom: 16px;">
                    <button class="btn btn-primary" onclick="loadHistory()">🔄 Refresh</button>
                    <button class="btn btn-secondary" onclick="loadHistory('voice')">🎙️ Voice Only</button>
                    <button class="btn btn-secondary" onclick="loadHistory('text')">💬 Text Only</button>
                    <select id="historyLimit" style="width: auto; padding: 8px 12px;" onchange="loadHistory()">
                        <option value="10">Last 10</option>
                        <option value="25" selected>Last 25</option>
                        <option value="50">Last 50</option>
                    </select>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Query</th>
                                <th>Language</th>
                                <th>Method</th>
                                <th>Cached</th>
                                <th>Response Time</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody id="historyTable">
                            <tr><td colspan="7" style="text-align:center; color:var(--text-muted)">Click refresh to load</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ═══════════ ANALYTICS ═══════════ -->
        <div class="section" id="section-analytics">
            <div class="card">
                <h3>📊 Analytics Dashboard</h3>
                <button class="btn btn-primary" onclick="loadAnalytics()" style="margin-bottom: 16px;">🔄 Load Analytics</button>
                <div class="stats-grid" id="analyticsStats">
                    <div class="stat-card"><div class="value">--</div><div class="label">Total Queries</div></div>
                    <div class="stat-card"><div class="value">--</div><div class="label">Avg Response (ms)</div></div>
                    <div class="stat-card"><div class="value">--</div><div class="label">Cache Hit Rate</div></div>
                    <div class="stat-card"><div class="value">--</div><div class="label">Languages Used</div></div>
                </div>
                <div class="grid-2">
                    <div>
                        <h4 style="margin-bottom: 12px; color: var(--text-secondary);">Language Distribution</h4>
                        <div id="langDist" class="response-box">Load analytics to see data...</div>
                    </div>
                    <div>
                        <h4 style="margin-bottom: 12px; color: var(--text-secondary);">Top Sign Types Queried</h4>
                        <div id="signTypeDist" class="response-box">Load analytics to see data...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ═══════════ SCAN RESULTS ═══════════ -->
        <div class="section" id="section-scans">
            <div class="card">
                <h3>📡 Scan Results (from scanning_YOLO.py)</h3>
                <button class="btn btn-primary" onclick="loadScanFiles()" style="margin-bottom: 16px;">🔄 Refresh Files</button>
                <div class="grid-2">
                    <div>
                        <h4 style="margin-bottom: 12px; color: var(--text-secondary);">📁 Scan Files</h4>
                        <ul class="file-list" id="scanFileList">
                            <li class="file-item"><span class="file-name" style="color:var(--text-muted)">Click refresh to scan directory</span></li>
                        </ul>
                    </div>
                    <div>
                        <h4 style="margin-bottom: 12px; color: var(--text-secondary);">📄 File Preview</h4>
                        <div class="response-box" id="scanPreview" style="max-height: 500px;">Select a file to preview...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ═══════════ HEALTH ═══════════ -->
        <div class="section" id="section-health">
            <div class="card">
                <h3>❤️ System Health Check</h3>
                <button class="btn btn-primary" onclick="checkHealth()" style="margin-bottom: 16px;">
                    <span class="spinner" id="healthSpinner"></span>
                    🔄 Check Health
                </button>
                <div class="response-box" id="healthResponse">Click to check system health...</div>
            </div>
            <div class="card">
                <h3>🧪 Active Sessions</h3>
                <button class="btn btn-primary" onclick="loadSessions()" style="margin-bottom: 16px;">🔄 Load Sessions</button>
                <div id="sessionsList" class="response-box">Click to view active sessions...</div>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div class="toast" id="toast"></div>

    <script>
        const RAG_URL = '/proxy';

        // ─── Tab Switching ───
        function switchTab(name) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(`section-${name}`).classList.add('active');
            event.target.classList.add('active');

            // Auto-load data for certain tabs
            if (name === 'languages') loadLanguages();
            if (name === 'health') checkHealth();
        }

        // ─── Toast ───
        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = `toast show ${type}`;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        // ─── API helper ───
        async function api(endpoint, options = {}) {
            try {
                const res = await fetch(`${RAG_URL}${endpoint}`, options);
                const data = await res.json();
                return { data, status: res.status, ok: res.ok };
            } catch (e) {
                return { data: { error: { message: e.message } }, status: 0, ok: false };
            }
        }

        // ─── Utility ───
        function setQuery(text) {
            document.getElementById('textQuery').value = text;
        }
        function setTTSText(text, lang) {
            document.getElementById('ttsText').value = text;
            document.getElementById('ttsLang').value = lang;
        }
        function formatJSON(obj) {
            return JSON.stringify(obj, null, 2);
        }

        // ─── TEXT QUERY ───
        async function sendTextQuery() {
            const query = document.getElementById('textQuery').value.trim();
            const sessionId = document.getElementById('textSessionId').value.trim();
            const wantAudio = document.getElementById('wantAudio').checked;
            if (!query) return showToast('Enter a query first', 'error');

            const spinner = document.getElementById('textSpinner');
            const btn = document.getElementById('btnTextQuery');
            spinner.classList.add('active');
            btn.disabled = true;

            const { data, ok } = await api('/api/rag-query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, session_id: sessionId, want_audio: wantAudio })
            });

            spinner.classList.remove('active');
            btn.disabled = false;

            const responseBox = document.getElementById('textResponse');
            responseBox.textContent = formatJSON(data);
            responseBox.className = `response-box ${ok ? 'success' : 'error'}`;

            // Show metadata badges
            let meta = '';
            if (data.detected_language) {
                const badge = data.language_badge || {};
                meta += `<span class="badge badge-lang">${badge.flag || '🌐'} ${badge.name || data.detected_language}</span> `;
            }
            if (data.cached !== undefined) {
                meta += data.cached
                    ? `<span class="badge badge-cached">⚡ Cached</span> `
                    : `<span class="badge badge-pass">🤖 Fresh</span> `;
            }
            if (data.response_time_ms) {
                meta += `<span class="badge" style="background:rgba(255,255,255,0.06);color:var(--text-muted)">${data.response_time_ms}ms</span>`;
            }
            document.getElementById('textResponseMeta').innerHTML = meta;

            // TTS audio
            const audioDiv = document.getElementById('textAudioPlayer');
            if (data.tts_audio_url) {
                audioDiv.innerHTML = `<audio controls src="${RAG_URL}${data.tts_audio_url}"></audio>`;
            } else {
                audioDiv.innerHTML = '';
            }

            showToast(ok ? 'Query processed successfully' : 'Query failed', ok ? 'success' : 'error');
        }

        // ─── VOICE RECORDING ───
        let mediaRecorder = null;
        let audioChunks = [];
        let recordingTimer = null;
        let recordStartTime = 0;

        async function toggleRecording() {
            const btn = document.getElementById('btnRecord');
            const indicator = document.getElementById('recordingIndicator');

            if (mediaRecorder && mediaRecorder.state === 'recording') {
                // Stop
                mediaRecorder.stop();
                btn.textContent = '🎙️ Start Recording';
                btn.classList.remove('btn-success');
                btn.classList.add('btn-danger');
                indicator.classList.remove('active');
                clearInterval(recordingTimer);
            } else {
                // Start
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];

                    mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
                    mediaRecorder.onstop = async () => {
                        stream.getTracks().forEach(t => t.stop());
                        const blob = new Blob(audioChunks, { type: 'audio/webm' });

                        // Preview
                        const url = URL.createObjectURL(blob);
                        document.getElementById('recordedAudioPreview').innerHTML =
                            `<audio controls src="${url}"></audio>`;

                        // Send to server
                        await sendVoiceBlob(blob);
                    };

                    mediaRecorder.start();
                    recordStartTime = Date.now();
                    btn.textContent = '⏹️ Stop Recording';
                    btn.classList.remove('btn-danger');
                    btn.classList.add('btn-success');
                    indicator.classList.add('active');

                    recordingTimer = setInterval(() => {
                        const elapsed = Math.round((Date.now() - recordStartTime) / 1000);
                        document.getElementById('recordTimer').textContent = `${elapsed}s`;
                    }, 100);
                } catch (e) {
                    showToast('Microphone access denied: ' + e.message, 'error');
                }
            }
        }

        async function uploadAudio(input) {
            if (!input.files[0]) return;
            await sendVoiceBlob(input.files[0], input.files[0].name);
        }

        async function sendVoiceBlob(blob, filename = 'recording.webm') {
            const sessionId = document.getElementById('voiceSessionId').value.trim();
            const formData = new FormData();
            formData.append('audio', blob, filename);
            formData.append('session_id', sessionId);
            formData.append('want_audio', 'true');

            document.getElementById('voiceResponse').textContent = '⏳ Processing audio...';

            try {
                const res = await fetch(`${RAG_URL}/api/voice-query`, {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                document.getElementById('voiceResponse').textContent = formatJSON(data);
                document.getElementById('voiceResponse').className =
                    `response-box ${res.ok ? 'success' : 'error'}`;

                // Metadata
                let meta = '';
                if (data.transcription) {
                    meta += `<span class="badge badge-pass">📝 "${data.transcription}"</span> `;
                }
                if (data.language_badge) {
                    meta += `<span class="badge badge-lang">${data.language_badge.flag} ${data.language_badge.name}</span> `;
                }
                document.getElementById('voiceResponseMeta').innerHTML = meta;

                // TTS audio
                const audioDiv = document.getElementById('voiceAudioPlayer');
                if (data.tts_audio_url) {
                    audioDiv.innerHTML = `<audio controls autoplay src="${RAG_URL}${data.tts_audio_url}"></audio>`;
                }

                showToast(res.ok ? 'Voice query processed' : 'Voice query failed', res.ok ? 'success' : 'error');
            } catch (e) {
                document.getElementById('voiceResponse').textContent = `Error: ${e.message}`;
                showToast('Failed to process voice', 'error');
            }
        }

        // ─── TTS ───
        async function generateTTS() {
            const text = document.getElementById('ttsText').value.trim();
            const lang = document.getElementById('ttsLang').value;
            if (!text) return showToast('Enter text first', 'error');

            document.getElementById('ttsSpinner').classList.add('active');

            const { data, ok } = await api('/api/tts-generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, language: lang })
            });

            document.getElementById('ttsSpinner').classList.remove('active');
            document.getElementById('ttsResult').textContent = formatJSON(data);

            if (data.audio_url) {
                document.getElementById('ttsAudioPlayer').innerHTML =
                    `<audio controls autoplay src="${RAG_URL}${data.audio_url}"></audio>`;
                showToast('Speech generated!', 'success');
            } else {
                showToast('TTS failed', 'error');
            }
        }

        // ─── LANGUAGES ───
        async function loadLanguages() {
            const { data } = await api('/api/languages');
            const grid = document.getElementById('langGrid');
            if (data.languages) {
                grid.innerHTML = data.languages.map(l => `
                    <div class="lang-card">
                        <div class="lang-flag">${l.flag}</div>
                        <div class="lang-info">
                            <div class="lang-name">${l.name}</div>
                            <div class="lang-native">${l.native_name}</div>
                            <div class="lang-code">${l.code}</div>
                        </div>
                    </div>
                `).join('');
            }
        }

        // ─── HISTORY ───
        async function loadHistory(method = null) {
            const limit = document.getElementById('historyLimit').value;
            let url = `/api/query-history?limit=${limit}`;
            if (method) url += `&input_method=${method}`;

            const { data } = await api(url);
            const tbody = document.getElementById('historyTable');

            if (data.queries && data.queries.length > 0) {
                tbody.innerHTML = data.queries.map(q => `
                    <tr>
                        <td>${q.id}</td>
                        <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${q.raw_query}</td>
                        <td><span class="badge badge-lang">${q.detected_lang || '?'}</span></td>
                        <td>${q.input_method === 'voice' ? '🎙️' : '💬'} ${q.input_method || 'text'}</td>
                        <td>${q.cached ? '<span class="badge badge-cached">cached</span>' : '<span class="badge badge-pass">fresh</span>'}</td>
                        <td>${q.response_time_ms ? q.response_time_ms + 'ms' : '--'}</td>
                        <td style="font-size:0.75rem; color:var(--text-muted)">${q.timestamp || ''}</td>
                    </tr>
                `).join('');
                showToast(`Loaded ${data.count} queries`, 'success');
            } else {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted)">No queries found</td></tr>';
            }
        }

        // ─── ANALYTICS ───
        async function loadAnalytics() {
            const { data } = await api('/api/analytics');

            if (data.total_queries !== undefined) {
                const statsHtml = `
                    <div class="stat-card"><div class="value">${data.total_queries}</div><div class="label">Total Queries</div></div>
                    <div class="stat-card"><div class="value">${data.avg_response_time_ms}ms</div><div class="label">Avg Response</div></div>
                    <div class="stat-card"><div class="value">${data.cache_hit_ratio_percent}%</div><div class="label">Cache Hit Rate</div></div>
                    <div class="stat-card"><div class="value">${data.language_distribution ? data.language_distribution.length : 0}</div><div class="label">Languages Used</div></div>
                `;
                document.getElementById('analyticsStats').innerHTML = statsHtml;

                // Language dist
                if (data.language_distribution && data.language_distribution.length > 0) {
                    document.getElementById('langDist').textContent =
                        data.language_distribution.map(l =>
                            `${l.flag || '🌐'} ${l.name || l.code}: ${l.count} queries`
                        ).join('\n');
                }

                // Sign types
                if (data.top_sign_types && data.top_sign_types.length > 0) {
                    document.getElementById('signTypeDist').textContent =
                        data.top_sign_types.map((s, i) =>
                            `${i+1}. ${s.sign_type}: ${s.count} queries`
                        ).join('\n');
                }

                showToast('Analytics loaded', 'success');
            }
        }

        // ─── SCAN FILES ───
        async function loadScanFiles() {
            try {
                const res = await fetch('/api/scan-files');
                const data = await res.json();

                const list = document.getElementById('scanFileList');
                if (data.files && data.files.length > 0) {
                    list.innerHTML = data.files.map(f => `
                        <li class="file-item" onclick="previewScanFile('${f.name}')" style="cursor:pointer">
                            <div>
                                <div class="file-name">${f.icon} ${f.name}</div>
                                <div class="file-meta">${f.size}</div>
                            </div>
                            <div>
                                ${f.type === 'html' ? `<a href="/scans/${f.name}" target="_blank" class="btn btn-secondary" style="padding:4px 10px; font-size:0.75rem;" onclick="event.stopPropagation()">Open</a>` : ''}
                            </div>
                        </li>
                    `).join('');
                    showToast(`Found ${data.files.length} scan files`, 'success');
                } else {
                    list.innerHTML = '<li class="file-item"><span class="file-name" style="color:var(--text-muted)">No scan files found. Run scanning_YOLO.py first.</span></li>';
                }
            } catch (e) {
                showToast('Failed to load scan files', 'error');
            }
        }

        async function previewScanFile(filename) {
            try {
                const res = await fetch(`/api/scan-preview/${filename}`);
                const data = await res.json();
                document.getElementById('scanPreview').textContent = data.content || 'Empty file';
            } catch (e) {
                document.getElementById('scanPreview').textContent = `Error: ${e.message}`;
            }
        }

        // ─── HEALTH ───
        async function checkHealth() {
            document.getElementById('healthSpinner').classList.add('active');
            const { data, ok } = await api('/health');
            document.getElementById('healthSpinner').classList.remove('active');

            document.getElementById('healthResponse').textContent = formatJSON(data);
            document.getElementById('healthResponse').className =
                `response-box ${ok ? 'success' : 'error'}`;

            // Update status dots
            const ragDot = document.getElementById('ragStatus');
            const llmDot = document.getElementById('llmStatus');
            ragDot.className = `status-dot ${ok ? 'online' : 'offline'}`;
            llmDot.className = `status-dot ${data.llm_reachable ? 'online' : 'offline'}`;

            if (data.uptime_seconds) {
                document.getElementById('uptimeVal').textContent =
                    `${Math.round(data.uptime_seconds)}s`;
            }
        }

        async function loadSessions() {
            const { data } = await api('/api/sessions');
            document.getElementById('sessionsList').textContent = formatJSON(data);
        }

        // ─── Auto health check on load ───
        checkHealth();
    </script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    """Serve the test dashboard."""
    return render_template_string(DASHBOARD_HTML)


# Proxy all RAG server requests through this app
# This avoids CORS issues and keeps the frontend simple
@app.route('/proxy/<path:path>', methods=['GET', 'POST', 'DELETE'])
def proxy_to_rag(path):
    """Proxy requests to the RAG server at port 5001."""
    import requests as req
    url = f"{RAG_SERVER_URL}/{path}"

    try:
        if request.method == 'GET':
            resp = req.get(url, params=request.args, timeout=30)
        elif request.method == 'DELETE':
            resp = req.delete(url, timeout=10)
        else:
            # POST — handle both JSON and multipart form data
            if request.content_type and 'multipart' in request.content_type:
                # Forward multipart (voice query with audio file)
                files = {}
                for key, file in request.files.items():
                    files[key] = (file.filename, file.read(), file.content_type)
                data = {k: v for k, v in request.form.items()}
                resp = req.post(url, files=files, data=data, timeout=60)
            else:
                resp = req.post(url, json=request.json, timeout=30)

        # Return the proxied response
        from flask import Response
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('Content-Type', 'application/json')
        )
    except req.ConnectionError:
        return jsonify({
            "error": {
                "code": "RAG_SERVER_OFFLINE",
                "message": f"Cannot connect to RAG server at {RAG_SERVER_URL}. Is rag_server.py running?"
            }
        }), 503
    except Exception as e:
        return jsonify({"error": {"code": "PROXY_ERROR", "message": str(e)}}), 500


# ─────────────────────────────────────────────────────────
# SCAN RESULTS ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.route('/api/scan-files')
def list_scan_files():
    """List all files in the scans/ directory."""
    if not os.path.exists(SCANS_DIR):
        return jsonify({"files": []})

    files = []
    for f in sorted(os.listdir(SCANS_DIR), reverse=True):
        filepath = os.path.join(SCANS_DIR, f)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            ext = os.path.splitext(f)[1].lower()

            icon_map = {
                '.csv': '📊', '.json': '📋', '.pdf': '📄',
                '.html': '🗺️', '.png': '📱',
            }
            size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"

            files.append({
                "name": f,
                "size": size_str,
                "type": ext.lstrip('.'),
                "icon": icon_map.get(ext, '📁'),
            })

    return jsonify({"files": files, "count": len(files)})


@app.route('/api/scan-preview/<filename>')
def preview_scan_file(filename):
    """Preview contents of a scan file (CSV/JSON only)."""
    filepath = os.path.join(SCANS_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ('.csv', '.json', '.txt'):
        return jsonify({"content": f"Preview not available for {ext} files. Use 'Open' for HTML files."})

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(50000)  # Limit preview to 50KB
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"content": f"Error reading file: {e}"})


@app.route('/scans/<path:filename>')
def serve_scan_file(filename):
    """Serve scan files directly (for heatmap HTML, QR codes, PDFs)."""
    return send_from_directory(SCANS_DIR, filename)


# ─────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("═" * 55)
    print("  NHAI Test Dashboard")
    print("═" * 55)
    print(f"  ├── Dashboard:    http://localhost:5002")
    print(f"  ├── RAG Proxy:    {RAG_SERVER_URL}")
    print(f"  ├── Scans Dir:    {SCANS_DIR}/")
    print(f"  └── Press Ctrl+C to stop")
    print("═" * 55)
    print()
    print("    Make sure rag_server.py is running on port 5001!")
    print()
    app.run(port=5002, debug=True)
