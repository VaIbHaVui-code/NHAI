import cv2
import numpy as np
import os

def enhance_frame(frame):
    # 1. Convert to LAB color space (L=Luminance, A/B=Color channels)
    # This allows us to adjust brightness without messing up the colors
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # 2. Apply CLAHE to the L-channel
    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)

    # 3. Merge back and convert to BGR
    limg = cv2.merge((cl, a, b))
    enhanced_frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    return enhanced_frame

def process_video(input_path, output_path):
    cap = cv2.VideoCapture(input_path)
    
    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Setup Output Writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    print("🛠 Enhancing video frames...")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        # Apply the enhancement
        clean_frame = enhance_frame(frame)
        out.write(clean_frame)
        
    cap.release()
    out.release()
    print(f"✅ Cleaned video saved to: {output_path}")

if __name__ == "__main__":
    # Use the same path logic we set up in mock_gps
    input_vid = "video_lab/raw_footage/highway_test.mp4"
    output_vid = "video_lab/processed/highway_enhanced.mp4"
    
    if os.path.exists(input_vid):
        process_video(input_vid, output_vid)
    else:
        print("Error: Raw video not found.")