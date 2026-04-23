import os
import sys
import re
import io
import json
import time
import sqlite3
import hashlib
import html
import tempfile
from collections import OrderedDict
from datetime import datetime, timezone
from functools import wraps

# Fix Windows console Unicode output (cp1252 can't print ═, emoji, etc.)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# ─────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────
# Groq API key — get yours free at https://console.groq.com/keys
os.environ["GROQ_API_KEY"] = "APIKEY"

# Rate limiting
RATE_LIMIT_MAX_REQUESTS = 30     # Requests per window
RATE_LIMIT_WINDOW_SECONDS = 60   # Window size in seconds

# Cache settings
CACHE_MAX_SIZE = 200             # Max cached queries
CACHE_TTL_SECONDS = 600          # 10 minutes TTL

# Conversation memory
MAX_HISTORY_TURNS = 5            # Keep last 5 turns per session

# Input validation
MAX_QUERY_LENGTH = 500           # Max characters per query

# Database
DB_PATH = "rag_query_history.db"

# Feature 1 (STT): Audio upload config
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
AUDIO_UPLOAD_DIR = "audio_uploads"
os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)

# Feature 3 (Language Badge): Language metadata map
LANGUAGE_META = {
    "en": {"name": "English",    "native": "English",    "flag": "🇬🇧"},
    "hi": {"name": "Hindi",      "native": "हिन्दी",      "flag": "🇮🇳"},
    "mr": {"name": "Marathi",    "native": "मराठी",       "flag": "🇮🇳"},
    "ta": {"name": "Tamil",      "native": "தமிழ்",       "flag": "🇮🇳"},
    "te": {"name": "Telugu",     "native": "తెలుగు",      "flag": "🇮🇳"},
    "kn": {"name": "Kannada",    "native": "ಕನ್ನಡ",       "flag": "🇮🇳"},
    "ml": {"name": "Malayalam",  "native": "മലയാളം",     "flag": "🇮🇳"},
    "bn": {"name": "Bengali",    "native": "বাংলা",       "flag": "🇮🇳"},
    "gu": {"name": "Gujarati",   "native": "ગુજરાતી",     "flag": "🇮🇳"},
    "pa": {"name": "Punjabi",    "native": "ਪੰਜਾਬੀ",      "flag": "🇮🇳"},
    "or": {"name": "Odia",       "native": "ଓଡ଼ିଆ",       "flag": "🇮🇳"},
    "as": {"name": "Assamese",   "native": "অসমীয়া",     "flag": "🇮🇳"},
    "ur": {"name": "Urdu",       "native": "اردو",        "flag": "🇮🇳"},
}


# ─────────────────────────────────────────────────
# APP INITIALIZATION
# ─────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

SERVER_START_TIME = time.time()

# Initialize the LLM (Groq — free, fast inference)
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
parser = JsonOutputParser()

# ─────────────────────────────────────────────────
# Feature 1: Conversation Memory
# ─────────────────────────────────────────────────
session_histories = {}  # { session_id: [ {role, content}, ... ] }


def get_conversation_context(session_id):
    """Return formatted conversation history for a session."""
    if session_id not in session_histories:
        return ""

    history = session_histories[session_id]
    lines = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        role = turn["role"].upper()
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)


def append_to_history(session_id, role, content):
    """Add a turn to the session history, trimming to max length."""
    if session_id not in session_histories:
        session_histories[session_id] = []

    session_histories[session_id].append({"role": role, "content": content})

    # Trim to keep only the latest turns
    if len(session_histories[session_id]) > MAX_HISTORY_TURNS * 2:
        session_histories[session_id] = session_histories[session_id][-MAX_HISTORY_TURNS:]


# ─────────────────────────────────────────────────
# Feature 5: Semantic Query Cache (LRU + TTL)
# ─────────────────────────────────────────────────
class LRUTTLCache:
    """Least-Recently-Used cache with Time-To-Live expiration."""

    def __init__(self, max_size=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()  # key -> (value, timestamp)
        self.hits = 0
        self.misses = 0

    def _make_key(self, query_text):
        """Normalize and hash the query for cache lookup."""
        normalized = query_text.strip().lower()
        normalized = re.sub(r'\s+', ' ', normalized)
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get(self, query_text):
        """Return cached result or None if miss/expired."""
        key = self._make_key(query_text)

        if key in self.cache:
            value, timestamp = self.cache[key]
            if (time.time() - timestamp) < self.ttl:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return value
            else:
                # Expired — remove it
                del self.cache[key]

        self.misses += 1
        return None

    def put(self, query_text, result):
        """Store a result in the cache."""
        key = self._make_key(query_text)

        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (result, time.time())

        # Evict oldest if over capacity
        while len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def stats(self):
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 1),
            "ttl_seconds": self.ttl,
        }


query_cache = LRUTTLCache()

# ─────────────────────────────────────────────────
# Feature 4: Rate Limiting (per-IP, in-memory)
# ─────────────────────────────────────────────────
rate_limit_store = {}  # { ip: [timestamp, timestamp, ...] }


def check_rate_limit(ip):
    """Return True if the request is within rate limits, False if exceeded."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    if ip not in rate_limit_store:
        rate_limit_store[ip] = []

    # Prune old entries
    rate_limit_store[ip] = [t for t in rate_limit_store[ip] if t > window_start]

    if len(rate_limit_store[ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    rate_limit_store[ip].append(now)
    return True


# ─────────────────────────────────────────────────
# Feature 2: SQLite Query History
# ─────────────────────────────────────────────────
def init_db():
    """Initialize the SQLite database for query logging."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            raw_query TEXT NOT NULL,
            detected_lang TEXT,
            mongo_query_json TEXT,
            ui_message TEXT,
            cached INTEGER DEFAULT 0,
            response_time_ms REAL,
            input_method TEXT DEFAULT 'text',
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def log_query(session_id, raw_query, detected_lang, mongo_query, ui_message,
              cached, response_time_ms, input_method="text"):
    """Log a query and its result to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO queries (session_id, raw_query, detected_lang, mongo_query_json,
                                 ui_message, cached, response_time_ms, input_method, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            raw_query,
            detected_lang,
            json.dumps(mongo_query) if mongo_query else None,
            ui_message,
            1 if cached else 0,
            round(response_time_ms, 2),
            input_method,
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f" DB Log Error: {e}")


# ─────────────────────────────────────────────────
# Feature 6: Input Sanitization
# ─────────────────────────────────────────────────
def sanitize_query(text):
    """Sanitize user input: strip HTML, limit length, normalize whitespace."""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape HTML entities
    text = html.unescape(text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def make_error_response(code, message, http_status=400):
    """Return a standardized error JSON response."""
    return jsonify({
        "error": {
            "code": code,
            "message": message,
        }
    }), http_status


# ─────────────────────────────────────────────────
# Feature 1 (STT): Speech-to-Text via OpenAI Whisper
# ─────────────────────────────────────────────────
def transcribe_audio(audio_file_path):
    """Transcribe an audio file using OpenAI Whisper API.
    Returns (transcript_text, detected_language) or raises an exception.
    """
    try:
        from openai import OpenAI
        client = OpenAI()

        with open(audio_file_path, "rb") as audio_file:
            # Use Whisper with language detection
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
            )

        text = transcript.text
        # Whisper returns language in the verbose response
        detected_lang = getattr(transcript, 'language', 'en')

        print(f"  Whisper transcribed: \"{text}\" (lang: {detected_lang})")
        return text, detected_lang

    except ImportError:
        raise RuntimeError("OpenAI Python SDK not installed. Run: pip install openai")
    except Exception as e:
        raise RuntimeError(f"Whisper transcription failed: {e}")


# ─────────────────────────────────────────────────
# Feature 2 (TTS): Text-to-Speech response
# ─────────────────────────────────────────────────
def generate_tts_audio(text, lang_code="en"):
    """Generate speech audio from text using gTTS.
    Returns the path to the generated MP3 file.
    """
    try:
        from gtts import gTTS

        # Map language codes to gTTS-supported codes
        gtts_lang_map = {
            "en": "en", "hi": "hi", "mr": "mr", "ta": "ta",
            "te": "te", "kn": "kn", "ml": "ml", "bn": "bn",
            "gu": "gu", "pa": "pa", "ur": "ur",
        }
        tts_lang = gtts_lang_map.get(lang_code, "en")

        tts = gTTS(text=text, lang=tts_lang, slow=False)

        # Save to a temp file
        os.makedirs("tts_cache", exist_ok=True)
        filename = f"tts_cache/response_{hashlib.md5(text.encode()).hexdigest()[:12]}.mp3"
        tts.save(filename)

        print(f"🔊 TTS generated: {filename} (lang: {tts_lang})")
        return filename

    except ImportError:
        print("  gTTS not installed. Run: pip install gTTS")
        return None
    except Exception as e:
        print(f"  TTS generation failed: {e}")
        return None


# ─────────────────────────────────────────────────
# Feature 3 (Language Badge): Enrich response with language metadata
# ─────────────────────────────────────────────────
def get_language_badge(lang_code):
    """Return language metadata for display in frontend."""
    if lang_code in LANGUAGE_META:
        return LANGUAGE_META[lang_code]
    return {
        "name": lang_code.upper(),
        "native": lang_code,
        "flag": "🌐"
    }


# ─────────────────────────────────────────────────
# PROMPT TEMPLATE (with conversation memory slot)
# ─────────────────────────────────────────────────
system_prompt = """
You are an advanced database assistant for the National Highways Authority of India (NHAI).
Your job is to convert user requests about highway sign inspections into precise MongoDB queries.
The user may speak in English, Hindi, Gujarati, Marathi, Tamil, or other regional languages.

Here is the exact schema for the MongoDB "signs" collection:
{{
  "sign_type": "String (e.g., 'Stop Sign', 'Speed Limit 80', 'car', 'person')",
  "status": "String (strictly 'Pass' or 'Fail')",
  "reflectivity_score": "Float (e.g., 1.5, -0.2)",
  "lighting": "String ('day' or 'night')"
}}

Follow these exact steps:
1. Detect the user's language and intent.
2. Convert the intent into a valid MongoDB JSON query based ONLY on the schema above.
3. Draft a conversational, first-person response confirming what you are filtering. This response MUST be in the user's ORIGINAL language.
4. Identify the 2-letter ISO language code (e.g., "en", "hi", "gu", "mr").

CRITICAL INSTRUCTION: You must ALWAYS respond with a single, valid JSON object. 
Do not include any conversational filler outside of the JSON. Your JSON MUST contain exactly these three keys:
1. "mongo_query": The MongoDB query dictionary to filter the database.
2. "ui_message": The translated conversational response to the highway worker.
3. "detected_language": The 2-letter code of the detected language.

Example Input: "મને ખરાબ સાઇન બોર્ડ બતાવો" (Show me the bad sign boards in Gujarati)
Example Output:
{{
  "mongo_query": {{"status": "Fail"}},
  "ui_message": "મેં મેપ પર માત્ર ખરાબ (Fail) થયેલા સાઇન બોર્ડ ફિલ્ટર કર્યા છે.",
  "detected_language": "gu"
}}

Conversation History:
{conversation_history}

User Query: {query}
"""

prompt = ChatPromptTemplate.from_template(system_prompt)
rag_chain = prompt | llm | parser


# ─────────────────────────────────────────────────
# HELPER: Process a text query through the RAG chain
# ─────────────────────────────────────────────────
def process_rag_query(user_text, session_id, input_method="text", want_audio=False):
    """Core RAG processing logic shared by text and voice endpoints.
    Returns (response_dict, http_status_code).
    """
    start_time = time.time()

    # Input validation
    if not user_text:
        return {"error": {"code": "EMPTY_QUERY", "message": "No query text provided."}}, 400

    if len(user_text) > MAX_QUERY_LENGTH:
        return {"error": {"code": "QUERY_TOO_LONG",
                          "message": f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters."}}, 400

    # Sanitize
    user_text = sanitize_query(user_text)
    if not user_text:
        return {"error": {"code": "EMPTY_QUERY", "message": "Query was empty after sanitization."}}, 400

    print(f"\n🔍 Processing Query: \"{user_text}\" [session: {session_id}] [via: {input_method}]")

    # Check cache
    cached_result = query_cache.get(user_text)
    if cached_result:
        elapsed_ms = (time.time() - start_time) * 1000
        print(f"⚡ Cache HIT — {elapsed_ms:.0f}ms")

        detected_lang = cached_result.get("detected_language", "en")

        log_query(
            session_id=session_id, raw_query=user_text,
            detected_lang=detected_lang,
            mongo_query=cached_result.get("mongo_query"),
            ui_message=cached_result.get("ui_message"),
            cached=True, response_time_ms=elapsed_ms,
            input_method=input_method,
        )

        response = dict(cached_result)
        response["cached"] = True
        response["response_time_ms"] = round(elapsed_ms, 2)
        response["language_badge"] = get_language_badge(detected_lang)

        # Feature 2 (TTS): Generate audio response if requested
        if want_audio:
            ui_message = cached_result.get("ui_message", "")
            tts_path = generate_tts_audio(ui_message, detected_lang)
            response["tts_audio_url"] = f"/api/tts/{os.path.basename(tts_path)}" if tts_path else None

        return response, 200

    # Build conversation context
    history_text = get_conversation_context(session_id)
    history_block = f"Previous conversation:\n{history_text}\n" if history_text else ""

    try:
        # Run the LangChain RAG chain
        result = rag_chain.invoke({
            "query": user_text,
            "conversation_history": history_block,
        })
        elapsed_ms = (time.time() - start_time) * 1000

        print(f"🤖 LangChain Output ({elapsed_ms:.0f}ms): {json.dumps(result, indent=2, ensure_ascii=False)}")

        # Update conversation memory
        append_to_history(session_id, "user", user_text)
        append_to_history(session_id, "assistant", result.get("ui_message", ""))

        # Cache the result
        query_cache.put(user_text, result)

        detected_lang = result.get("detected_language", "en")

        # Log to database
        log_query(
            session_id=session_id, raw_query=user_text,
            detected_lang=detected_lang,
            mongo_query=result.get("mongo_query"),
            ui_message=result.get("ui_message"),
            cached=False, response_time_ms=elapsed_ms,
            input_method=input_method,
        )

        # Enrich response
        result["cached"] = False
        result["response_time_ms"] = round(elapsed_ms, 2)
        result["language_badge"] = get_language_badge(detected_lang)

        # Feature 2 (TTS): Generate audio response if requested
        if want_audio:
            ui_message = result.get("ui_message", "")
            tts_path = generate_tts_audio(ui_message, detected_lang)
            result["tts_audio_url"] = f"/api/tts/{os.path.basename(tts_path)}" if tts_path else None

        return result, 200

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        print(f"❌ RAG Error ({elapsed_ms:.0f}ms): {e}")
        return {"error": {"code": "LLM_ERROR",
                          "message": "Failed to process your query. The AI service may be temporarily unavailable."}}, 500


# ─────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check with uptime and LLM reachability status."""
    uptime = round(time.time() - SERVER_START_TIME, 1)
    llm_ok = False
    try:
        # The model will return a short completion; we only care that it succeeds.
        _ = llm.invoke(
            ChatPromptTemplate.from_template("{question}").format(question="Hi")
        )
        llm_ok = True
    except Exception as e:
        print(f"⚠️  LLM health check failed: {e}")
        llm_ok = False

    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime,
        "llm_reachable": llm_ok,
        "cache_stats": query_cache.stats(),
        "active_sessions": len(session_histories),
        "supported_languages": list(LANGUAGE_META.keys()),
        "features": ["stt", "tts", "multi-language", "cache", "rate-limit", "conversation-memory"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────
# Main RAG query endpoint (text input)
# ─────────────────────────────────────────────────
@app.route('/api/rag-query', methods=['POST'])
def handle_rag_query():
    # Rate limiting
    client_ip = request.remote_addr or "unknown"
    if not check_rate_limit(client_ip):
        return make_error_response(
            "RATE_LIMIT_EXCEEDED",
            f"Too many requests. Limit is {RATE_LIMIT_MAX_REQUESTS} per {RATE_LIMIT_WINDOW_SECONDS}s. Please wait.",
            429
        )

    data = request.json
    if not data:
        return make_error_response("INVALID_BODY", "Request body must be valid JSON.", 400)

    user_voice_text = data.get("query", "")
    session_id = data.get("session_id", "default")
    want_audio = data.get("want_audio", False)  # Feature 2: Client can request TTS

    # The AI does its processing...
    result, status_code = process_rag_query(user_voice_text, session_id,
                                             input_method="text", want_audio=want_audio)
    
    # --- THE FALLBACK INTERCEPTOR ---
    # If the AI succeeded but only returned the raw mongo_query JSON, we rescue it here.
    if status_code == 200 and isinstance(result, dict):
        if "ui_message" not in result:
            result["ui_message"] = "I have processed your request."
        if "language_badge" not in result:
            result["language_badge"] = {"flag": "🤖", "name": "AI Agent"}
    # --------------------------------

    return jsonify(result), status_code

# ─────────────────────────────────────────────────
# Feature 1 (STT): Voice query endpoint — accepts audio file
# ─────────────────────────────────────────────────
@app.route('/api/voice-query', methods=['POST'])
def handle_voice_query():
    """Accept an audio file, transcribe it with Whisper, then process through RAG."""
    # Rate limiting
    client_ip = request.remote_addr or "unknown"
    if not check_rate_limit(client_ip):
        return make_error_response(
            "RATE_LIMIT_EXCEEDED",
            f"Too many requests. Limit is {RATE_LIMIT_MAX_REQUESTS} per {RATE_LIMIT_WINDOW_SECONDS}s.",
            429
        )

    # Check for audio file in request
    if 'audio' not in request.files:
        return make_error_response(
            "NO_AUDIO_FILE",
            "No audio file found. Send multipart form data with key 'audio'.",
            400
        )

    audio_file = request.files['audio']
    if not audio_file.filename:
        return make_error_response("INVALID_FILE", "Empty filename.", 400)

    # Validate file extension
    file_ext = os.path.splitext(audio_file.filename)[1].lower()
    if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
        return make_error_response(
            "UNSUPPORTED_FORMAT",
            f"Supported formats: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}",
            400
        )

    session_id = request.form.get("session_id", "default")
    want_audio = request.form.get("want_audio", "true").lower() == "true"

    # Save temp audio file
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_path = os.path.join(AUDIO_UPLOAD_DIR, f"voice_{timestamp_str}{file_ext}")
    audio_file.save(saved_path)

    print(f"\n🎙️  Voice file received: {saved_path} ({os.path.getsize(saved_path)} bytes)")

    # Step 1: Transcribe with Whisper
    try:
        transcribed_text, whisper_lang = transcribe_audio(saved_path)
    except RuntimeError as e:
        return make_error_response("TRANSCRIPTION_ERROR", str(e), 500)

    if not transcribed_text or not transcribed_text.strip():
        return make_error_response("EMPTY_TRANSCRIPTION", "Could not detect speech in the audio.", 400)

    # Step 2: Process through RAG chain
    result, status_code = process_rag_query(transcribed_text, session_id,
                                             input_method="voice", want_audio=want_audio)

    # Add STT metadata to response
    if isinstance(result, dict) and "error" not in result:
        result["transcription"] = transcribed_text
        result["whisper_language"] = whisper_lang

    # Cleanup audio file (optional — keep for debugging)
    # os.remove(saved_path)

    return jsonify(result), status_code


# ─────────────────────────────────────────────────
# Feature 2 (TTS): Serve generated audio files
# ─────────────────────────────────────────────────
@app.route('/api/tts/<filename>', methods=['GET'])
def serve_tts_audio(filename):
    """Serve a generated TTS audio file."""
    filepath = os.path.join("tts_cache", filename)
    if not os.path.exists(filepath):
        return make_error_response("FILE_NOT_FOUND", "Audio file not found.", 404)

    return send_file(filepath, mimetype="audio/mpeg", as_attachment=False)


# ─────────────────────────────────────────────────
# Feature 2 (TTS): Standalone TTS endpoint
# ─────────────────────────────────────────────────
@app.route('/api/tts-generate', methods=['POST'])
def generate_tts():
    """Generate TTS audio for arbitrary text in a given language."""
    data = request.json
    if not data:
        return make_error_response("INVALID_BODY", "Request body must be valid JSON.", 400)

    text = data.get("text", "")
    lang = data.get("language", "en")

    if not text:
        return make_error_response("EMPTY_TEXT", "No text provided.", 400)

    if len(text) > 1000:
        return make_error_response("TEXT_TOO_LONG", "Max 1000 characters for TTS.", 400)

    tts_path = generate_tts_audio(text, lang)
    if tts_path:
        return jsonify({
            "audio_url": f"/api/tts/{os.path.basename(tts_path)}",
            "language": lang,
            "language_badge": get_language_badge(lang),
            "text_length": len(text),
        })
    else:
        return make_error_response("TTS_ERROR", "Failed to generate speech audio.", 500)


# ─────────────────────────────────────────────────
# Feature 3: Supported languages endpoint
# ─────────────────────────────────────────────────
@app.route('/api/languages', methods=['GET'])
def list_languages():
    """Return all supported languages with metadata."""
    languages = []
    for code, meta in LANGUAGE_META.items():
        languages.append({
            "code": code,
            "name": meta["name"],
            "native_name": meta["native"],
            "flag": meta["flag"],
        })
    return jsonify({
        "supported_count": len(languages),
        "languages": languages,
    })


# ─────────────────────────────────────────────────
# Query history endpoint
# ─────────────────────────────────────────────────
@app.route('/api/query-history', methods=['GET'])
def query_history():
    """Return recent query history, optionally filtered by session_id."""
    limit = request.args.get("limit", 50, type=int)
    session_filter = request.args.get("session_id", None)
    method_filter = request.args.get("input_method", None)  # "voice" or "text"

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = []
        params = []

        if session_filter:
            conditions.append("session_id = ?")
            params.append(session_filter)
        if method_filter:
            conditions.append("input_method = ?")
            params.append(method_filter)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cursor.execute(
            f"SELECT * FROM queries {where_clause} ORDER BY id DESC LIMIT ?",
            params + [limit]
        )

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            "count": len(rows),
            "queries": rows,
        })
    except Exception as e:
        return make_error_response("DB_ERROR", f"Failed to fetch history: {e}", 500)


# ─────────────────────────────────────────────────
# Analytics endpoint
# ─────────────────────────────────────────────────
@app.route('/api/analytics', methods=['GET'])
def analytics():
    """Return aggregate analytics: queries per day, top sign types, language distribution."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Total queries
        cursor.execute("SELECT COUNT(*) as total FROM queries")
        total = cursor.fetchone()["total"]

        # Queries per day (last 30 days)
        cursor.execute("""
            SELECT DATE(timestamp) as day, COUNT(*) as count
            FROM queries
            GROUP BY DATE(timestamp)
            ORDER BY day DESC
            LIMIT 30
        """)
        queries_per_day = [dict(row) for row in cursor.fetchall()]

        # Language distribution
        cursor.execute("""
            SELECT detected_lang, COUNT(*) as count
            FROM queries
            WHERE detected_lang IS NOT NULL
            GROUP BY detected_lang
            ORDER BY count DESC
        """)
        language_dist = []
        for row in cursor.fetchall():
            lang_code = row["detected_lang"]
            badge = get_language_badge(lang_code)
            language_dist.append({
                "code": lang_code,
                "name": badge["name"],
                "native_name": badge["native"],
                "flag": badge["flag"],
                "count": row["count"],
            })

        # Input method distribution (voice vs text)
        cursor.execute("""
            SELECT input_method, COUNT(*) as count
            FROM queries
            GROUP BY input_method
            ORDER BY count DESC
        """)
        input_method_dist = [dict(row) for row in cursor.fetchall()]

        # Top queried sign types (extracted from mongo_query)
        cursor.execute("""
            SELECT mongo_query_json
            FROM queries
            WHERE mongo_query_json IS NOT NULL
        """)
        sign_type_counts = {}
        for row in cursor.fetchall():
            try:
                mq = json.loads(row["mongo_query_json"])
                st = mq.get("sign_type")
                if st:
                    key = st if isinstance(st, str) else json.dumps(st)
                    sign_type_counts[key] = sign_type_counts.get(key, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        top_sign_types = sorted(sign_type_counts.items(), key=lambda x: -x[1])[:10]

        # Cache performance
        cache_stats = query_cache.stats()

        # Average response time
        cursor.execute("SELECT AVG(response_time_ms) as avg_ms FROM queries")
        avg_response = cursor.fetchone()["avg_ms"] or 0

        # Cache hit ratio from DB
        cursor.execute("SELECT COUNT(*) as cached FROM queries WHERE cached = 1")
        cached_count = cursor.fetchone()["cached"]
        cache_ratio = (cached_count / total * 100) if total > 0 else 0

        conn.close()

        return jsonify({
            "total_queries": total,
            "avg_response_time_ms": round(avg_response, 2),
            "cache_hit_ratio_percent": round(cache_ratio, 1),
            "queries_per_day": queries_per_day,
            "language_distribution": language_dist,
            "input_method_distribution": input_method_dist,
            "top_sign_types": [{"sign_type": k, "count": v} for k, v in top_sign_types],
            "cache_stats": cache_stats,
        })
    except Exception as e:
        return make_error_response("DB_ERROR", f"Failed to compute analytics: {e}", 500)


# ─────────────────────────────────────────────────
# Session management endpoints
# ─────────────────────────────────────────────────
@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List all active conversation sessions."""
    sessions = []
    for sid, history in session_histories.items():
        sessions.append({
            "session_id": sid,
            "turns": len(history),
            "last_message": history[-1]["content"][:100] if history else "",
        })
    return jsonify({"active_sessions": sessions})


@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def clear_session(session_id):
    """Clear conversation history for a specific session."""
    if session_id in session_histories:
        del session_histories[session_id]
        return jsonify({"message": f"Session '{session_id}' cleared."})
    return make_error_response("SESSION_NOT_FOUND", f"No session with ID '{session_id}'.", 404)


# ─────────────────────────────────────────────────
# Download endpoints
# ─────────────────────────────────────────────────
@app.route('/api/download/<file_type>', methods=['GET'])
def download_report(file_type):
    """Serve the latest generated report (PDF, Heatmap, or CSV)."""
    import glob
    scans_dir = "scans"
    if not os.path.exists(scans_dir):
        return make_error_response("NOT_FOUND", "No scans directory found.", 404)
        
    if file_type == "report":
        pattern = "report_*.pdf"
    elif file_type == "heatmap":
        pattern = "heatmap_*.html"
    elif file_type == "csv":
        pattern = "scan_*.csv"
    else:
        return make_error_response("INVALID_TYPE", "Invalid file type.", 400)
        
    files = glob.glob(os.path.join(scans_dir, pattern))
    if not files:
        return make_error_response("NOT_FOUND", f"No {file_type} files found. Run the YOLO scanner first.", 404)
        
    # Get the latest file
    latest_file = max(files, key=os.path.getctime)
    return send_file(latest_file, as_attachment=False if file_type == "heatmap" else True)

# ─────────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────────
@app.route('/api/admin/clear-cache', methods=['POST'])
def admin_clear_cache():
    """Clear the RAG semantic cache."""
    query_cache.cache.clear()
    query_cache.hits = 0
    query_cache.misses = 0
    return jsonify({"success": True, "message": "Cache cleared."})

# ─────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    print("═" * 55)
    print("  🚀 AI RAG Server — NHAI Voice Assistant")
    print("═" * 55)
    print(f"  ├── Port:            5002")
    print(f"  ├── LLM:             Groq llama-3.1-8b-instant")
    print(f"  ├── Rate Limit:      {RATE_LIMIT_MAX_REQUESTS} req / {RATE_LIMIT_WINDOW_SECONDS}s")
    print(f"  ├── Cache:           {CACHE_MAX_SIZE} entries, {CACHE_TTL_SECONDS}s TTL")
    print(f"  ├── Memory:          {MAX_HISTORY_TURNS} turns / session")
    print(f"  ├── Query DB:        {DB_PATH}")
    print(f"  ├── Max Query Len:   {MAX_QUERY_LENGTH} chars")
    print(f"  ├── STT:             OpenAI Whisper")
    print(f"  ├── TTS:             gTTS (13 Indian languages)")
    print(f"  └── Languages:       {', '.join(LANGUAGE_META.keys())}")
    print("═" * 55)
    print("  📡 Endpoints:")
    print("     POST /api/rag-query      → Text query")
    print("     POST /api/voice-query    → Voice query (audio upload)")
    print("     POST /api/tts-generate   → Text-to-Speech")
    print("     GET  /api/tts/<file>     → Serve TTS audio")
    print("     GET  /api/languages      → Supported languages")
    print("     GET  /api/query-history  → Query log")
    print("     GET  /api/analytics      → Dashboard data")
    print("     GET  /api/sessions       → Active sessions")
    print("     GET  /health             → Health check")
    print("═" * 55)
    # Start Flask server on port 5002, binding to all interfaces
    app.run(host='0.0.0.0', port=5002, debug=True)