#!/usr/bin/env python3
"""
ESP32 Microplastic Detector - PC Client Main Application
Enhanced and optimized version with better error handling and performance
"""

import cv2
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

from detector import ParticleDetector
from web_server import WebServer
from esp32_client import ESP32Client
from data_logger import DataLogger

class MicroplasticDetectorApp:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.running = False
        self.headless = False
        
        # Initialize components
        self.detector = ParticleDetector(self.config['detection'])
        self.esp32 = ESP32Client(self.config['esp32'])
        self.logger = DataLogger(self.config.get('logging', {}))
        self.web_server = WebServer(self.config['web'], self)
        
        # Video capture
        self.cap = None
        self.current_frame = None
        self.current_stats = {
            'particle_count': 0,
            'mean_size_mm': 0.0,
            'std_size_mm': 0.0,
            'concentration_per_ml': 0.0,
            'particles_sizes': [],
            'timestamp': time.time(),
            'fps': 0.0
        }
        # Start time for uptime/health checks
        self.start_time = time.time()
        
        # Threading
        self.detection_thread = None
        self.frame_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        
    def load_config(self, config_path):
        """Load configuration from JSON file with defaults"""
        default_config = {
            "esp32": {"ip": "192.168.4.1", "port": 80},
            "camera": {"source": 0, "width": 640, "height": 480, "fps": 30},
            "detection": {
                "scale_mm_per_pixel": 0.01,
                "min_particle_area": 50,
                "max_particle_area": 5000,
                "threshold_value": 60,
                "gaussian_blur": 5,
                "gaussian_sigma": 1
            },
            "volume": {"sample_volume_ml": 0.05},
            "web": {"host": "0.0.0.0", "port": 5000, "debug": False},
            "logging": {
                "log_file": "data/logs/detections.csv",
                "auto_log_interval": 30
            }
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                # Merge with defaults
                config = {**default_config, **user_config}
            else:
                config = default_config
                # Save default config
                self.save_config(config, config_path)
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
            config = default_config
            
        return config
    
    def save_config(self, config, config_path):
        """Save configuration to JSON file"""
        try:
            dirpath = os.path.dirname(config_path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def initialize_camera(self, camera_source=None):
        """Initialize camera with error handling"""
        source = camera_source or self.config['camera']['source']
        
        try:
            if isinstance(source, str) and source.startswith('http'):
                # IP camera
                print(f"Connecting to IP camera: {source}")
                self.cap = cv2.VideoCapture(source)
            else:
                # Local camera
                print(f"Connecting to local camera: {source}")
                self.cap = cv2.VideoCapture(int(source))
            
            if not self.cap.isOpened():
                raise Exception(f"Could not open camera: {source}")
            
            # Set camera properties
            cam_config = self.config['camera']
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_config['width'])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_config['height'])
            self.cap.set(cv2.CAP_PROP_FPS, cam_config['fps'])
            
            # Test frame capture
            ret, frame = self.cap.read()
            if not ret:
                raise Exception("Could not capture test frame")
            
            print(f"Camera initialized: {frame.shape[1]}x{frame.shape[0]}")
            return True
            
        except Exception as e:
            print(f"Camera initialization failed: {e}")
            return False
    
    def detection_loop(self, headless=False):
        """Main detection loop running in separate thread"""
        fps_counter = 0
        fps_start_time = time.time()
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to capture frame; retrying...")
                    time.sleep(0.05)
                    continue
                
                # Process frame
                processed_frame, particles = self.detector.detect_particles(frame)
                
                # Calculate statistics
                particle_count = len(particles)
                mean_size = sum(particles) / len(particles) if particles else 0.0
                std_size = 0.0  # Calculate standard deviation if needed
                
                # Calculate concentration
                volume_ml = self.config['volume']['sample_volume_ml']
                concentration = (particle_count / volume_ml) if volume_ml > 0 else 0.0
                
                # Update current stats
                with self.stats_lock:
                    self.current_stats.update({
                        'particle_count': particle_count,
                        'mean_size_mm': mean_size,
                        'std_size_mm': std_size,
                        'concentration_per_ml': concentration,
                        'particles_sizes': particles.copy(),
                        'timestamp': time.time()
                    })
                
                # Update current frame
                with self.frame_lock:
                    self.current_frame = processed_frame.copy()
                
                # Send to ESP32
                esp32_data = {
                    'count': particle_count,
                    'mean_size_mm': round(mean_size, 3),
                    'concentration_per_ml': round(concentration, 1)
                }
                self.esp32.send_stats(esp32_data)
                
                # Log data
                self.logger.log_detection(self.current_stats)
                
                # Display frame (if not headless)
                if not headless:
                    cv2.imshow("Microplastic Detection", processed_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                # Calculate FPS
                fps_counter += 1
                if fps_counter % 30 == 0:  # Update every 30 frames
                    current_time = time.time()
                    fps = 30 / (current_time - fps_start_time)
                    with self.stats_lock:
                        self.current_stats['fps'] = fps
                    fps_start_time = current_time
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Detection loop error: {e}")
                time.sleep(0.1)  # Prevent tight error loop
        
        print("Detection loop ended")
    
    def get_current_stats(self):
        """Get current detection statistics (thread-safe)"""
        with self.stats_lock:
            return self.current_stats.copy()
    
    def get_current_frame(self):
        """Get current processed frame (thread-safe)"""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            return None
    
    def start(self, headless=False, camera_source=None):
        """Start the detection system"""
        print("Starting Microplastic Detector...")
        self.headless = headless
        
        # Initialize camera
        if not self.initialize_camera(camera_source):
            return False
        
        # Connect to ESP32
        if self.esp32.connect():
            print("ESP32 connected")
        else:
            print("Warning: ESP32 connection failed, continuing without it")
        
        # Start web server
        self.web_server.start()
        
        # Start detection
        self.running = True
        self.detection_thread = threading.Thread(
            target=self.detection_loop, 
            args=(headless,),
            daemon=True
        )
        self.detection_thread.start()
        
        print(f"Web dashboard available at: http://localhost:{self.config['web']['port']}")
        return True
    
    def stop(self):
        """Stop the detection system"""
        print("Stopping Microplastic Detector...")
        
        self.running = False
        
        if self.detection_thread:
            self.detection_thread.join(timeout=5.0)
        
        if self.cap:
            self.cap.release()
        
        if not self.headless:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        self.web_server.stop()
        self.logger.close()
        
        print("System stopped")
    
    def calibrate_scale(self):
        """Interactive scale calibration"""
        print("Starting scale calibration...")
        
        if not self.cap:
            print("Camera not initialized")
            return False
        
        # Capture calibration frame
        ret, frame = self.cap.read()
        if not ret:
            print("Could not capture calibration frame")
            return False
        
        # Simple calibration interface
        points = []
        
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                points.append((x, y))
                cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
                cv2.imshow("Calibration", frame)
        
        cv2.imshow("Calibration", frame)
        cv2.setMouseCallback("Calibration", mouse_callback)
        
        print("Click two points on an object of known size, then press any key")
        cv2.waitKey(0)
        
        if len(points) >= 2:
            # Calculate pixel distance
            pixel_distance = ((points[1][0] - points[0][0])**2 + 
                            (points[1][1] - points[0][1])**2)**0.5
            
            # Get actual distance from user
            try:
                actual_mm = float(input("Enter actual distance in mm: "))
                scale = actual_mm / pixel_distance
                
                # Update configuration
                self.config['detection']['scale_mm_per_pixel'] = scale
                self.save_config(self.config, "config.json")
                
                print(f"Calibration complete! Scale: {scale:.6f} mm/pixel")
                cv2.destroyAllWindows()
                return True
                
            except ValueError:
                print("Invalid distance entered")
        
        cv2.destroyAllWindows()
        return False

def main():
    parser = argparse.ArgumentParser(description="ESP32 Microplastic Detector")
    parser.add_argument('--camera', type=str, default=None,
                       help='Camera source (0, 1, or IP camera URL)')
    parser.add_argument('--esp-ip', type=str, default=None,
                       help='ESP32 IP address')
    parser.add_argument('--config', type=str, default='config.json',
                       help='Configuration file path')
    parser.add_argument('--calibrate', action='store_true',
                       help='Run scale calibration')
    parser.add_argument('--headless', action='store_true',
                       help='Run without OpenCV display window')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Create directories
    os.makedirs('data/logs', exist_ok=True)
    os.makedirs('data/exports', exist_ok=True)
    
    # Initialize app
    app = MicroplasticDetectorApp(args.config)
    
    # Override ESP32 IP if provided
    if args.esp_ip:
        app.config['esp32']['ip'] = args.esp_ip
    
    # Enable debug mode
    if args.debug:
        app.config['web']['debug'] = True
    
    try:
        if args.calibrate:
            # Run calibration mode
            if not app.initialize_camera(args.camera):
                sys.exit(1)
            app.calibrate_scale()
        else:
            # Run normal detection
            if not app.start(args.headless, args.camera):
                sys.exit(1)
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            
    finally:
        app.stop()

if __name__ == "__main__":
    main()