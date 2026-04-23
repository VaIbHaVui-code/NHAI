import cv2
import numpy as np
import os

def play_comparison(raw_path, enhanced_path):
    # Open both video captures
    cap_raw = cv2.VideoCapture(raw_path)
    cap_enhanced = cv2.VideoCapture(enhanced_path)

    # Verify both videos opened
    if not cap_raw.isOpened() or not cap_enhanced.isOpened():
        print("❌ Error: Could not open one or both video files.")
        return

    print("📺 Playing Side-by-Side Comparison...")
    print("⌨️  Press 'q' to quit | Press 'space' to pause")

    paused = False

    while True:
        if not paused:
            ret_r, frame_r = cap_raw.read()
            ret_e, frame_e = cap_enhanced.read()

            # If either video reaches the end, stop
            if not ret_r or not ret_e:
                break

            # 1. Resize frames so they fit on your screen (e.g., 640x360 each)
            # Total window size will be 1280x360
            display_r = cv2.resize(frame_r, (640, 360))
            display_e = cv2.resize(frame_e, (640, 360))

            # 2. Add text labels to the frames
            cv2.putText(display_r, "RAW FOOTAGE", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(display_e, "ENHANCED (CLAHE)", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # 3. Stack them horizontally
            combined = np.hstack((display_r, display_e))

            # 4. Show the combined frame
            cv2.imshow('Project RoadSign AI - Quality Comparison', combined)

        # Keyboard Controls
        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '): # Spacebar to pause
            paused = not paused

    cap_raw.release()
    cap_enhanced.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    # Path logic using your standard structure
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RAW_VID = os.path.join(ROOT, "video_lab", "raw_footage", "highway_test.mp4")
    ENHANCED_VID = os.path.join(ROOT, "video_lab", "processed", "highway_enhanced.mp4")

    play_comparison(RAW_VID, ENHANCED_VID)