"""
ESP32 Client Module for Microplastic Detector
Handles communication with ESP32 device
"""

import requests
import json
import time
import threading
from typing import Dict, Any, Optional, Callable
from urllib.parse import urljoin

class ESP32Client:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ip = config.get('ip', '192.168.4.1')
        self.port = config.get('port', 80)
        self.timeout = config.get('timeout', 5)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 1)
        
        self.base_url = f"http://{self.ip}:{self.port}"
        self.connected = False
        self.last_status = {}
        
        # Threading for status monitoring
        self.status_thread = None
        self.running = False
        self.status_callback = None
        
        # Request session for connection pooling
        self.session = requests.Session()
        self.session.timeout = self.timeout
        
        print(f"ESP32 Client initialized for {self.base_url}")

    def set_address(self, ip: str, port: Optional[int] = None):
        """Update ESP32 address at runtime and reset base URL."""
        if ip:
            self.ip = ip
        if port is not None:
            self.port = port
        self.base_url = f"http://{self.ip}:{self.port}"
        # Also reflect back to stored config for persistence outside
        self.config['ip'] = self.ip
        self.config['port'] = self.port
        print(f"ESP32 address updated to {self.base_url}")
    
    def connect(self) -> bool:
        """Test connection to ESP32 and verify it's responding"""
        try:
            response = self.get_status()
            if response:
                self.connected = True
                print(f"ESP32 connected successfully at {self.base_url}")
                return True
        except Exception as e:
            print(f"ESP32 connection failed: {e}")
        
        self.connected = False
        return False
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     json_data: Optional[Dict] = None) -> Optional[requests.Response]:
        """Make HTTP request with retry logic"""
        url = urljoin(self.base_url, endpoint)
        
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url)
                elif method.upper() == 'POST':
                    if json_data:
                        response = self.session.post(url, json=json_data)
                    else:
                        response = self.session.post(url, data=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                self.connected = True
                return response
                
            except requests.exceptions.RequestException as e:
                self.connected = False
                if attempt < self.retry_attempts - 1:
                    print(f"ESP32 request failed (attempt {attempt + 1}): {e}, retrying...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"ESP32 request failed after {self.retry_attempts} attempts: {e}")
                    return None
            except Exception as e:
                print(f"Unexpected error in ESP32 request: {e}")
                return None
        
        return None
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """Get current ESP32 status"""
        try:
            response = self._make_request('GET', '/status')
            if response and response.text:
                status = response.json()
                self.last_status = status
                return status
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing ESP32 status response: {e}")
        except Exception as e:
            print(f"Error getting ESP32 status: {e}")
        
        return None
    
    def send_stats(self, stats: Dict[str, Any]) -> bool:
        """Send detection statistics to ESP32"""
        try:
            # Format stats for ESP32
            esp32_stats = {
                'count': int(stats.get('count', 0)),
                'mean_size_mm': float(stats.get('mean_size_mm', 0)),
                'concentration_per_ml': float(stats.get('concentration_per_ml', 0))
            }
            
            response = self._make_request('POST', '/stats', json_data=esp32_stats)
            
            if response:
                return True
            
        except Exception as e:
            print(f"Error sending stats to ESP32: {e}")
        
        return False
    
    def set_mode(self, mode: str) -> bool:
        """Set ESP32 operation mode (detect, clean, standby)"""
        valid_modes = ['detect', 'clean', 'standby']
        
        if mode not in valid_modes:
            print(f"Invalid mode: {mode}. Valid modes: {valid_modes}")
            return False
        
        try:
            response = self._make_request('POST', f'/mode/{mode}')
            
            if response:
                print(f"ESP32 mode set to: {mode}")
                return True
            
        except Exception as e:
            print(f"Error setting ESP32 mode: {e}")
        
        return False
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """Get ESP32 configuration"""
        try:
            response = self._make_request('GET', '/config')
            if response:
                return response.json()
        except Exception as e:
            print(f"Error getting ESP32 config: {e}")
        
        return None
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """Update ESP32 configuration"""
        try:
            response = self._make_request('POST', '/config', json_data=config)
            
            if response:
                print("ESP32 configuration updated successfully")
                return True
            
        except Exception as e:
            print(f"Error updating ESP32 config: {e}")
        
        return False
    
    def restart_esp32(self) -> bool:
        """Restart ESP32 device"""
        try:
            response = self._make_request('POST', '/restart')
            
            if response:
                print("ESP32 restart command sent")
                self.connected = False  # Will be disconnected during restart
                return True
            
        except Exception as e:
            print(f"Error restarting ESP32: {e}")
        
        return False
    
    def start_status_monitoring(self, callback: Optional[Callable] = None, interval: float = 10.0):
        """Start background status monitoring thread"""
        if self.running:
            return
        
        self.status_callback = callback
        self.running = True
        self.status_thread = threading.Thread(
            target=self._status_monitor_worker, 
            args=(interval,),
            daemon=True
        )
        self.status_thread.start()
        print(f"Started ESP32 status monitoring (interval: {interval}s)")
    
    def _status_monitor_worker(self, interval: float):
        """Background worker for status monitoring"""
        while self.running:
            try:
                status = self.get_status()
                
                if self.status_callback and status:
                    self.status_callback(status)
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"Error in ESP32 status monitoring: {e}")
                time.sleep(interval)
    
    def stop_status_monitoring(self):
        """Stop background status monitoring"""
        self.running = False
        
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=5)
        
        print("ESP32 status monitoring stopped")
    
    def is_connected(self) -> bool:
        """Check if ESP32 is currently connected"""
        return self.connected
    
    def get_last_status(self) -> Dict[str, Any]:
        """Get last received status"""
        return self.last_status.copy()
    
    def ping(self) -> bool:
        """Simple ping test to ESP32"""
        try:
            response = self._make_request('GET', '/status')
            return response is not None
        except Exception:
            return False
    
    def get_system_info(self) -> Optional[Dict[str, Any]]:
        """Get detailed ESP32 system information"""
        try:
            status = self.get_status()
            if not status:
                return None
            
            # Enhance status with additional info
            system_info = {
                'connection_status': self.connected,
                'base_url': self.base_url,
                'last_response_time': time.time(),
                'esp32_status': status
            }
            
            return system_info
            
        except Exception as e:
            print(f"Error getting ESP32 system info: {e}")
            return None
    
    def send_heartbeat(self) -> bool:
        """Send heartbeat to ESP32 to maintain connection"""
        return self.ping()
    
    def configure_wifi(self, ssid: str, password: str) -> bool:
        """Configure WiFi settings on ESP32"""
        try:
            wifi_config = {
                'wifi_ssid': ssid,
                'wifi_password': password
            }
            
            return self.update_config(wifi_config)
            
        except Exception as e:
            print(f"Error configuring ESP32 WiFi: {e}")
            return False
    
    def set_lcd_update_interval(self, interval_ms: int) -> bool:
        """Set LCD update interval on ESP32"""
        try:
            config = {'lcd_update_interval': interval_ms}
            return self.update_config(config)
        except Exception as e:
            print(f"Error setting LCD update interval: {e}")
            return False
    
    def get_connection_quality(self) -> Dict[str, Any]:
        """Assess connection quality to ESP32"""
        try:
            # Perform multiple ping tests
            ping_times = []
            successful_pings = 0
            total_pings = 5
            
            for _ in range(total_pings):
                start_time = time.time()
                if self.ping():
                    ping_time = (time.time() - start_time) * 1000  # ms
                    ping_times.append(ping_time)
                    successful_pings += 1
                time.sleep(0.5)
            
            if ping_times:
                avg_ping = sum(ping_times) / len(ping_times)
                min_ping = min(ping_times)
                max_ping = max(ping_times)
            else:
                avg_ping = min_ping = max_ping = 0
            
            success_rate = (successful_pings / total_pings) * 100
            
            # Determine quality level
            if success_rate >= 90 and avg_ping < 100:
                quality = 'excellent'
            elif success_rate >= 80 and avg_ping < 200:
                quality = 'good'
            elif success_rate >= 60 and avg_ping < 500:
                quality = 'fair'
            else:
                quality = 'poor'
            
            return {
                'quality': quality,
                'success_rate_percent': success_rate,
                'average_ping_ms': avg_ping,
                'min_ping_ms': min_ping,
                'max_ping_ms': max_ping,
                'total_tests': total_pings,
                'successful_tests': successful_pings
            }
            
        except Exception as e:
            print(f"Error assessing connection quality: {e}")
            return {
                'quality': 'unknown',
                'error': str(e)
            }
    
    def scan_networks(self) -> bool:
        """Trigger WiFi network scan on ESP32 (if supported)"""
        try:
            response = self._make_request('POST', '/scan_wifi')
            return response is not None
        except Exception as e:
            print(f"Error triggering network scan: {e}")
            return False
    
    def factory_reset(self) -> bool:
        """Trigger factory reset on ESP32 (if supported)"""
        try:
            response = self._make_request('POST', '/factory_reset')
            if response:
                self.connected = False  # Device will restart
                return True
        except Exception as e:
            print(f"Error triggering factory reset: {e}")
        
        return False
    
    def close(self):
        """Close ESP32 client and cleanup resources"""
        self.stop_status_monitoring()
        
        if hasattr(self, 'session'):
            self.session.close()
        
        self.connected = False
        print("ESP32 client closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Destructor"""
        try:
            self.close()
        except:
            pass