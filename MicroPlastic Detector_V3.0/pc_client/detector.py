"""
Optimized particle detection engine using OpenCV
Enhanced for microplastic detection with improved accuracy
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
import time

class ParticleDetector:
    def __init__(self, config: dict):
        self.config = config
        self.scale = config.get('scale_mm_per_pixel', 0.01)
        self.min_area = config.get('min_particle_area', 50)
        self.max_area = config.get('max_particle_area', 5000)
        self.threshold_value = config.get('threshold_value', 60)
        self.blur_kernel = config.get('gaussian_blur', 5)
        self.blur_sigma = config.get('gaussian_sigma', 1)
        
        # Background subtraction for improved detection
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=False, varThreshold=16
        )
        
        # Morphological operations kernels
        
        
        self.closing_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.opening_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        
        # Performance tracking
        self.processing_times = []
        
    def detect_particles(self, frame: np.ndarray) -> Tuple[np.ndarray, List[float]]:
        """
        Detect particles in frame and return annotated frame with particle sizes
        
        Args:
            frame: Input BGR frame from camera
            
        Returns:
            Tuple of (annotated_frame, list_of_particle_sizes_in_mm)
        """
        start_time = time.time()
        
        # Create working copy
        result_frame = frame.copy()
        particles = []
        
        try:
            # Preprocessing
            processed_frame = self._preprocess_frame(frame)
            
            # Find contours
            contours = self._find_contours(processed_frame)
            
            # Analyze each contour
            for contour in contours:
                particle_info = self._analyze_contour(contour)
                if particle_info:
                    particles.append(particle_info['size_mm'])
                    self._draw_particle(result_frame, particle_info)
            
            # Add information overlay
            self._draw_info_overlay(result_frame, len(particles))
            
        except Exception as e:
            print(f"Detection error: {e}")
            # Return original frame on error
            result_frame = frame.copy()
            particles = []
        
        # Track performance
        processing_time = time.time() - start_time
        self.processing_times.append(processing_time)
        if len(self.processing_times) > 100:  # Keep last 100 measurements
            self.processing_times.pop(0)
        
        return result_frame, particles
    
    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for particle detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), self.blur_sigma)
        
        # Apply threshold
        _, binary = cv2.threshold(blurred, self.threshold_value, 255, cv2.THRESH_BINARY)
        
        # Morphological operations to clean up
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, self.closing_kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self.opening_kernel)
        
        return binary
    
    def _find_contours(self, binary_frame: np.ndarray) -> List[np.ndarray]:
        """Find contours in binary frame"""
        contours, _ = cv2.findContours(
            binary_frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        return contours
    
    def _analyze_contour(self, contour: np.ndarray) -> Optional[dict]:
        """Analyze a single contour to determine if it's a valid particle"""
        area = cv2.contourArea(contour)
        
        # Filter by area
        if area < self.min_area or area > self.max_area:
            return None
        
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        
        # Calculate center
        center_x = x + w // 2
        center_y = y + h // 2
        
        # Calculate equivalent diameter in mm
        # Assuming circular particles: diameter = 2 * sqrt(area / π)
        diameter_pixels = 2 * np.sqrt(area / np.pi)
        diameter_mm = diameter_pixels * self.scale
        
        # Calculate aspect ratio for shape analysis
        aspect_ratio = w / h if h > 0 else 0
        
        # Calculate solidity (area / convex hull area)
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0
        
        # Filter based on shape characteristics
        if aspect_ratio > 3.0 or aspect_ratio < 0.33:  # Too elongated
            return None
        if solidity < 0.5:  # Too irregular
            return None
        
        return {
            'contour': contour,
            'center': (center_x, center_y),
            'bounding_rect': (x, y, w, h),
            'area_pixels': area,
            'size_mm': diameter_mm,
            'aspect_ratio': aspect_ratio,
            'solidity': solidity
        }
    
    def _draw_particle(self, frame: np.ndarray, particle_info: dict):
        """Draw particle annotation on frame"""
        center = particle_info['center']
        size_mm = particle_info['size_mm']
        x, y, w, h = particle_info['bounding_rect']
        
        # Draw circle around particle
        radius = max(w, h) // 2
        cv2.circle(frame, center, radius, (0, 255, 0), 2)
        
        # Draw size label
        label = f"{size_mm:.2f}mm"
        label_pos = (center[0] - 30, center[1] - radius - 10)
        
        # Background for text
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(frame, 
                     (label_pos[0] - 2, label_pos[1] - label_h - 2),
                     (label_pos[0] + label_w + 2, label_pos[1] + 2),
                     (0, 0, 0), -1)
        
        # Text
        cv2.putText(frame, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw center point
        cv2.circle(frame, center, 2, (0, 0, 255), -1)
    
    def _draw_info_overlay(self, frame: np.ndarray, particle_count: int):
        """Draw information overlay on frame"""
        h, w = frame.shape[:2]
        
        # Background for info panel
        info_height = 80
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, info_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Particle count
        count_text = f"Particles: {particle_count}"
        cv2.putText(frame, count_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Processing time info
        if self.processing_times:
            avg_time = sum(self.processing_times) / len(self.processing_times)
            fps_estimate = 1.0 / avg_time if avg_time > 0 else 0
            time_text = f"FPS: {fps_estimate:.1f}"
            cv2.putText(frame, time_text, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Scale info
        scale_text = f"Scale: {self.scale:.4f} mm/px"
        cv2.putText(frame, scale_text, (w - 200, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    def update_config(self, new_config: dict):
        """Update detection parameters"""
        self.config.update(new_config)
        self.scale = self.config.get('scale_mm_per_pixel', self.scale)
        self.min_area = self.config.get('min_particle_area', self.min_area)
        self.max_area = self.config.get('max_particle_area', self.max_area)
        self.threshold_value = self.config.get('threshold_value', self.threshold_value)
        self.blur_kernel = self.config.get('gaussian_blur', self.blur_kernel)
        self.blur_sigma = self.config.get('gaussian_sigma', self.blur_sigma)
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        if not self.processing_times:
            return {}
        
        times = np.array(self.processing_times)
        return {
            'avg_processing_time': float(np.mean(times)),
            'min_processing_time': float(np.min(times)),
            'max_processing_time': float(np.max(times)),
            'estimated_fps': float(1.0 / np.mean(times)) if np.mean(times) > 0 else 0
        }
    
    def calibrate_threshold(self, frame: np.ndarray) -> int:
        """Auto-calibrate threshold based on frame content"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Use Otsu's method for automatic thresholding
        threshold_value, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return int(threshold_value)
    
    def reset_background(self):
        """Reset background subtractor"""
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=False, varThreshold=16
        )