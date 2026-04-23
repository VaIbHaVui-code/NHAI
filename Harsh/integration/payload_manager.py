import requests
from datetime import datetime, timezone

# Configuration
GPS_API_URL = "http://localhost:8000/get_location"
BACKEND_API_URL = "http://localhost:5000/api/signs" 

def stitch_and_send(frame_id, sign_type, contrast_ratio, status, months_remaining, confidence, lighting):
    """
    The 'Stitcher' function that combines AI data with GPS data and sends it to the DB.
    """
    try:
        # 1. Fetch the synced GPS from mock_gps.py
        gps_resp = requests.get(f"{GPS_API_URL}/{frame_id}")
        if gps_resp.status_code != 200:
            print(f"⚠️ Could not fetch GPS for frame {frame_id}. Is mock_gps.py running?")
            return

        gps_data = gps_resp.json()
        
        # 2. Build the EXACT payload Member 2's backend expects
        payload = {
            "sign_id": f"NHAI-{frame_id}-{int(datetime.now().timestamp())}",
            "sign_type": sign_type,
            "reflectivity_score": contrast_ratio,
            "status": status,
            "months_remaining": months_remaining,
            "gps": {
                "lat": gps_data['coords']['lat'], 
                "lng": gps_data['coords']['lng']
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": confidence,
            "lighting": lighting
        }

        # 3. Send to Backend (IT IS UNCOMMENTED NOW!)
        response = requests.post(BACKEND_API_URL, json=payload)
        
        print(f"🚀 [STITCHER] Synced Frame {frame_id} to GPS. DB Response: [{response.status_code}]")

    except requests.exceptions.ConnectionError:
        print("🚨 Stitcher Error: Could not connect to backend or GPS server. Are they running?")
    except Exception as e:
        print(f"🚨 Stitcher Error: {e}")