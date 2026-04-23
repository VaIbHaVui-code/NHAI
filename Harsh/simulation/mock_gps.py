from fastapi import FastAPI
import xml.etree.ElementTree as ET
import cv2  # Added for dynamic video probing
import os

app = FastAPI()

import os

# --- DYNAMIC CONFIGURATION ---
# This finds the exact folder where mock_gps.py is located on your machine
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# This guarantees it always finds the KML file right next to it
KML_PATH = os.path.join(BASE_DIR, "highway_path.kml")

# This points it back to the ai_engine folder where your video lives
# (If you are still using the webcam, don't worry, the script's 1000-frame fallback will handle it safely!)
VIDEO_PATH = os.path.join(BASE_DIR, "..", "..", "ai_engine", "test_highway.mp4")

def get_video_metadata(path):
    """Dynamically retrieves the total frame count from the video file."""
    if not os.path.exists(path):
        print(f"⚠️ Warning: Video file not found at {path}. Using fallback.")
        return 1000 # Fallback default
    
    cap = cv2.VideoCapture(path)
    # CAP_PROP_FRAME_COUNT gives the total number of frames in the file
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return total_frames

def parse_kml(file_path):
    """Parses KML and returns list of lat/lng dictionaries."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    # Handle KML namespace (often required for find())
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    coords_element = root.find(".//kml:coordinates", ns)
    
    if coords_element is None:
        # Fallback if namespace is different
        coords_text = root.find(".//coordinates").text.strip()
    else:
        coords_text = coords_element.text.strip()

    points = []
    for item in coords_text.split():
        lng, lat, _ = item.split(',')
        points.append({"lat": float(lat), "lng": float(lng)})
    return points

# --- Initialize Data on Startup ---
VIDEO_TOTAL_FRAMES = get_video_metadata(VIDEO_PATH)
GPS_POINTS = parse_kml(KML_PATH)
TOTAL_POINTS = len(GPS_POINTS)

print(f"✅ Integration Ready:")
print(f"   - Video Frames: {VIDEO_TOTAL_FRAMES}")
print(f"   - GPS Waypoints: {TOTAL_POINTS}")

@app.get("/get_location/{frame_id}")
def get_location(frame_id: int):
    # The Sync Logic: Maps current frame to the corresponding GPS index
    if frame_id >= VIDEO_TOTAL_FRAMES:
        return {"error": "End of video", "frame_id": frame_id}
    
    # Calculate mapping: (Current Frame / Total Frames) * Total GPS Points
    index = int((frame_id / VIDEO_TOTAL_FRAMES) * TOTAL_POINTS)
    index = min(index, TOTAL_POINTS - 1) # Safety check
    
    return {
        "frame_id": frame_id,
        "total_video_frames": VIDEO_TOTAL_FRAMES,
        "coords": GPS_POINTS[index],
        "speed_kmh": 80.0,
        "status": "SYNCED"
    }

if __name__ == "__main__":
    import uvicorn
    # Start the local microservice
    uvicorn.run(app, host="127.0.0.1", port=8000)