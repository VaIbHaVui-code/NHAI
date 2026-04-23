"""
═══════════════════════════════════════════════════════
  NHAI — YOLOv8 Fine-Tuning on REAL Road Signs
  Dataset: Road signs by Midstem (5.1k images, 169 classes)
  URL: https://universe.roboflow.com/midstem/road-signs-vanga
  Pre-trained metrics: mAP@50=86.9%, Precision=82.7%, Recall=79.6%
═══════════════════════════════════════════════════════
"""

import os
import shutil
from ultralytics import YOLO
import torch

# ═══════════════════════════════════════════════════
ROBOFLOW_API_KEY = "iVRlFmt90UdCvaJXesCC"
EPOCHS = 15
IMG_SIZE = 640
BATCH_SIZE = 4
BASE_MODEL = "yolov8n.pt"
PROJECT_NAME = "nhai_signs"
DATASET_DIR = "./datasets/road_signs"
# ═══════════════════════════════════════════════════


def download_dataset():
    print("═" * 55)
    print("  📥 STEP 1: Downloading Real Road Signs Dataset")
    print("═" * 55)

    from roboflow import Roboflow

    if os.path.exists(DATASET_DIR):
        shutil.rmtree(DATASET_DIR)

    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace("midstem").project("road-signs-vanga")
    version = project.version(1)
    dataset = version.download("yolov8", location=DATASET_DIR)

    print(f"\n  ✅ Dataset downloaded: {dataset.location}")
    return dataset.location


def train_model(dataset_path):
    print("\n" + "═" * 55)
    print("  🧠 STEP 2: Fine-Tuning YOLOv8 on Real Road Signs")
    print("═" * 55)

    data_yaml = os.path.join(dataset_path, "data.yaml")

    # ═════════════════════════════════════════════════════════
    # 🛠️ THE ROBOFLOW FIX
    # ═════════════════════════════════════════════════════════
    with open(data_yaml, 'r') as f:
        yaml_content = f.read()

    # 1. Strip Roboflow's messy relative paths
    yaml_content = yaml_content.replace('../train', 'train')
    yaml_content = yaml_content.replace('../valid', 'valid')
    yaml_content = yaml_content.replace('../test', 'test')

    # 2. Check if the 'valid' folder actually exists on the drive
    valid_dir = os.path.join(dataset_path, "valid")
    if not os.path.exists(valid_dir):
        print("  ⚠️ 'valid' folder missing. Re-routing validation to 'train' split.")
        # Force YOLO to just use the training set for its validation checks
        yaml_content = yaml_content.replace('val: valid/images', 'val: train/images')
        
    with open(data_yaml, 'w') as f:
        f.write(yaml_content)
    # ═════════════════════════════════════════════════════════

    model = YOLO(BASE_MODEL)

    device = "0" if torch.cuda.is_available() else "cpu"

    if device == "cpu":
        print("\n  ⚠️  No CUDA GPU. Training on CPU (slower).")
        print("     Tip: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121\n")

    print(f"  ├── Base model:  {BASE_MODEL}")
    print(f"  ├── Device:      {device}")
    print(f"  ├── Epochs:      {EPOCHS}")
    print(f"  ├── Batch:       {BATCH_SIZE}")
    print(f"  └── Dataset:     {data_yaml}")
    print(f"\n  ⏳ Training started...\n")

    model.train(
        data=data_yaml,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        project=PROJECT_NAME,
        name="train",
        exist_ok=True,
        pretrained=True,
        patience=10,
        workers=2,
        device=device,
    )


def deploy_model():
    print("\n" + "═" * 55)
    print("  📦 STEP 3: Deploying Model")
    print("═" * 55)

    best_pt = os.path.join(PROJECT_NAME, "train", "weights", "best.pt")
    if not os.path.exists(best_pt):
        print(f"  ❌ best.pt not found at {best_pt}")
        return

    shutil.copy2(best_pt, "best.pt")
    print(f"\n  ✅ Model saved: {os.path.abspath('best.pt')}")

    # Auto-update scanning_YOLO.py
    scan_file = "scanning_YOLO.py"
    if os.path.exists(scan_file):
        with open(scan_file, "r", encoding="utf-8") as f:
            content = f.read()
        updated = False
        if 'YOLO("yolov8n.pt")' in content:
            content = content.replace('YOLO("yolov8n.pt")', 'YOLO("best.pt")')
            updated = True
        old_filter = """                # ONLY allow actual infrastructure/sign classes from the standard COCO dataset
                allowed_classes = {"stop sign", "traffic light", "fire hydrant", "parking meter"}
                if sign_type not in allowed_classes:
                    continue"""
        if old_filter in content:
            content = content.replace(old_filter, "                # Custom model — no class filter needed")
            updated = True
        if updated:
            with open(scan_file, "w", encoding="utf-8") as f:
                f.write(content)
            print("  ✅ scanning_YOLO.py auto-updated to use best.pt")


if __name__ == "__main__":
    print("\n  ╔═══════════════════════════════════════════════╗")
    print("  ║   NHAI — Real Road Signs Trainer (5.1k imgs) ║")
    print("  ╚═══════════════════════════════════════════════╝\n")

    dataset_path = download_dataset()
    train_model(dataset_path)
    deploy_model()

    print("\n" + "═" * 55)
    print("  🎉 DONE! Run: python scanning_YOLO.py")
    print("═" * 55 + "\n")
