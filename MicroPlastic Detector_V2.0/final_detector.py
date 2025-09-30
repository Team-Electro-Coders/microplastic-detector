import cv2
import numpy as np
import serial
import time
import tensorflow as tf
import logging
import os
from collections import deque
import threading
from queue import Queue

# ----------- SETTINGS ------------
VIDEO_SOURCE = "http://10.85.145.152:8080/video"  # Phone IP camera stream
ARDUINO_PORT = "COM9"   # Replace with your Arduino port
BAUD_RATE = 9600

PARTICLE_AREA_MIN = 5
PARTICLE_AREA_MAX = 500

MODEL_PATH = "microplastic_type_model"  # Saved CNN model folder
IMG_SIZE = (128, 128)
CONC_THRESH = [5, 20]  # [Low ≤5, Medium 6-20, High >20]

# Enhanced settings
CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence for classification
SMOOTHING_WINDOW = 5  # Frames for temporal smoothing
LOG_FILE = "detector.log"
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 2
# ---------------------------------

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ArduinoConnection:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.connection = None
        self.connect()
    
    def connect(self):
        """Connect to Arduino with retry mechanism"""
        for attempt in range(RECONNECT_ATTEMPTS):
            try:
                self.connection = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=0.5)
                time.sleep(2)  # Arduino reset time
                logger.info(f"Connected to Arduino on {self.port}")
                return True
            except Exception as e:
                logger.warning(f"Arduino connection attempt {attempt + 1} failed: {e}")
                if attempt < RECONNECT_ATTEMPTS - 1:
                    time.sleep(RECONNECT_DELAY)
        
        logger.error("Failed to connect to Arduino after all attempts")
        self.connection = None
        return False
    
    def send_data(self, data):
        """Send data to Arduino with error handling"""
        if self.connection is None:
            return False
        
        try:
            self.connection.write(data.encode("utf-8"))
            return True
        except Exception as e:
            logger.warning(f"Failed to send data to Arduino: {e}")
            self.connection = None
            return False
    
    def is_connected(self):
        return self.connection is not None

class MicroplasticDetector:
    def __init__(self):
        self.load_model()
        self.arduino = ArduinoConnection(ARDUINO_PORT, BAUD_RATE)
        self.setup_video_capture()
        
        # Smoothing buffers
        self.count_history = deque(maxlen=SMOOTHING_WINDOW)
        self.concentration_history = deque(maxlen=SMOOTHING_WINDOW)
        
        # Statistics
        self.frame_count = 0
        self.detection_stats = {cls: 0 for cls in self.classes}
        
    def load_model(self):
        """Load the trained model with error handling"""
        try:
            if not os.path.exists(MODEL_PATH):
                raise FileNotFoundError(f"Model path {MODEL_PATH} does not exist")
            
            self.model = tf.keras.models.load_model(MODEL_PATH)
            
            classes_file = os.path.join(MODEL_PATH, "classes.txt")
            if not os.path.exists(classes_file):
                raise FileNotFoundError(f"Classes file {classes_file} does not exist")
            
            with open(classes_file, "r") as f:
                self.classes = [line.strip() for line in f.readlines()]
            
            logger.info(f"Model loaded successfully. Classes: {self.classes}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def setup_video_capture(self):
        """Setup video capture with enhanced error handling"""
        self.cap = cv2.VideoCapture(VIDEO_SOURCE)
        
        if not self.cap.isOpened():
            logger.error(f"Cannot open video stream {VIDEO_SOURCE}")
            raise ConnectionError(f"Video source {VIDEO_SOURCE} not accessible")
        
        # Set buffer size to reduce latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Get video properties for logging
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Video capture initialized: {width}x{height} @ {fps}fps")
    
    def preprocess_frame(self, frame):
        """Enhanced frame preprocessing with noise reduction"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        
        # Adaptive thresholding for better performance in varying lighting
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_MEAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return thresh
    
    def predict_type(self, crop):
        """Enhanced type prediction with confidence checking"""
        try:
            if crop.size == 0:
                return "unknown", 0.0, -1
            
            img = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, IMG_SIZE)
            img = img.astype("float32") / 255.0
            img = np.expand_dims(img, axis=0)
            
            preds = self.model.predict(img, verbose=0)
            idx = np.argmax(preds, axis=1)[0]
            prob = float(preds[0, idx])
            
            # Only return classification if confidence is above threshold
            if prob >= CONFIDENCE_THRESHOLD:
                return self.classes[idx], prob, idx
            else:
                return "uncertain", prob, -1
            
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return "error", 0.0, -1
    
    def concentration_from_count(self, count):
        """Enhanced concentration mapping with smoothing"""
        if count <= CONC_THRESH[0]:
            level, code = "Low", 0
        elif count <= CONC_THRESH[1]:
            level, code = "Medium", 1
        else:
            level, code = "High", 2
        
        return level, code
    
    def get_smoothed_concentration(self):
        """Get temporally smoothed concentration"""
        if len(self.concentration_history) == 0:
            return "Low", 0
        
        # Use mode of recent concentrations for stability
        codes = [c[1] for c in self.concentration_history]
        most_common_code = max(set(codes), key=codes.count)
        
        level_map = {0: "Low", 1: "Medium", 2: "High"}
        return level_map[most_common_code], most_common_code
    
    def process_frame(self, frame):
        """Process a single frame and return detection results"""
        thresh = self.preprocess_frame(frame)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        particle_count = 0
        type_counts = {c: 0 for c in self.classes}
        type_counts["uncertain"] = 0
        type_counts["error"] = 0
        
        valid_detections = []
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if PARTICLE_AREA_MIN < area < PARTICLE_AREA_MAX:
                particle_count += 1
                x, y, w, h = cv2.boundingRect(cnt)
                
                # Enhanced padding calculation
                pad = max(4, int(min(w, h) * 0.1))
                x1, y1 = max(0, x - pad), max(0, y - pad)
                x2, y2 = min(frame.shape[1], x + w + pad), min(frame.shape[0], y + h + pad)
                
                crop = frame[y1:y2, x1:x2]
                typ, prob, idx = self.predict_type(crop)
                
                type_counts[typ] += 1
                
                # Store detection info for visualization
                valid_detections.append({
                    'bbox': (x1, y1, x2, y2),
                    'type': typ,
                    'confidence': prob,
                    'area': area
                })
                
                # Update statistics
                if typ in self.detection_stats:
                    self.detection_stats[typ] += 1
        
        return particle_count, type_counts, valid_detections
    
    def draw_detections(self, frame, detections, particle_count, concentration_label, dominant_type):
        """Draw detection results on frame with enhanced visualization"""
        # Draw bounding boxes and labels
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            typ = detection['type']
            conf = detection['confidence']
            
            # Color coding by type confidence
            if typ == "uncertain":
                color = (0, 165, 255)  # Orange
            elif typ == "error":
                color = (0, 0, 255)    # Red
            else:
                color = (0, 255, 0)    # Green
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Label with confidence
            label = f"{typ} {conf:.2f}" if conf > 0 else typ
            cv2.putText(frame, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # Enhanced overlay information
        overlay_y = 30
        line_height = 30
        
        # Main statistics
        cv2.putText(frame, f"Count: {particle_count}", (10, overlay_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        overlay_y += line_height
        
        cv2.putText(frame, f"Concentration: {concentration_label}", (10, overlay_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        overlay_y += line_height
        
        cv2.putText(frame, f"Dominant Type: {dominant_type}", (10, overlay_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        overlay_y += line_height
        
        # Frame counter and connection status
        cv2.putText(frame, f"Frame: {self.frame_count}", (10, overlay_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Arduino connection status
        status_color = (0, 255, 0) if self.arduino.is_connected() else (0, 0, 255)
        status_text = "Arduino: OK" if self.arduino.is_connected() else "Arduino: DISC"
        cv2.putText(frame, status_text, (frame.shape[1] - 150, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)
        
        return frame
    
    def run(self):
        """Main detection loop with enhanced error handling"""
        logger.info("Starting real-time microplastic detection...")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Failed to read frame, attempting to reconnect...")
                    self.cap.release()
                    time.sleep(1)
                    self.setup_video_capture()
                    continue
                
                self.frame_count += 1
                
                # Process frame
                particle_count, type_counts, detections = self.process_frame(frame)
                
                # Update smoothing buffers
                self.count_history.append(particle_count)
                
                # Calculate concentration
                concentration_label, concentration_code = self.concentration_from_count(particle_count)
                self.concentration_history.append((concentration_label, concentration_code))
                
                # Get smoothed concentration for Arduino
                smooth_conc_label, smooth_conc_code = self.get_smoothed_concentration()
                
                # Determine dominant type
                if particle_count > 0:
                    # Exclude uncertain and error from dominant type calculation
                    valid_types = {k: v for k, v in type_counts.items() 
                                 if k in self.classes and v > 0}
                    if valid_types:
                        dominant_type = max(valid_types.items(), key=lambda x: x[1])[0]
                        type_index = self.classes.index(dominant_type)
                    else:
                        dominant_type = "uncertain"
                        type_index = -1
                else:
                    dominant_type = "none"
                    type_index = -1
                
                # Send to Arduino (using smoothed values for stability)
                if self.arduino.is_connected():
                    msg = f"C{smooth_conc_code};T{type_index}\n"
                    if not self.arduino.send_data(msg):
                        logger.info("Attempting to reconnect to Arduino...")
                        self.arduino.connect()
                
                # Draw and display
                frame = self.draw_detections(frame, detections, particle_count, 
                                           concentration_label, dominant_type)
                
                cv2.imshow("Enhanced Microplastic Detector", frame)
                
                # Check for quit
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("r"):  # Reset statistics
                    self.detection_stats = {cls: 0 for cls in self.classes}
                    logger.info("Statistics reset")
                elif key == ord("s"):  # Save current frame
                    cv2.imwrite(f"detection_frame_{self.frame_count}.jpg", frame)
                    logger.info(f"Frame saved as detection_frame_{self.frame_count}.jpg")
        
        except KeyboardInterrupt:
            logger.info("Detection stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()
        if self.arduino.is_connected():
            self.arduino.connection.close()
        
        # Log final statistics
        logger.info("Final detection statistics:")
        for class_name, count in self.detection_stats.items():
            logger.info(f"  {class_name}: {count}")

if __name__ == "__main__":
    try:
        detector = MicroplasticDetector()
        detector.run()
    except Exception as e:
        logger.error(f"Failed to initialize detector: {e}")
        print(f"Error: {e}")
        print("Please check your camera connection, model files, and Arduino setup.")