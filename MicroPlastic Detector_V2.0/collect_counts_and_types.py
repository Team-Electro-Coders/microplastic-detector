import cv2
import csv
import os
import tensorflow as tf
import numpy as np
import time
import logging
from datetime import datetime

# -------- SETTINGS --------
VIDEO_SOURCE = "http://10.85.145.152:8080/video"
OUTPUT_CSV = "frame_counts_types.csv"
SAVE_FRAMES = True
SAVE_DIR = "collected_frames"
PARTICLE_AREA_MIN = 5
PARTICLE_AREA_MAX = 500

MODEL_PATH = "microplastic_type_model"
IMG_SIZE = (128, 128)
CONFIDENCE_THRESHOLD = 0.6  # Only count high-confidence predictions

# Enhanced settings
LOG_FILE = "collection.log"
COLLECTION_INTERVAL = 0.5  # Seconds between collections
MAX_FRAMES = 1000  # Maximum frames to collect (0 = unlimited)
AUTO_EXPOSURE_FRAMES = 30  # Frames to skip for auto-exposure
# --------------------------

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

class EnhancedCollector:
    def __init__(self):
        self.setup_video_capture()
        self.load_model()
        self.setup_output()
        
        # Statistics
        self.frames_collected = 0
        self.total_particles = 0
        self.start_time = time.time()
        
    def setup_video_capture(self):
        """Setup video capture with enhanced settings"""
        self.cap = cv2.VideoCapture(VIDEO_SOURCE)
        
        if not self.cap.isOpened():
            raise ConnectionError(f"Cannot open video stream: {VIDEO_SOURCE}")
        
        # Set capture properties for better performance
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
        
        # Log video properties
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.info(f"Video capture initialized: {width}x{height} @ {fps}fps")
        logger.info(f"Video source: {VIDEO_SOURCE}")
        
    def load_model(self):
        """Load the trained model with error handling"""
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
        
        try:
            self.model = tf.keras.models.load_model(MODEL_PATH)
            
            classes_file = os.path.join(MODEL_PATH, "classes.txt")
            with open(classes_file, "r") as f:
                self.classes = [line.strip() for line in f.readlines()]
            
            logger.info(f"Model loaded successfully")
            logger.info(f"Classes: {self.classes}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def setup_output(self):
        """Setup output files and directories"""
        # Create output directory
        if SAVE_FRAMES and not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)
            logger.info(f"Created frame directory: {SAVE_DIR}")
        
        # Initialize CSV file
        self.csv_file = open(OUTPUT_CSV, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        
        # Write header with all class names
        header = ["timestamp", "filename", "total_count"] + self.classes + ["uncertain", "error"]
        self.csv_writer.writerow(header)
        
        logger.info(f"CSV output: {OUTPUT_CSV}")
        logger.info(f"CSV header: {header}")
    
    def preprocess_frame(self, frame):
        """Enhanced frame preprocessing"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        
        # Adaptive thresholding for varying lighting conditions
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
                return "error", 0.0
            
            # Preprocess crop
            img = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, IMG_SIZE)
            img = img.astype("float32") / 255.0
            img = np.expand_dims(img, axis=0)
            
            # Predict
            preds = self.model.predict(img, verbose=0)
            idx = np.argmax(preds, axis=1)[0]
            prob = float(preds[0, idx])
            
            # Apply confidence threshold
            if prob >= CONFIDENCE_THRESHOLD:
                return self.classes[idx], prob
            else:
                return "uncertain", prob
                
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return "error", 0.0
    
    def process_frame(self, frame, frame_id):
        """Process a single frame and extract particle data"""
        # Preprocess frame
        thresh = self.preprocess_frame(frame)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Initialize counters
        particle_count = 0
        type_counts = {cls: 0 for cls in self.classes}
        type_counts["uncertain"] = 0
        type_counts["error"] = 0
        
        # Process each contour
        for cnt in contours:
            area = cv2.contourArea(cnt)
            
            if PARTICLE_AREA_MIN < area < PARTICLE_AREA_MAX:
                particle_count += 1
                x, y, w, h = cv2.boundingRect(cnt)
                
                # Enhanced padding based on particle size
                pad = max(4, int(min(w, h) * 0.1))
                x1, y1 = max(0, x - pad), max(0, y - pad)
                x2, y2 = min(frame.shape[1], x + w + pad), min(frame.shape[0], y + h + pad)
                
                # Extract crop and predict type
                crop = frame[y1:y2, x1:x2]
                particle_type, confidence = self.predict_type(crop)
                type_counts[particle_type] += 1
                
                # Draw visualization
                color = self.get_color_for_type(particle_type)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Add label with confidence
                label = f"{particle_type[:4]} {confidence:.2f}"
                cv2.putText(frame, label, (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # Update statistics
        self.total_particles += particle_count
        
        return particle_count, type_counts, frame
    
    def get_color_for_type(self, particle_type):
        """Get color for particle type visualization"""
        color_map = {
            "fiber": (0, 255, 0),      # Green
            "fragment": (255, 0, 0),    # Blue
            "film": (0, 255, 255),      # Yellow
            "bead": (255, 0, 255),      # Magenta
            "other": (255, 255, 0),     # Cyan
            "uncertain": (0, 165, 255), # Orange
            "error": (0, 0, 255)        # Red
        }
        return color_map.get(particle_type, (128, 128, 128))  # Gray default
    
    def add_frame_overlay(self, frame, particle_count, type_counts):
        """Add informational overlay to frame"""
        overlay_y = 30
        line_height = 25
        
        # Main statistics
        cv2.putText(frame, f"Frame: {self.frames_collected}", (10, overlay_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        overlay_y += line_height
        
        cv2.putText(frame, f"Particles: {particle_count}", (10, overlay_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        overlay_y += line_height
        
        # Type breakdown (only show non-zero counts)
        active_types = {k: v for k, v in type_counts.items() if v > 0}
        if active_types:
            cv2.putText(frame, "Types:", (10, overlay_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            overlay_y += 20
            
            for particle_type, count in active_types.items():
                color = self.get_color_for_type(particle_type)
                cv2.putText(frame, f"  {particle_type}: {count}", (10, overlay_y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                overlay_y += 18
        
        # Collection progress
        if MAX_FRAMES > 0:
            progress = self.frames_collected / MAX_FRAMES
            cv2.putText(frame, f"Progress: {progress*100:.1f}%", (10, frame.shape[0] - 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Performance stats
        elapsed = time.time() - self.start_time
        fps = self.frames_collected / elapsed if elapsed > 0 else 0
        cv2.putText(frame, f"FPS: {fps:.1f}", (frame.shape[1] - 100, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return frame
    
    def save_frame_data(self, particle_count, type_counts, filename):
        """Save frame data to CSV"""
        timestamp = datetime.now().isoformat()
        
        # Prepare row data
        row = [timestamp, filename, particle_count]
        for cls in self.classes:
            row.append(type_counts[cls])
        row.append(type_counts["uncertain"])
        row.append(type_counts["error"])
        
        # Write to CSV
        self.csv_writer.writerow(row)
        
        # Flush to ensure data is written
        self.csv_file.flush()
    
    def collect(self):
        """Main collection loop"""
        logger.info("Starting enhanced data collection...")
        logger.info(f"Press 'q' to stop, 's' to skip frame, 'p' to pause")
        
        # Skip initial frames for auto-exposure
        logger.info(f"Skipping {AUTO_EXPOSURE_FRAMES} frames for auto-exposure...")
        for _ in range(AUTO_EXPOSURE_FRAMES):
            ret, _ = self.cap.read()
            if not ret:
                break
        
        paused = False
        last_collection_time = 0
        
        try:
            while True:
                # Check frame limit
                if MAX_FRAMES > 0 and self.frames_collected >= MAX_FRAMES:
                    logger.info(f"Reached maximum frames ({MAX_FRAMES})")
                    break
                
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Failed to read frame")
                    break
                
                # Check collection interval
                current_time = time.time()
                if current_time - last_collection_time < COLLECTION_INTERVAL:
                    cv2.imshow("Enhanced Collection", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    elif key == ord("p"):
                        paused = not paused
                        logger.info(f"Collection {'paused' if paused else 'resumed'}")
                    continue
                
                if paused:
                    cv2.putText(frame, "PAUSED - Press 'p' to resume", 
                               (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    cv2.imshow("Enhanced Collection", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    elif key == ord("p"):
                        paused = False
                        logger.info("Collection resumed")
                    continue
                
                # Process frame
                particle_count, type_counts, processed_frame = self.process_frame(frame, self.frames_collected)
                
                # Add overlay
                processed_frame = self.add_frame_overlay(processed_frame, particle_count, type_counts)
                
                # Save frame data
                filename = f"frame_{self.frames_collected:06d}.jpg"
                self.save_frame_data(particle_count, type_counts, filename)
                
                # Save frame image if enabled
                if SAVE_FRAMES:
                    cv2.imwrite(os.path.join(SAVE_DIR, filename), processed_frame)
                
                # Update counters
                self.frames_collected += 1
                last_collection_time = current_time
                
                # Log progress periodically
                if self.frames_collected % 50 == 0:
                    logger.info(f"Collected {self.frames_collected} frames, "
                               f"{self.total_particles} total particles")
                
                # Display frame
                cv2.imshow("Enhanced Collection", processed_frame)
                
                # Handle user input
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("s"):
                    logger.info("Skipped frame")
                    continue
                elif key == ord("p"):
                    paused = True
                    logger.info("Collection paused")
                elif key == ord("r"):
                    # Reset statistics
                    self.total_particles = 0
                    logger.info("Statistics reset")
        
        except KeyboardInterrupt:
            logger.info("Collection interrupted by user")
        
        except Exception as e:
            logger.error(f"Collection error: {e}")
            
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources and save final statistics"""
        logger.info("Cleaning up...")
        
        # Release resources
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()
        
        if hasattr(self, 'csv_file'):
            self.csv_file.close()
        
        # Calculate and log final statistics
        elapsed_time = time.time() - self.start_time
        avg_fps = self.frames_collected / elapsed_time if elapsed_time > 0 else 0
        avg_particles_per_frame = self.total_particles / self.frames_collected if self.frames_collected > 0 else 0
        
        logger.info("=== COLLECTION SUMMARY ===")
        logger.info(f"Total frames collected: {self.frames_collected}")
        logger.info(f"Total particles detected: {self.total_particles}")
        logger.info(f"Average particles per frame: {avg_particles_per_frame:.2f}")
        logger.info(f"Collection time: {elapsed_time:.2f} seconds")
        logger.info(f"Average FPS: {avg_fps:.2f}")
        logger.info(f"Data saved to: {OUTPUT_CSV}")
        if SAVE_FRAMES:
            logger.info(f"Frames saved to: {SAVE_DIR}")
        
        print("\nCollection completed successfully!")
        print(f"Results saved to: {OUTPUT_CSV}")

def main():
    """Main function with enhanced error handling"""
    try:
        collector = EnhancedCollector()
        collector.collect()
        
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        print("Please ensure the model is trained and available.")
        
    except ConnectionError as e:
        print(f"Connection error: {e}")
        print("Please check your camera/video source.")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}")
        
    finally:
        # Ensure cleanup even if collector wasn't fully initialized
        try:
            cv2.destroyAllWindows()
        except:
            pass

if __name__ == "__main__":
    main()