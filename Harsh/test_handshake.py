import requests
import time

# Let's simulate a car "driving" through 5 specific frames
test_frames = [0, 500, 1000, 2000, 4000]

print("--- Starting Integration Test ---")
for f in test_frames:
    try:
        response = requests.get(f"http://127.0.0.1:8000/get_location/{f}")
        data = response.json()
        
        if "coords" in data:
            print(f"✅ Frame {f}: Lat {data['coords']['lat']}, Lng {data['coords']['lng']}")
        else:
            print(f"❌ Frame {f}: Error -> {data.get('error')}")
            
    except Exception as e:
        print(f"🚨 Connection Failed: {e}")
    
    time.sleep(0.5) # Just for readability