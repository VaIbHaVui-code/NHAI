import cv2
import numpy as np
import requests
import time
import csv
import json
import os
import threading
import winsound
from collections import defaultdict
from ultralytics import YOLO
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime, timezone
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Harsh.integration.payload_manager import stitch_and_send

# --- CONFIGURATION ---
API_ENDPOINT = "http://localhost:5000/api/signs"  # Member 2's Backend
YOLO_MODEL_PATH = "yolov8s-world.pt"  # The YOLO-World model
YOLO_WORLD_CLASSES = [
    "speed limit sign", 
    "highway distance board", 
    "traffic sign", 
    "stop sign",
    "green overhead highway sign"
]
MIN_WEBER_THRESHOLD = 1.5

# Feature 7: Confidence filtering
YOLO_CONFIDENCE_THRESHOLD = 0.15  # Skip detections below this confidence

# Feature 8: Batch posting
BATCH_SIZE = 10           # Max payloads per batch POST
BATCH_INTERVAL = 5.0      # Seconds between forced flushes
MAX_RETRIES = 3            # Retry attempts for failed batches

# Feature 11: Night-mode thresholds
LOW_LIGHT_BRIGHTNESS_THRESHOLD = 50   # Mean brightness below this = night
NIGHT_CLAHE_CLIP_LIMIT = 4.0          # Increased CLAHE for night
DAY_CLAHE_CLIP_LIMIT = 2.0            # Default CLAHE for day
NIGHT_GAMMA = 0.6                     # Gamma correction for night frames

# Feature 12: Deduplication
IOU_OVERLAP_THRESHOLD = 0.70  # IoU above this = same sign across frames

# Feature 9: Export directory
SCANS_DIR = "scans"

# Feature 5 (Audio Alert): Alert settings
ALERT_ON_FAIL = True                  # Play beep on failed signs
ALERT_CRITICAL_THRESHOLD = 0.5        # Contrast below this = critical alert
ALERT_FREQUENCY_HZ = 1500             # Beep frequency
ALERT_DURATION_MS = 200               # Beep duration
CRITICAL_ALERT_FREQUENCY_HZ = 2500    # Higher pitch for critical
CRITICAL_ALERT_DURATION_MS = 500      # Longer beep for critical

# Feature 7 (Telegram): Bot alert settings
TELEGRAM_BOT_TOKEN = ""               # Set your Telegram bot token
TELEGRAM_CHAT_ID = ""                 # Set your Telegram chat ID
TELEGRAM_ALERT_THRESHOLD = 0.5        # Send alert when contrast below this
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# Feature 8 (QR Code): QR settings
QR_CODE_DIR = os.path.join(SCANS_DIR, "qr_codes")
QR_BASE_URL = "http://localhost:5000/api/signs"  # Base URL for sign records

# Feature 9 (Multilingual): Overlay language
# Options: "en", "hi", "mr", "ta", "te", "kn"
OVERLAY_LANGUAGE = "en"

# Multilingual overlay labels
OVERLAY_TRANSLATIONS = {
    "en": {
        "pass": "PASS", "fail": "FAIL", "tracked": "tracked",
        "mode_day": "DAY", "mode_night": "NIGHT",
        "brightness": "Brightness", "signs": "Signs",
        "passed": "Passed", "failed": "Failed", "fps": "FPS",
        "elapsed": "Elapsed", "title": "NHAI Dashcam AI",
        "critical": "CRITICAL", "contrast": "CR",
        "confidence": "Conf", "months_left": "Months Left",
    },
    "hi": {
        "pass": "उत्तीर्ण", "fail": "असफल", "tracked": "ट्रैक्ड",
        "mode_day": "दिन", "mode_night": "रात",
        "brightness": "चमक", "signs": "चिन्ह",
        "passed": "उत्तीर्ण", "failed": "असफल", "fps": "FPS",
        "elapsed": "समय", "title": "NHAI डैशकैम AI",
        "critical": "गंभीर", "contrast": "CR",
        "confidence": "विश्वास", "months_left": "महीने शेष",
    },
    "mr": {
        "pass": "उत्तीर्ण", "fail": "अनुत्तीर्ण", "tracked": "ट्रॅक",
        "mode_day": "दिवस", "mode_night": "रात्र",
        "brightness": "तेजस्विता", "signs": "चिन्हे",
        "passed": "उत्तीर्ण", "failed": "अनुत्तीर्ण", "fps": "FPS",
        "elapsed": "वेळ", "title": "NHAI डॅशकॅम AI",
        "critical": "गंभीर", "contrast": "CR",
        "confidence": "विश्वास", "months_left": "महिने शिल्लक",
    },
    "ta": {
        "pass": "தேர்ச்சி", "fail": "தோல்வி", "tracked": "கண்காணிப்பு",
        "mode_day": "பகல்", "mode_night": "இரவு",
        "brightness": "பிரகாசம்", "signs": "அடையாளங்கள்",
        "passed": "தேர்ச்சி", "failed": "தோல்வி", "fps": "FPS",
        "elapsed": "நேரம்", "title": "NHAI டாஷ்கேம் AI",
        "critical": "முக்கியமான", "contrast": "CR",
        "confidence": "நம்பிக்கை", "months_left": "மாதங்கள்",
    },
    "te": {
        "pass": "ఉత్తీర్ణత", "fail": "విఫలం", "tracked": "ట్రాక్",
        "mode_day": "పగలు", "mode_night": "రాత్రి",
        "brightness": "ప్రకాశం", "signs": "సంకేతాలు",
        "passed": "ఉత్తీర్ణత", "failed": "విఫలం", "fps": "FPS",
        "elapsed": "సమయం", "title": "NHAI డ్యాష్‌క్యామ్ AI",
        "critical": "అత్యవసరం", "contrast": "CR",
        "confidence": "నమ్మకం", "months_left": "నెలలు మిగిలి",
    },
    "kn": {
        "pass": "ಉತ್ತೀರ್ಣ", "fail": "ವಿಫಲ", "tracked": "ಟ್ರ್ಯಾಕ್",
        "mode_day": "ಹಗಲು", "mode_night": "ರಾತ್ರಿ",
        "brightness": "ಹೊಳಪು", "signs": "ಚಿಹ್ನೆಗಳು",
        "passed": "ಉತ್ತೀರ್ಣ", "failed": "ವಿಫಲ", "fps": "FPS",
        "elapsed": "ಸಮಯ", "title": "NHAI ಡ್ಯಾಶ್‌ಕ್ಯಾಮ್ AI",
        "critical": "ಗಂಭೀರ", "contrast": "CR",
        "confidence": "ನಂಬಿಕೆ", "months_left": "ತಿಂಗಳು ಉಳಿದಿದೆ",
    },
}


# --- PYDANTIC VALIDATION SCHEMA ---
class GPSLocation(BaseModel):
    lat: float
    lng: float

class SignPayload(BaseModel):
    sign_type: str
    reflectivity_score: float
    status: str
    months_remaining: float
    gps: GPSLocation
    timestamp: str
    confidence: float = 0.0      # Feature 7: YOLO confidence
    lighting: str = "day"        # Feature 11: day/night tag


class RetroreflectivityEngine:
    def __init__(self, overlay_lang="en"):
        self.model = YOLO(YOLO_MODEL_PATH)
        self.model.set_classes(YOLO_WORLD_CLASSES)
        self.clahe = cv2.createCLAHE(clipLimit=DAY_CLAHE_CLIP_LIMIT, tileGridSize=(8, 8))
        self.current_lighting = "day"  # Feature 11

        # --- Feature 9 (Multilingual Overlay) ---
        self.lang = overlay_lang if overlay_lang in OVERLAY_TRANSLATIONS else "en"
        self.labels = OVERLAY_TRANSLATIONS[self.lang]

        # --- Feature 8: Batch posting ---
        self.post_buffer = []
        self.retry_queue = []
        self.last_flush_time = time.time()
        self.buffer_lock = threading.Lock()

        # --- Feature 9: CSV/JSON export ---
        os.makedirs(SCANS_DIR, exist_ok=True)
        os.makedirs(QR_CODE_DIR, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.csv_path = os.path.join(SCANS_DIR, f"scan_{timestamp_str}.csv")
        self.json_path = os.path.join(SCANS_DIR, f"scan_{timestamp_str}.json")
        self.pdf_path = os.path.join(SCANS_DIR, f"report_{timestamp_str}.pdf")
        self.maintenance_path = os.path.join(SCANS_DIR, f"maintenance_{timestamp_str}.csv")
        self.all_records = []  # Kept in memory for JSON dump + heatmap + summary
        self._init_csv()

        # --- Feature 12: Deduplication ---
        self.prev_frame_detections = []  # list of (bbox, sign_type) from previous frame

        # --- Feature 10 (HUD): Frame-level counters ---
        self.session_start_time = time.time()
        self.frame_count = 0
        self.fps_timer = time.time()
        self.current_fps = 0.0
        self.sign_id_counter = 0  # Unique ID for each sign

        # --- Feature 13: Summary counters ---
        self.stats = {
            "total_detections": 0,
            "total_unique": 0,
            "pass_count": 0,
            "fail_count": 0,
            "critical_count": 0,
            "contrast_values": [],
            "signs_by_type": defaultdict(int),
            "worst_sign": None,       # (sign_type, contrast, location)
            "skipped_low_conf": 0,
            "skipped_duplicate": 0,
            "night_frames": 0,
            "day_frames": 0,
            "alerts_sent": 0,
            "qr_codes_generated": 0,
        }

        print("✅ YOLO Engine Initialized.")
        print(f"   ├── Confidence threshold: {YOLO_CONFIDENCE_THRESHOLD}")
        print(f"   ├── Batch size: {BATCH_SIZE} | Interval: {BATCH_INTERVAL}s")
        print(f"   ├── CSV export: {self.csv_path}")
        print(f"   ├── Dedup IoU threshold: {IOU_OVERLAP_THRESHOLD}")
        print(f"   ├── Overlay language: {self.lang}")
        print(f"   ├── Audio alerts: {'ON' if ALERT_ON_FAIL else 'OFF'}")
        print(f"   ├── Telegram alerts: {'ON' if TELEGRAM_ENABLED else 'OFF'}")
        print(f"   └── QR code generation: ON")

    # ─────────────────────────────────────────────
    # Feature 9: CSV initialization
    # ─────────────────────────────────────────────
    def _init_csv(self):
        """Create CSV file with headers."""
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "sign_id", "timestamp", "sign_type", "confidence", "reflectivity_score",
                "status", "months_remaining", "lat", "lng", "lighting"
            ])

    def _append_csv(self, record: dict):
        """Append a single scan record to CSV."""
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                record.get("sign_id", ""),
                record["timestamp"], record["sign_type"], record["confidence"],
                record["reflectivity_score"], record["status"],
                record["months_remaining"],
                record["gps"]["lat"], record["gps"]["lng"],
                record["lighting"]
            ])

    # ─────────────────────────────────────────────
    # Feature 11: Night-mode detection
    # ─────────────────────────────────────────────
    def detect_lighting(self, frame_bgr):
        """Detect whether the frame is day or night based on average brightness."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        if mean_brightness < LOW_LIGHT_BRIGHTNESS_THRESHOLD:
            self.current_lighting = "night"
            self.clahe = cv2.createCLAHE(clipLimit=NIGHT_CLAHE_CLIP_LIMIT, tileGridSize=(8, 8))
            self.stats["night_frames"] += 1
        else:
            self.current_lighting = "day"
            self.clahe = cv2.createCLAHE(clipLimit=DAY_CLAHE_CLIP_LIMIT, tileGridSize=(8, 8))
            self.stats["day_frames"] += 1

        return mean_brightness

    def apply_gamma_correction(self, image, gamma=NIGHT_GAMMA):
        """Apply gamma correction to brighten dark images."""
        inv_gamma = 1.0 / gamma
        table = np.array([
            ((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)
        ]).astype("uint8")
        return cv2.LUT(image, table)

    # ─────────────────────────────────────────────
    # Image preprocessing (CLAHE)
    # ─────────────────────────────────────────────
    def apply_clahe(self, image_bgr):
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        cl = self.clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

    # ─────────────────────────────────────────────
    # Weber contrast calculation
    # ─────────────────────────────────────────────
    def calculate_weber_contrast(self, image_gray, bbox):
        x1, y1, x2, y2 = bbox
        sign_roi = image_gray[y1:y2, x1:x2]
        if sign_roi.size == 0:
            return 0.0
        Is = np.mean(sign_roi)

        h, w = image_gray.shape
        bx1, by1 = max(0, x1 - 20), max(0, y1 - 20)
        bx2, by2 = min(w, x2 + 20), min(h, y2 + 20)

        bg_mask = np.ones_like(image_gray[by1:by2, bx1:bx2], dtype=bool)
        bg_mask[(y1 - by1):(y2 - by1), (x1 - bx1):(x2 - bx1)] = False

        background_roi = image_gray[by1:by2, bx1:bx2][bg_mask]
        Ib = np.mean(background_roi) if background_roi.size > 0 else 1
        if Ib == 0:
            Ib = 1

        contrast = (Is - Ib) / Ib
        return round(contrast, 3)

    # ─────────────────────────────────────────────
    # Failure timeline prediction
    # ─────────────────────────────────────────────
    def predict_failure_timeline(self, current_cr):
        if current_cr <= MIN_WEBER_THRESHOLD:
            return 0
        cr_remaining = current_cr - MIN_WEBER_THRESHOLD
        months_remaining = cr_remaining / 0.05
        return round(months_remaining, 1)

    # ─────────────────────────────────────────────
    # Feature 12: IoU-based deduplication
    # ─────────────────────────────────────────────
    @staticmethod
    def compute_iou(boxA, boxB):
        """Compute Intersection over Union between two [x1,y1,x2,y2] boxes."""
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter_area = max(0, xB - xA) * max(0, yB - yA)
        if inter_area == 0:
            return 0.0

        boxA_area = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxB_area = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        union_area = boxA_area + boxB_area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def is_duplicate(self, bbox, sign_type):
        """Check if this detection overlaps significantly with a previous-frame detection."""
        for prev_bbox, prev_type in self.prev_frame_detections:
            if prev_type == sign_type and self.compute_iou(bbox, prev_bbox) >= IOU_OVERLAP_THRESHOLD:
                return True
        return False

    # ─────────────────────────────────────────────
    # Feature 5 (Audio Alert): Beep on failed signs
    # ─────────────────────────────────────────────
    def play_alert(self, contrast):
        """Play an audio beep when a degraded sign is detected (Windows only)."""
        if not ALERT_ON_FAIL:
            return

        def _beep():
            try:
                if contrast < ALERT_CRITICAL_THRESHOLD:
                    # Critical — louder, longer beep
                    winsound.Beep(CRITICAL_ALERT_FREQUENCY_HZ, CRITICAL_ALERT_DURATION_MS)
                else:
                    # Standard fail beep
                    winsound.Beep(ALERT_FREQUENCY_HZ, ALERT_DURATION_MS)
            except Exception:
                pass  # Silently fail on non-Windows or audio errors

        # Run in thread so it doesn't block frame processing
        threading.Thread(target=_beep, daemon=True).start()

    # ─────────────────────────────────────────────
    # Feature 7 (Telegram): Send alert to Telegram
    # ─────────────────────────────────────────────
    def send_telegram_alert(self, payload):
        """Send a critical sign alert to Telegram bot."""
        if not TELEGRAM_ENABLED:
            return
        if payload["reflectivity_score"] > TELEGRAM_ALERT_THRESHOLD:
            return

        def _send():
            try:
                message = (
                    f"🚨 *CRITICAL SIGN DETECTED*\n\n"
                    f"📍 *Type:* {payload['sign_type']}\n"
                    f"📊 *Contrast:* {payload['reflectivity_score']}\n"
                    f"⚠️ *Status:* {payload['status']}\n"
                    f"⏳ *Months Left:* {payload['months_remaining']}\n"
                    f"🌙 *Lighting:* {payload['lighting']}\n"
                    f"📌 *GPS:* [{payload['gps']['lat']}, {payload['gps']['lng']}]"
                    f"(https://maps.google.com/?q={payload['gps']['lat']},{payload['gps']['lng']})\n"
                    f"🕐 *Time:* {payload['timestamp']}\n"
                    f"🎯 *Confidence:* {payload['confidence']}"
                )
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(url, json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                }, timeout=5)
                self.stats["alerts_sent"] += 1
                print(f"📱 Telegram alert sent for {payload['sign_type']}")
            except Exception as e:
                print(f"⚠️  Telegram alert failed: {e}")

        # Send in background thread
        threading.Thread(target=_send, daemon=True).start()

    # ─────────────────────────────────────────────
    # Feature 8 (QR Code): Generate QR for each sign
    # ─────────────────────────────────────────────
    def generate_qr_code(self, sign_id, payload):
        """Generate a QR code linking to the sign's database record."""
        try:
            import qrcode
        except ImportError:
            return None

        try:
            # URL that the QR code points to
            sign_url = f"{QR_BASE_URL}/{sign_id}"
            qr_data = json.dumps({
                "id": sign_id,
                "url": sign_url,
                "type": payload["sign_type"],
                "gps": payload["gps"],
                "scanned": payload["timestamp"],
            })

            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            qr_path = os.path.join(QR_CODE_DIR, f"sign_{sign_id}.png")
            img.save(qr_path)
            self.stats["qr_codes_generated"] += 1
            return qr_path

        except Exception as e:
            print(f"⚠️  QR generation failed: {e}")
            return None

    # ─────────────────────────────────────────────
    # Feature 8: Batch posting with retry
    # ─────────────────────────────────────────────
    def queue_payload(self, payload_dict):
        """Add a payload to the buffer; auto-flush when full or interval elapsed."""
        try:
            valid_payload = SignPayload(**payload_dict)
            with self.buffer_lock:
                self.post_buffer.append(valid_payload.model_dump())
        except ValidationError as e:
            print(f"❌ Validation Error: {e}")
            return

        # Check flush conditions
        should_flush = False
        with self.buffer_lock:
            if len(self.post_buffer) >= BATCH_SIZE:
                should_flush = True
            elif (time.time() - self.last_flush_time) >= BATCH_INTERVAL:
                should_flush = True

        if should_flush:
            self.flush_buffer()

    def flush_buffer(self):
        """Send buffered payloads as a batch POST. Move failures to retry queue."""
        with self.buffer_lock:
            if not self.post_buffer:
                return
            batch = self.post_buffer.copy()
            self.post_buffer.clear()
            self.last_flush_time = time.time()

        self._send_batch(batch, attempt=1)

    def _send_batch(self, batch, attempt):
        """POST a batch of payloads. Retry with exponential backoff on failure."""
        try:
            response = requests.post(
                API_ENDPOINT,
                json=batch,
                timeout=10
            )
            if response.status_code in (200, 201):
                print(f"📡 Batch synced: {len(batch)} signs [{response.status_code}]")
            else:
                raise requests.RequestException(f"HTTP {response.status_code}")
        except Exception as e:
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt  # exponential backoff: 2s, 4s, 8s
                print(f"⚠️  Batch failed (attempt {attempt}/{MAX_RETRIES}), retrying in {wait}s... ({e})")
                time.sleep(wait)
                self._send_batch(batch, attempt + 1)
            else:
                print(f"❌ Batch permanently failed after {MAX_RETRIES} attempts. Queued {len(batch)} for retry.")
                with self.buffer_lock:
                    self.retry_queue.extend(batch)

    def retry_failed(self):
        """Attempt to re-send all items in the retry queue."""
        with self.buffer_lock:
            if not self.retry_queue:
                return
            retries = self.retry_queue.copy()
            self.retry_queue.clear()

        print(f"🔄 Retrying {len(retries)} previously failed payloads...")
        self._send_batch(retries, attempt=1)

    # ─────────────────────────────────────────────
    # Feature 10 (HUD): Draw dashboard overlay
    # ─────────────────────────────────────────────
    def draw_hud(self, frame, brightness):
        """Draw a heads-up display with live stats on the video frame."""
        h, w = frame.shape[:2]
        L = self.labels

        # Calculate FPS
        self.frame_count += 1
        elapsed_since_fps = time.time() - self.fps_timer
        if elapsed_since_fps >= 1.0:
            self.current_fps = self.frame_count / elapsed_since_fps
            self.frame_count = 0
            self.fps_timer = time.time()

        total_elapsed = time.time() - self.session_start_time
        mins = int(total_elapsed // 60)
        secs = int(total_elapsed % 60)

        s = self.stats

        # ── Top-left: Mode & brightness ──
        mode_label = L["mode_night"] if self.current_lighting == "night" else L["mode_day"]
        mode_color = (0, 255, 255) if self.current_lighting == "night" else (200, 200, 200)
        cv2.putText(frame, f"{mode_label} | {L['brightness']}: {brightness:.0f}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, mode_color, 2)

        # ── Top-right: HUD panel ──
        panel_x = w - 280
        panel_y = 10
        panel_h = 170
        panel_w = 270

        # Semi-transparent dark background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y),
                      (panel_x + panel_w, panel_y + panel_h),
                      (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Border
        cv2.rectangle(frame, (panel_x, panel_y),
                      (panel_x + panel_w, panel_y + panel_h),
                      (0, 200, 255), 1)

        # Title bar
        cv2.putText(frame, L["title"], (panel_x + 10, panel_y + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)

        # Stats lines
        line_y = panel_y + 48
        line_spacing = 22
        text_color = (220, 220, 220)
        val_color_pass = (0, 255, 0)
        val_color_fail = (0, 0, 255)

        lines = [
            (f"{L['signs']}: {s['total_unique']}", text_color),
            (f"{L['passed']}: {s['pass_count']}", val_color_pass),
            (f"{L['failed']}: {s['fail_count']}", val_color_fail),
            (f"{L['fps']}: {self.current_fps:.1f}  |  {L['elapsed']}: {mins:02d}:{secs:02d}", text_color),
        ]

        for text, color in lines:
            cv2.putText(frame, text, (panel_x + 12, line_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            line_y += line_spacing

        # Pass rate bar
        total = s["total_unique"]
        if total > 0:
            pass_rate = s["pass_count"] / total
            bar_x = panel_x + 12
            bar_y = line_y + 2
            bar_w = panel_w - 24
            bar_h = 12

            # Background bar
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                          (60, 60, 60), -1)
            # Pass portion (green)
            pass_w = int(bar_w * pass_rate)
            if pass_w > 0:
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + pass_w, bar_y + bar_h),
                              (0, 200, 0), -1)
            # Fail portion (red)
            if pass_w < bar_w:
                cv2.rectangle(frame, (bar_x + pass_w, bar_y),
                              (bar_x + bar_w, bar_y + bar_h),
                              (0, 0, 200), -1)

            # Pass rate text
            cv2.putText(frame, f"{pass_rate:.0%}", (bar_x + bar_w + 5, bar_y + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 220, 220), 1)

        return frame

    # ─────────────────────────────────────────────
    # Main frame processing
    # ─────────────────────────────────────────────
    def process_frame(self, frame):
        L = self.labels

        # Feature 11: Detect lighting and adapt
        brightness = self.detect_lighting(frame)

        # Preprocessing
        enhanced_frame = self.apply_clahe(frame)
        if self.current_lighting == "night":
            enhanced_frame = self.apply_gamma_correction(enhanced_frame)

        gray_frame = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2GRAY)
        results = self.model(enhanced_frame, verbose=False)

        current_frame_detections = []  # For dedup tracking

        for result in results:
            for box in result.boxes:
                # Feature 7: Confidence filtering
                conf = float(box.conf[0])
                if conf < YOLO_CONFIDENCE_THRESHOLD:
                    self.stats["skipped_low_conf"] += 1
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = int(box.cls[0])
                sign_type = self.model.names[cls]
                
                # ONLY allow actual infrastructure/sign classes from the standard COCO dataset
                allowed_classes = {"stop sign", "traffic light", "fire hydrant", "parking meter"}
                if sign_type not in allowed_classes:
                    continue

                bbox = [x1, y1, x2, y2]

                # Feature 12: Deduplication
                if self.is_duplicate(bbox, sign_type):
                    self.stats["skipped_duplicate"] += 1
                    # Still draw the box (dimmed) so operator sees tracking
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
                    cv2.putText(frame, f"[{L['tracked']}] {sign_type}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
                    current_frame_detections.append((bbox, sign_type))
                    continue

                current_frame_detections.append((bbox, sign_type))

                # Calculate metrics
                contrast = self.calculate_weber_contrast(gray_frame, bbox)
                status = "Pass" if contrast >= MIN_WEBER_THRESHOLD else "Fail"
                months_left = self.predict_failure_timeline(contrast)

                # Assign unique sign ID
                self.sign_id_counter += 1
                sign_id = f"NHAI-{datetime.now().strftime('%Y%m%d')}-{self.sign_id_counter:04d}"

                # --- HARSH'S STITCHER (Replaces Mock GPS & self.queue_payload) ---
                # This automatically pairs your YOLO data with the KML simulation GPS
                # --- HARSH'S STITCHER (Now with all fields!) ---
                stitch_and_send(
                    frame_id=self.frame_count, 
                    sign_type=sign_type, 
                    contrast_ratio=contrast,
                    status=status,
                    months_remaining=months_left,
                    confidence=conf,
                    lighting=self.current_lighting
                )

                # Note: We still keep the local payload dictionary for your CSV/PDF exports
                payload = {
                    "sign_id": sign_id,
                    "sign_type": sign_type,
                    "reflectivity_score": contrast,
                    "status": status,
                    "months_remaining": months_left,
                    "gps": {"lat": 0.0, "lng": 0.0}, # Handled by Harsh for backend, dummy for CSV
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": round(conf, 3),
                    "lighting": self.current_lighting,
                }

                # Feature 9: Save locally for your reports
                self.all_records.append(payload)
                self._append_csv(payload)

                # Feature 5 (Audio Alert): Beep on fail
                if status == "Fail":
                    self.play_alert(contrast)

                # Feature 7 (Telegram): Alert on critical
                if contrast < TELEGRAM_ALERT_THRESHOLD:
                    self.send_telegram_alert(payload)
                    self.stats["critical_count"] += 1

                # Feature 8 (QR Code): Generate QR
                self.generate_qr_code(sign_id, payload)

                # Feature 13: Update stats
                self.stats["total_detections"] += 1
                self.stats["total_unique"] += 1
                self.stats["contrast_values"].append(contrast)
                self.stats["signs_by_type"][sign_type] += 1
                if status == "Pass":
                    self.stats["pass_count"] += 1
                else:
                    self.stats["fail_count"] += 1
                # Track worst sign
                if (self.stats["worst_sign"] is None or
                        contrast < self.stats["worst_sign"][1]):
                    self.stats["worst_sign"] = (sign_type, contrast, (0.0,0.0), sign_id)

                # Draw bounding box with multilingual labels
                is_critical = contrast < ALERT_CRITICAL_THRESHOLD
                if status == "Pass":
                    color = (0, 255, 0)
                elif is_critical:
                    color = (0, 0, 255)  # Bright red for critical
                else:
                    color = (0, 100, 255)  # Orange for normal fail

                thickness = 3 if is_critical else 2
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

                # Label line 1: Sign type + status
                status_label = L["pass"] if status == "Pass" else L["fail"]
                if is_critical:
                    status_label = f"⚠ {L['critical']}"
                label1 = f"{sign_type} [{status_label}]"
                cv2.putText(frame, label1, (x1, y1 - 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # Label line 2: Contrast + Confidence
                label2 = f"{L['contrast']}:{contrast} | {L['confidence']}:{conf:.0%}"
                cv2.putText(frame, label2, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

                # Critical flash effect
                if is_critical:
                    # Add pulsing border effect for critical signs
                    cv2.rectangle(frame, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3),
                                  (0, 0, 255), 2)

        # Update dedup tracker for next frame
        self.prev_frame_detections = current_frame_detections

        # Feature 10 (HUD): Draw dashboard overlay
        frame = self.draw_hud(frame, brightness)

        # Periodically retry failed posts
        if time.time() - self.last_flush_time > BATCH_INTERVAL * 3:
            self.retry_failed()

        return frame

    # ─────────────────────────────────────────────
    # Feature 10: GPS Heatmap generation
    # ─────────────────────────────────────────────
    def generate_heatmap(self):
        """Generate an HTML heatmap of all scanned signs using folium."""
        if not self.all_records:
            print("⚠️  No records to generate heatmap.")
            return

        try:
            import folium
        except ImportError:
            print("⚠️  folium not installed. Skipping heatmap. Install with: pip install folium")
            return

        # Center map on average coordinates
        avg_lat = np.mean([r["gps"]["lat"] for r in self.all_records])
        avg_lng = np.mean([r["gps"]["lng"] for r in self.all_records])
        m = folium.Map(location=[avg_lat, avg_lng], zoom_start=15, tiles="OpenStreetMap")

        for record in self.all_records:
            color = "green" if record["status"] == "Pass" else "red"
            popup_text = (
                f"<b>{record.get('sign_id', 'N/A')}</b><br>"
                f"<b>{record['sign_type']}</b><br>"
                f"Status: {record['status']}<br>"
                f"Contrast: {record['reflectivity_score']}<br>"
                f"Confidence: {record['confidence']}<br>"
                f"Months Left: {record['months_remaining']}<br>"
                f"Lighting: {record['lighting']}<br>"
                f"Time: {record['timestamp']}"
            )
            folium.CircleMarker(
                location=[record["gps"]["lat"], record["gps"]["lng"]],
                radius=8,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=f"{record['sign_type']} ({record['status']})"
            ).add_to(m)

        # Add legend
        legend_html = """
        <div style="position:fixed; bottom:30px; left:30px; z-index:1000;
                    background:white; padding:10px; border-radius:8px;
                    border:2px solid #ccc; font-size:13px;">
            <b>Sign Status</b><br>
            🟢 Pass (Reflective)<br>
            🔴 Fail (Degraded)
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        heatmap_path = os.path.join(SCANS_DIR, f"heatmap_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.html")
        m.save(heatmap_path)
        print(f"🗺️  Heatmap saved: {heatmap_path}")

    # ─────────────────────────────────────────────
    # Feature 9: JSON export
    # ─────────────────────────────────────────────
    def export_json(self):
        """Dump all session records to a JSON file."""
        if not self.all_records:
            return
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.all_records, f, indent=2, ensure_ascii=False)
        print(f"💾 JSON export saved: {self.json_path} ({len(self.all_records)} records)")

    # ─────────────────────────────────────────────
    # Feature 6 (Prioritized Maintenance List)
    # ─────────────────────────────────────────────
    def generate_maintenance_list(self):
        """Generate a priority-sorted maintenance list (worst signs first)."""
        if not self.all_records:
            return

        # Sort by contrast ascending (worst first), then months_remaining ascending
        sorted_records = sorted(
            [r for r in self.all_records if r["status"] == "Fail"],
            key=lambda r: (r["reflectivity_score"], r["months_remaining"])
        )

        if not sorted_records:
            print("✅ No failed signs — no maintenance list needed.")
            return

        with open(self.maintenance_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Priority", "Sign ID", "Sign Type", "Contrast Score",
                "Months Remaining", "Status", "GPS Lat", "GPS Lng",
                "Lighting", "Timestamp"
            ])

            for i, record in enumerate(sorted_records, 1):
                urgency = "🔴 CRITICAL" if record["reflectivity_score"] < ALERT_CRITICAL_THRESHOLD else "🟡 URGENT"
                writer.writerow([
                    f"{i} ({urgency})",
                    record.get("sign_id", "N/A"),
                    record["sign_type"],
                    record["reflectivity_score"],
                    record["months_remaining"],
                    record["status"],
                    record["gps"]["lat"],
                    record["gps"]["lng"],
                    record["lighting"],
                    record["timestamp"],
                ])

        print(f"🔧 Maintenance list saved: {self.maintenance_path} ({len(sorted_records)} signs)")

    # ─────────────────────────────────────────────
    # Feature 4 (PDF Report): Auto-generated report
    # ─────────────────────────────────────────────
    def generate_pdf_report(self):
        """Generate a PDF scan report with charts and summary."""
        if not self.all_records:
            print("⚠️  No records for PDF report.")
            return

        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_pdf import PdfPages
        except ImportError:
            print("⚠️  matplotlib not installed. Skipping PDF. Install with: pip install matplotlib")
            return

        s = self.stats
        total = s["total_unique"]
        if total == 0:
            return

        try:
            with PdfPages(self.pdf_path) as pdf:
                # ── Page 1: Title & Summary ──
                fig, ax = plt.subplots(figsize=(8.5, 11))
                ax.axis('off')

                # Title
                ax.text(0.5, 0.92, "NHAI Road Sign Scan Report",
                        fontsize=22, fontweight='bold', ha='center',
                        color='#1a237e')
                ax.text(0.5, 0.88, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        fontsize=11, ha='center', color='#666')
                ax.text(0.5, 0.85, "National Highways Authority of India",
                        fontsize=12, ha='center', color='#333')

                # Divider
                ax.axhline(y=0.83, xmin=0.1, xmax=0.9, color='#1a237e', linewidth=2)

                # Summary stats
                summary_lines = [
                    f"Total Signs Detected:    {total}",
                    f"Pass (Reflective):       {s['pass_count']}",
                    f"Fail (Degraded):         {s['fail_count']}",
                    f"Critical (< {ALERT_CRITICAL_THRESHOLD}):       {s['critical_count']}",
                    f"Skipped (Low Conf):      {s['skipped_low_conf']}",
                    f"Skipped (Duplicates):    {s['skipped_duplicate']}",
                    f"Day Frames:              {s['day_frames']}",
                    f"Night Frames:            {s['night_frames']}",
                    f"QR Codes Generated:      {s['qr_codes_generated']}",
                    f"Telegram Alerts Sent:    {s['alerts_sent']}",
                ]

                y_pos = 0.78
                for line in summary_lines:
                    ax.text(0.15, y_pos, line, fontsize=11, fontfamily='monospace',
                            color='#333')
                    y_pos -= 0.035

                # Worst sign highlight
                if s["worst_sign"]:
                    ws = s["worst_sign"]
                    y_pos -= 0.02
                    ax.text(0.15, y_pos, "⚠️ WORST SIGN:", fontsize=12,
                            fontweight='bold', color='#d32f2f')
                    y_pos -= 0.035
                    ax.text(0.15, y_pos,
                            f"    {ws[0]} | Contrast: {ws[1]} | GPS: ({ws[2][0]:.4f}, {ws[2][1]:.4f})",
                            fontsize=10, color='#d32f2f')

                pdf.savefig(fig)
                plt.close(fig)

                # ── Page 2: Pass/Fail Pie Chart + Sign Type Bar Chart ──
                fig, axes = plt.subplots(1, 2, figsize=(11, 5))

                # Pie chart
                if s["pass_count"] + s["fail_count"] > 0:
                    sizes = [s["pass_count"], s["fail_count"]]
                    labels_pie = ["Pass", "Fail"]
                    colors_pie = ["#4caf50", "#f44336"]
                    explode = (0, 0.05)
                    axes[0].pie(sizes, explode=explode, labels=labels_pie, colors=colors_pie,
                                autopct='%1.1f%%', shadow=True, startangle=90,
                                textprops={'fontsize': 12})
                    axes[0].set_title("Pass / Fail Distribution", fontsize=14, fontweight='bold')

                # Bar chart for sign types
                if s["signs_by_type"]:
                    sorted_types = sorted(s["signs_by_type"].items(), key=lambda x: -x[1])[:10]
                    types_names = [t[0][:15] for t in sorted_types]
                    types_counts = [t[1] for t in sorted_types]

                    bars = axes[1].barh(types_names, types_counts, color='#1976d2')
                    axes[1].set_xlabel("Count", fontsize=11)
                    axes[1].set_title("Top Sign Types", fontsize=14, fontweight='bold')
                    axes[1].invert_yaxis()

                    for bar, count in zip(bars, types_counts):
                        axes[1].text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                                     str(count), va='center', fontsize=9)

                plt.tight_layout()
                pdf.savefig(fig)
                plt.close(fig)

                # ── Page 3: Contrast Distribution Histogram ──
                if s["contrast_values"]:
                    fig, ax = plt.subplots(figsize=(8, 5))
                    values = s["contrast_values"]
                    n, bins, patches = ax.hist(values, bins=20, color='#42a5f5',
                                                edgecolor='white', alpha=0.8)

                    # Color bars below threshold red
                    for patch, left_edge in zip(patches, bins[:-1]):
                        if left_edge < MIN_WEBER_THRESHOLD:
                            patch.set_facecolor('#ef5350')

                    ax.axvline(x=MIN_WEBER_THRESHOLD, color='#d32f2f', linestyle='--',
                               linewidth=2, label=f'Threshold ({MIN_WEBER_THRESHOLD})')
                    ax.set_xlabel("Weber Contrast Score", fontsize=12)
                    ax.set_ylabel("Number of Signs", fontsize=12)
                    ax.set_title("Contrast Score Distribution", fontsize=14, fontweight='bold')
                    ax.legend(fontsize=10)

                    avg_cr = np.mean(values)
                    ax.axvline(x=avg_cr, color='#1565c0', linestyle=':',
                               linewidth=1.5, label=f'Average ({avg_cr:.2f})')
                    ax.legend(fontsize=10)

                    plt.tight_layout()
                    pdf.savefig(fig)
                    plt.close(fig)

            print(f"📄 PDF report saved: {self.pdf_path}")

        except Exception as e:
            print(f"⚠️  PDF generation failed: {e}")

    # ─────────────────────────────────────────────
    # Feature 13: Terminal scan summary
    # ─────────────────────────────────────────────
    def print_summary(self):
        """Print a formatted summary table of the scan session."""
        s = self.stats
        total = s["total_unique"]
        avg_cr = np.mean(s["contrast_values"]) if s["contrast_values"] else 0

        elapsed = time.time() - self.session_start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        divider = "═" * 60
        print(f"\n{divider}")
        print("         📊  NHAI SCAN SESSION SUMMARY")
        print(divider)
        print(f"  {'Session Duration':<40} {mins:02d}:{secs:02d}")
        print(f"  {'Total Unique Signs Detected':<40} {total:>8}")
        print(f"  {'├── Pass (Reflective)':<40} {s['pass_count']:>8}")
        print(f"  {'├── Fail (Degraded)':<40} {s['fail_count']:>8}")
        print(f"  {'├── Critical (Urgent)':<40} {s['critical_count']:>8}")
        print(f"  {'Skipped (Low Confidence)':<40} {s['skipped_low_conf']:>8}")
        print(f"  {'Skipped (Duplicates Across Frames)':<40} {s['skipped_duplicate']:>8}")
        print(f"  {'Average Weber Contrast':<40} {avg_cr:>8.3f}")
        print(f"  {'Day Frames':<40} {s['day_frames']:>8}")
        print(f"  {'Night Frames':<40} {s['night_frames']:>8}")
        print(f"  {'Telegram Alerts Sent':<40} {s['alerts_sent']:>8}")
        print(f"  {'QR Codes Generated':<40} {s['qr_codes_generated']:>8}")

        if s["worst_sign"]:
            ws = s["worst_sign"]
            sign_id = ws[3] if len(ws) > 3 else "N/A"
            print(f"\n  ⚠️  Worst Sign: {ws[0]} [{sign_id}] (CR: {ws[1]}) at ({ws[2][0]:.4f}, {ws[2][1]:.4f})")

        if s["signs_by_type"]:
            print(f"\n  {'Sign Type':<35} {'Count':>8}")
            print(f"  {'─' * 35} {'─' * 8}")
            for stype, count in sorted(s["signs_by_type"].items(), key=lambda x: -x[1]):
                print(f"  {stype:<35} {count:>8}")

        pass_rate = (s["pass_count"] / total * 100) if total > 0 else 0
        print(f"\n  ✅ Overall Pass Rate: {pass_rate:.1f}%")
        print(f"\n  📁 Output Files:")
        print(f"     ├── CSV:          {self.csv_path}")
        print(f"     ├── JSON:         {self.json_path}")
        print(f"     ├── PDF Report:   {self.pdf_path}")
        print(f"     ├── Maintenance:  {self.maintenance_path}")
        print(f"     └── QR Codes:     {QR_CODE_DIR}/")
        print(divider)

    # ─────────────────────────────────────────────
    # Cleanup: flush, export, summarize
    # ─────────────────────────────────────────────
    def finalize(self):
        """Call on session end to flush buffers and generate all outputs."""
        print("\n🔄 Finalizing scan session...")
        self.flush_buffer()
        self.retry_failed()
        self.export_json()
        self.generate_maintenance_list()
        self.generate_heatmap()
        self.generate_pdf_report()
        self.print_summary()


if __name__ == "__main__":
    engine = RetroreflectivityEngine(overlay_lang=OVERLAY_LANGUAGE)
    cap = cv2.VideoCapture("highway_test.mp4") # Or whatever your video is named

    if not cap.isOpened():
        print("❌ Error: Could not open video source.")
        exit(1)

    print("▶️  Scanning started. Press 'q' to stop.\n")

    # --- PERFORMANCE SETTINGS ---
    MAX_FRAMES = 1000 # Scan for a much longer time (approx 3 minutes at 3x skip)
    FRAME_SKIP = 3   # Process 1 out of every 3 frames for 3x speedup
    frames_processed = 0
    last_processed_frame = None

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # 🚀 OPTIMIZATION 1: Resize high-res video to 720p
            h, w = frame.shape[:2]
            if w > 1280:
                frame = cv2.resize(frame, (1280, int(h * 1280 / w)))

            # 🚀 OPTIMIZATION 2: Frame Skipping
            if frames_processed % FRAME_SKIP == 0:
                processed_frame = engine.process_frame(frame)
                last_processed_frame = processed_frame
            
            # Show the frame (will look like ~10fps but runs real-time)
            if last_processed_frame is not None:
                cv2.imshow("NHAI Dashcam AI", last_processed_frame)

            frames_processed += 1
            
            # The Kill Switch
            if frames_processed >= MAX_FRAMES:
                print(f"\n🛑 Demo limit of {MAX_FRAMES} frames reached. Forcing completion...")
                break

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        print("\n⏹️  Scan interrupted by user.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        engine.finalize() # This forces the PDF and CSV to generate immediately!