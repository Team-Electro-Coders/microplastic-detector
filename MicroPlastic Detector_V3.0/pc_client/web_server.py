"""
Flask Web Server for ESP32 Microplastic Detector
Provides REST API and web dashboard
RECTIFIED VERSION - All bugs fixed
"""

import os
import io
import cv2
import json
import threading
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, Response, send_file
from flask_cors import CORS
from typing import Dict, Any, Optional
import time

class WebServer:
    def __init__(self, config: Dict[str, Any], app_instance):
        self.config = config
        self.app_instance = app_instance  # Reference to main app
        self.host = config.get('host', '0.0.0.0')
        self.port = config.get('port', 5000)
        self.debug = config.get('debug', False)
        
        # Initialize Flask app
        self.app = Flask(__name__, 
                        template_folder='templates',
                        static_folder='static')
        
        # Enable CORS for API access
        CORS(self.app)
        
        # Configure Flask
        self.app.config['SECRET_KEY'] = 'microplastic_detector_2025'
        self.app.config['JSON_SORT_KEYS'] = False
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
        
        # Setup routes
        self.setup_routes()
        
        # Server thread
        self.server_thread = None
        self.running = False
        
        print(f"Web server initialized on {self.host}:{self.port}")
    
    def setup_routes(self):
        """Setup all Flask routes"""
        
        # Dashboard routes
        @self.app.route('/')
        def dashboard():
            """Main dashboard page - FIX: Pass ESP32 IP to template"""
            esp32_ip = self.app_instance.config.get('esp32', {}).get('ip', '192.168.4.1')
            return render_template('dashboard.html', esp32_ip=esp32_ip)
        
        @self.app.route('/settings')
        def settings():
            """Settings page"""
            return render_template('settings.html')
        
        @self.app.route('/debug')
        def debug_page():
            """Debug interface (only if debug enabled)"""
            if not self.debug:
                return jsonify({'error': 'Debug mode disabled'}), 403
            return render_template('debug.html')
        
        # API routes
        @self.app.route('/api/stats')
        def get_stats():
            """Get current detection statistics"""
            try:
                stats = self.app_instance.get_current_stats()
                response = jsonify(stats)
                # Disable client/proxy caching for real-time updates
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/frame')
        def get_frame():
            """Get current processed frame as MJPEG stream"""
            def generate_frames():
                while True:
                    try:
                        frame = self.app_instance.get_current_frame()
                        if frame is not None:
                            # Encode frame as JPEG
                            _, buffer = cv2.imencode('.jpg', frame, 
                                                   [cv2.IMWRITE_JPEG_QUALITY, 85])
                            frame_bytes = buffer.tobytes()
                            
                            yield (b'--frame\r\n'
                                  b'Content-Type: image/jpeg\r\n\r\n' + 
                                  frame_bytes + b'\r\n')
                        else:
                            # Send placeholder frame if no video
                            placeholder = self._create_placeholder_frame()
                            _, buffer = cv2.imencode('.jpg', placeholder)
                            frame_bytes = buffer.tobytes()
                            
                            yield (b'--frame\r\n'
                                  b'Content-Type: image/jpeg\r\n\r\n' + 
                                  frame_bytes + b'\r\n')
                        
                        time.sleep(0.033)  # ~30 FPS
                        
                    except GeneratorExit:
                        break
                    except Exception as e:
                        print(f"Error generating frame: {e}")
                        time.sleep(1)
            
            return Response(generate_frames(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/api/frame/single')
        def get_single_frame():
            """Get single current frame as JPEG"""
            try:
                frame = self.app_instance.get_current_frame()
                if frame is not None:
                    _, buffer = cv2.imencode('.jpg', frame)
                    return Response(buffer.tobytes(), mimetype='image/jpeg')
                else:
                    placeholder = self._create_placeholder_frame()
                    _, buffer = cv2.imencode('.jpg', placeholder)
                    return Response(buffer.tobytes(), mimetype='image/jpeg')
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/history')
        def get_history():
            """Get historical detection data"""
            try:
                minutes = request.args.get('minutes', 60, type=int)
                data = self.app_instance.logger.get_recent_data(minutes)
                return jsonify(data)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/calibrate', methods=['POST'])
        def calibrate_scale():
            """Update scale calibration"""
            try:
                data = request.get_json()
                scale = data.get('scale_mm_per_pixel')
                
                if scale and scale > 0:
                    # Update detector configuration
                    self.app_instance.detector.update_config({
                        'scale_mm_per_pixel': scale
                    })
                    
                    # Save to main config
                    self.app_instance.config['detection']['scale_mm_per_pixel'] = scale
                    self.app_instance.save_config(self.app_instance.config, 'config.json')
                    
                    return jsonify({
                        'success': True,
                        'message': f'Scale updated to {scale:.6f} mm/pixel'
                    })
                else:
                    return jsonify({'error': 'Invalid scale value'}), 400
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/settings/<tab>')
        def get_settings(tab):
            """Get settings for specific tab"""
            try:
                if tab == 'detection':
                    settings = self.app_instance.config.get('detection', {})
                elif tab == 'camera':
                    settings = self.app_instance.config.get('camera', {})
                elif tab == 'system':
                    settings = {
                        'esp32_ip': self.app_instance.config.get('esp32', {}).get('ip'),
                        'sample_volume_ml': self.app_instance.config.get('volume', {}).get('sample_volume_ml'),
                        'auto_log_interval': self.app_instance.config.get('logging', {}).get('auto_log_interval'),
                        'debug': self.app_instance.config.get('web', {}).get('debug')
                    }
                else:
                    return jsonify({'error': 'Invalid settings tab'}), 400
                
                return jsonify(settings)
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/settings', methods=['POST'])
        def update_settings():
            """Update system settings"""
            try:
                settings = request.get_json()
                
                # Update configuration
                if 'scale' in settings:
                    self.app_instance.config['detection']['scale_mm_per_pixel'] = settings['scale']
                if 'threshold' in settings:
                    self.app_instance.config['detection']['threshold_value'] = settings['threshold']
                if 'min_area' in settings:
                    self.app_instance.config['detection']['min_particle_area'] = settings['min_area']
                if 'max_area' in settings:
                    self.app_instance.config['detection']['max_particle_area'] = settings['max_area']
                # Allow updating ESP32 IP/port at runtime
                if 'esp32_ip' in settings or 'esp32_port' in settings:
                    new_ip = settings.get('esp32_ip', self.app_instance.config['esp32'].get('ip'))
                    new_port = settings.get('esp32_port', self.app_instance.config['esp32'].get('port'))
                    self.app_instance.esp32.set_address(new_ip, new_port)
                    self.app_instance.config['esp32']['ip'] = new_ip
                    self.app_instance.config['esp32']['port'] = new_port
                
                # Update detector
                self.app_instance.detector.update_config(self.app_instance.config['detection'])
                
                # Save configuration
                self.app_instance.save_config(self.app_instance.config, 'config.json')
                
                return jsonify({'success': True, 'message': 'Settings updated'})
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/mode/<mode>', methods=['POST'])
        def set_mode(mode):
            """Set detection mode"""
            try:
                if self.app_instance.esp32.set_mode(mode):
                    return jsonify({'success': True, 'mode': mode})
                else:
                    return jsonify({'error': 'Failed to set mode'}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/parameter', methods=['POST'])
        def update_parameter():
            """Update single detection parameter"""
            try:
                data = request.get_json()
                
                # Update detector configuration
                self.app_instance.detector.update_config(data)
                
                return jsonify({'success': True})
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reset-parameters', methods=['POST'])
        def reset_parameters():
            """Reset detection parameters to defaults"""
            try:
                default_params = {
                    'threshold_value': 60,
                    'min_particle_area': 50,
                    'max_particle_area': 5000,
                    'gaussian_blur': 5,
                    'gaussian_sigma': 1
                }
                
                self.app_instance.detector.update_config(default_params)
                self.app_instance.config['detection'].update(default_params)
                
                return jsonify({'success': True})
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/save-parameters', methods=['POST'])
        def save_parameters():
            """Save current parameters to config file"""
            try:
                params = request.get_json()
                
                # Update config
                if 'threshold' in params:
                    self.app_instance.config['detection']['threshold_value'] = int(params['threshold'])
                if 'min_area' in params:
                    self.app_instance.config['detection']['min_particle_area'] = int(params['min_area'])
                if 'max_area' in params:
                    self.app_instance.config['detection']['max_particle_area'] = int(params['max_area'])
                
                # Save to file
                self.app_instance.save_config(self.app_instance.config, 'config.json')
                
                return jsonify({'success': True})
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/snapshot', methods=['POST'])
        def take_snapshot():
            """Save current frame as snapshot"""
            try:
                frame = self.app_instance.get_current_frame()
                if frame is not None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"snapshot_{timestamp}.jpg"
                    filepath = os.path.join('data/exports', filename)
                    
                    os.makedirs('data/exports', exist_ok=True)
                    cv2.imwrite(filepath, frame)
                    
                    return jsonify({'success': True, 'filename': filename})
                else:
                    return jsonify({'error': 'No frame available'}), 400
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/export/current')
        def export_current():
            """Export current session data"""
            try:
                filepath = self.app_instance.logger.export_data(format_type='csv')
                return send_file(filepath, as_attachment=True)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/export/range')
        def export_range():
            """Export data within date range"""
            try:
                start_date = request.args.get('start')
                end_date = request.args.get('end')
                format_type = request.args.get('format', 'csv')
                
                if start_date:
                    start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                if end_date:
                    end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                filepath = self.app_instance.logger.export_data(
                    start_date=start_date,
                    end_date=end_date,
                    format_type=format_type
                )
                
                return send_file(filepath, as_attachment=True)
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/report/generate', methods=['POST'])
        def generate_report():
            """Generate summary report"""
            try:
                # Get date range from request
                data = request.get_json() or {}
                start_date = data.get('start_date')
                end_date = data.get('end_date')
                
                if start_date:
                    start_date = datetime.fromisoformat(start_date)
                if end_date:
                    end_date = datetime.fromisoformat(end_date)
                
                # Generate report
                report = self.app_instance.logger.generate_summary_report(start_date, end_date)
                
                # Save report as JSON
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_filename = f"report_{timestamp}.json"
                report_path = os.path.join('data/exports', report_filename)
                
                os.makedirs('data/exports', exist_ok=True)
                with open(report_path, 'w') as f:
                    json.dump(report, f, indent=2)
                
                return jsonify({
                    'success': True,
                    'report': report,
                    'report_url': f'/api/report/download/{report_filename}'
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/report/download/<filename>')
        def download_report(filename):
            """Download generated report"""
            try:
                filepath = os.path.join('data/exports', filename)
                return send_file(filepath, as_attachment=True)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/system/status')
        def system_status():
            """Get complete system status"""
            try:
                status = {
                    'timestamp': datetime.now().isoformat(),
                    'camera': {
                        'connected': self.app_instance.cap is not None and self.app_instance.cap.isOpened(),
                        'fps': self.app_instance.get_current_stats().get('fps', 0)
                    },
                    'esp32': {
                        'connected': self.app_instance.esp32.is_connected(),
                        'last_status': self.app_instance.esp32.get_last_status()
                    },
                    'detection': {
                        'active': self.app_instance.running,
                        'current_stats': self.app_instance.get_current_stats()
                    },
                    'data_logger': self.app_instance.logger.get_data_stats()
                }
                return jsonify(status)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/health')
        def health_check():
            """Simple health check endpoint"""
            # FIX: Use start_time which is now properly initialized in main.py
            uptime = time.time() - self.app_instance.start_time
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'uptime_seconds': uptime
            })
        
        # Error handlers
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'Endpoint not found'}), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({'error': 'Internal server error'}), 500
    
    def _create_placeholder_frame(self, width=640, height=480):
        """Create placeholder frame when no video available"""
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = (30, 30, 30)  # Dark gray background
        
        text = "No Video Feed"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 1, 2)[0]
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2
        
        cv2.putText(frame, text, (text_x, text_y), font, 1, (100, 100, 100), 2)
        
        return frame
    
    def start(self):
        """Start the web server in a separate thread"""
        if self.running:
            return
        
        self.running = True
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self.server_thread.start()
        print(f"Web server started on http://{self.host}:{self.port}")
    
    def _run_server(self):
        """Run Flask server (called in separate thread)"""
        try:
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,  # Never use debug in threaded mode
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            print(f"Web server error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the web server"""
        self.running = False
        print("Web server stopped")
    
    def is_running(self):
        """Check if server is running"""
        return self.running