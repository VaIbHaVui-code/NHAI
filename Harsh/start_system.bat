@echo off
echo 🚀 Starting RoadSign AI System...

:: 1. Start the GPS Simulator in the background
start cmd /k "python simulation/mock_gps.py"

echo ⏳ Waiting for GPS Server to warm up...
timeout /t 5

:: 2. Start the AI Detection Engine (Your teammate's script)
echo 🧠 Starting AI Detection Engine...
python ai_engine/main_detection.py

pause