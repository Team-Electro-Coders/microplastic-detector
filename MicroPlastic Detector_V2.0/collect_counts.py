import cv2
import csv
import os

# -------- SETTINGS --------
VIDEO_SOURCE = "http://10.85.145.152:8080/video"
OUTPUT_CSV = "frame_counts.csv"
SAVE_FRAMES = True
SAVE_DIR = "collected_frames"
PARTICLE_AREA_MIN = 5
PARTICLE_AREA_MAX = 500
# --------------------------

cap = cv2.VideoCapture(VIDEO_SOURCE)
if not cap.isOpened():
    print("[ERROR] Cannot open stream")
    exit()

csv_file = open(OUTPUT_CSV, "w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["filename", "count"])

frame_id = 0
print("[INFO] Collecting... press 'q' to stop")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    _, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    count = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if PARTICLE_AREA_MIN < area < PARTICLE_AREA_MAX:
            count += 1
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 1)

    filename = f"frame_{frame_id}.jpg"
    csv_writer.writerow([filename, count])

    if SAVE_FRAMES:
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)
        cv2.imwrite(f"{SAVE_DIR}/{filename}", frame)

    cv2.putText(frame, f"Count: {count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.imshow("Collect Counts", frame)

    frame_id += 1

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
csv_file.close()
cv2.destroyAllWindows()
print(f"[INFO] Saved results to {OUTPUT_CSV}")
