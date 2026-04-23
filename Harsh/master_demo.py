import time
from integration.payload_manager import stitch_and_send

def run_full_simulation():
    print("🚦 Starting End-to-End Integration Test...")
    print("Ensure mock_gps.py is running in another terminal!\n")

    # Simulate finding signs at these specific frame intervals
    simulated_detections = [
        {"frame": 100, "type": "Stop Sign", "ratio": 1.1},   # FAILED
        {"frame": 850, "type": "Speed Limit 80", "ratio": 1.7}, # PASSED
        {"frame": 1500, "type": "No Parking", "ratio": 0.9}, # FAILED
        {"frame": 2400, "type": "Yield", "ratio": 1.8},      # PASSED
    ]

    for detection in simulated_detections:
        print(f"🔍 AI found {detection['type']} at Frame {detection['frame']}...")
        
        # Call YOUR stitcher logic
        stitch_and_send(
            frame_id=detection['frame'], 
            sign_type=detection['type'], 
            contrast_ratio=detection['ratio']
        )
        
        time.sleep(2) # Wait 2 seconds between detections for demo purposes

    print("\n✅ Simulation Complete. Check integration/detections_log.json for results.")

if __name__ == "__main__":
    run_full_simulation()