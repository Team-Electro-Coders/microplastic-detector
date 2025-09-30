import cv2
import numpy as np
import serial
import time

# --- 1. SET YOUR PARAMETERS HERE ---

# Replace with the URL from your IP Webcam app
VIDEO_SOURCE = "http://10.85.145.152:8080/video"

# Replace with the COM port of your ARDUINO
ARDUINO_PORT = 'COM9' # IMPORTANT: Change this to your Arduino's port!

# Detection threshold
PARTICLE_THRESHOLD = 5

# --- 2. SETUP SERIAL CONNECTION TO ARDUINO ---
try:
    # Use the ARDUINO_PORT variable here
    arduino = serial.Serial(port=ARDUINO_PORT, baudrate=9600, timeout=.1)
    print(f"Successfully connected to Arduino on {ARDUINO_PORT}")
    # Wait a moment for the Arduino to reset after connection
    time.sleep(2) 
except serial.SerialException as e:
    print(f"Error: Could not connect to Arduino on {ARDUINO_PORT}. {e}")
    exit()

# --- 3. THE MAIN REAL-TIME LOOP ---
print(f"--- Starting Real-Time Analysis from {VIDEO_SOURCE} ---")
print("Press 'q' in the video window to quit.")

cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    print(f"Error: Could not open video stream at {VIDEO_SOURCE}")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)[1]
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    particle_count_in_frame = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 5 and area < 500:
            particle_count_in_frame += 1
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 0), 2)

    if particle_count_in_frame > PARTICLE_THRESHOLD:
        status = "Microplastic Detected"
        status_color = (0, 0, 255)
        # --- SEND SIGNAL '1' TO ARDUINO ---
        arduino.write(b'1')
    else:
        status = "No Microplastic Detected"
        status_color = (0, 255, 0)
        # --- SEND SIGNAL '0' TO ARDUINO ---
        arduino.write(b'0')

    cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2, cv2.LINE_AA)
    cv2.imshow("Live Microplastic Detector", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- 4. CLEANUP ---
cap.release()
cv2.destroyAllWindows()
arduino.close() # Close the serial connection
print("--- Analysis Stopped ---")