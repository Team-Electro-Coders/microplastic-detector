"""
Data Logger for ESP32 Microplastic Detector
Handles CSV logging, data export, and report generation
"""

import csv
import json
import os
import gzip
import shutil
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import time

class DataLogger:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.log_file = config.get('log_file', 'data/logs/detections.csv')
        self.auto_log_interval = config.get('auto_log_interval', 30)  # seconds
        self.max_log_size_mb = config.get('max_log_size_mb', 100)
        self.backup_count = config.get('backup_count', 5)
        
        # Create directories
        self.log_dir = Path(self.log_file).parent
        self.export_dir = Path('data/exports')
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        # Threading
        self.lock = threading.Lock()
        self.auto_log_thread = None
        self.running = False
        
        # Data buffers
        self.current_session_data = []
        self.last_logged_data = {}
        
        # Initialize CSV file
        self.initialize_csv()
        
        # Start auto-logging if enabled
        if self.auto_log_interval > 0:
            self.start_auto_logging()
    
    def initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not Path(self.log_file).exists():
            headers = [
                'timestamp',
                'particle_count',
                'mean_size_mm',
                'std_size_mm',
                'min_size_mm',
                'max_size_mm',
                'concentration_per_ml',
                'sample_volume_ml',
                'detection_fps',
                'system_mode',
                'threshold_value',
                'min_particle_area',
                'max_particle_area',
                'session_id'
            ]
            
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            
            print(f"Initialized CSV log file: {self.log_file}")
    
    def log_detection(self, stats: Dict[str, Any], force_log: bool = False):
        """Log detection statistics to CSV"""
        try:
            with self.lock:
                # Prepare log entry
                timestamp = datetime.now()
                
                # Calculate additional statistics
                particles = stats.get('particles_sizes', [])
                particle_count = len(particles)
                
                if particles:
                    mean_size = np.mean(particles)
                    std_size = np.std(particles)
                    min_size = np.min(particles)
                    max_size = np.max(particles)
                else:
                    mean_size = std_size = min_size = max_size = 0.0
                
                log_entry = {
                    'timestamp': timestamp.isoformat(),
                    'particle_count': particle_count,
                    'mean_size_mm': round(mean_size, 4),
                    'std_size_mm': round(std_size, 4),
                    'min_size_mm': round(min_size, 4),
                    'max_size_mm': round(max_size, 4),
                    'concentration_per_ml': round(stats.get('concentration_per_ml', 0), 2),
                    'sample_volume_ml': stats.get('sample_volume_ml', 0.05),
                    'detection_fps': round(stats.get('fps', 0), 2),
                    'system_mode': stats.get('system_mode', 'detect'),
                    'threshold_value': stats.get('threshold_value', 60),
                    'min_particle_area': stats.get('min_particle_area', 50),
                    'max_particle_area': stats.get('max_particle_area', 5000),
                    'session_id': stats.get('session_id', self.get_session_id())
                }
                
                # Add to session data
                self.current_session_data.append(log_entry)
                
                # Write to CSV if forced or significant change detected
                if force_log or self.should_log(log_entry):
                    self.write_to_csv(log_entry)
                    self.last_logged_data = log_entry.copy()
                
                # Rotate log if needed
                self.check_log_rotation()
                
        except Exception as e:
            print(f"Error logging detection data: {e}")
    
    def should_log(self, current_entry: Dict[str, Any]) -> bool:
        """Determine if current entry should be logged based on change threshold"""
        if not self.last_logged_data:
            return True
        
        # Check for significant changes
        last = self.last_logged_data
        current = current_entry
        
        # Log if particle count changed significantly
        count_change = abs(current['particle_count'] - last['particle_count'])
        if count_change >= 5:  # Log if count changed by 5 or more
            return True
        
        # Log if concentration changed significantly
        conc_change = abs(current['concentration_per_ml'] - last['concentration_per_ml'])
        if conc_change >= 50:  # Log if concentration changed by 50 or more
            return True
        
        # Log if mean size changed significantly
        size_change = abs(current['mean_size_mm'] - last['mean_size_mm'])
        if size_change >= 0.01:  # Log if mean size changed by 0.01mm or more
            return True
        
        # Log periodically regardless (every 5 minutes)
        last_time = datetime.fromisoformat(last['timestamp'])
        current_time = datetime.fromisoformat(current['timestamp'])
        if (current_time - last_time).total_seconds() >= 300:  # 5 minutes
            return True
        
        return False
    
    def write_to_csv(self, entry: Dict[str, Any]):
        """Write a single entry to CSV file"""
        try:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=entry.keys())
                writer.writerow(entry)
        except Exception as e:
            print(f"Error writing to CSV: {e}")
    
    def check_log_rotation(self):
        """Check if log file needs rotation based on size"""
        try:
            file_size_mb = Path(self.log_file).stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_log_size_mb:
                self.rotate_log()
        except Exception as e:
            print(f"Error checking log rotation: {e}")
    
    def rotate_log(self):
        """Rotate log file when it gets too large"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.log_dir / f"detections_{timestamp}.csv.gz"
            
            # Compress and backup current log
            with open(self.log_file, 'rb') as f_in:
                with gzip.open(backup_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Start new log file
            self.initialize_csv()
            
            # Clean up old backups
            self.cleanup_old_backups()
            
            print(f"Log rotated to: {backup_file}")
            
        except Exception as e:
            print(f"Error rotating log: {e}")
    
    def cleanup_old_backups(self):
        """Remove old backup files beyond backup_count"""
        try:
            backup_files = sorted(self.log_dir.glob("detections_*.csv.gz"))
            while len(backup_files) > self.backup_count:
                oldest = backup_files.pop(0)
                oldest.unlink()
                print(f"Removed old backup: {oldest}")
        except Exception as e:
            print(f"Error cleaning up backups: {e}")
    
    def start_auto_logging(self):
        """Start automatic logging thread"""
        if self.running:
            return
        
        self.running = True
        self.auto_log_thread = threading.Thread(target=self._auto_log_worker, daemon=True)
        self.auto_log_thread.start()
        print(f"Started auto-logging every {self.auto_log_interval} seconds")
    
    def _auto_log_worker(self):
        """Worker thread for automatic logging"""
        while self.running:
            try:
                time.sleep(self.auto_log_interval)
                if self.current_session_data:
                    # Log latest entry if available
                    with self.lock:
                        if self.current_session_data:
                            latest_entry = self.current_session_data[-1]
                            self.write_to_csv(latest_entry)
                            self.last_logged_data = latest_entry.copy()
            except Exception as e:
                print(f"Error in auto-logging worker: {e}")
    
    def export_data(self, 
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   format_type: str = 'csv') -> str:
        """Export data within date range to specified format"""
        try:
            # Load data
            df = self.load_data_as_dataframe(start_date, end_date)
            
            if df.empty:
                raise ValueError("No data found in specified date range")
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            start_str = start_date.strftime("%Y%m%d") if start_date else "all"
            end_str = end_date.strftime("%Y%m%d") if end_date else "all"
            
            filename = f"microplastic_export_{start_str}_to_{end_str}_{timestamp}.{format_type}"
            filepath = self.export_dir / filename
            
            # Export based on format
            if format_type.lower() == 'csv':
                df.to_csv(filepath, index=False)
            elif format_type.lower() == 'json':
                df.to_json(filepath, orient='records', date_format='iso')
            elif format_type.lower() in ['xlsx', 'excel']:
                df.to_excel(filepath, index=False, engine='openpyxl')
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
            
            print(f"Data exported to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"Error exporting data: {e}")
            raise
    
    def load_data_as_dataframe(self, 
                              start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Load log data as pandas DataFrame with optional date filtering"""
        try:
            # Read CSV files (current + compressed backups)
            all_files = [self.log_file]
            all_files.extend(self.log_dir.glob("detections_*.csv.gz"))
            
            dataframes = []
            
            for file_path in all_files:
                try:
                    if str(file_path).endswith('.gz'):
                        # Read compressed file
                        df = pd.read_csv(file_path, compression='gzip')
                    else:
                        # Read regular CSV
                        df = pd.read_csv(file_path)
                    
                    if not df.empty:
                        dataframes.append(df)
                except Exception as e:
                    print(f"Warning: Could not read {file_path}: {e}")
                    continue
            
            if not dataframes:
                return pd.DataFrame()
            
            # Combine all dataframes
            combined_df = pd.concat(dataframes, ignore_index=True)
            
            # Convert timestamp column
            combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'])
            
            # Filter by date range if specified
            if start_date:
                combined_df = combined_df[combined_df['timestamp'] >= start_date]
            if end_date:
                combined_df = combined_df[combined_df['timestamp'] <= end_date]
            
            # Sort by timestamp
            combined_df = combined_df.sort_values('timestamp')
            
            return combined_df
            
        except Exception as e:
            print(f"Error loading data as DataFrame: {e}")
            return pd.DataFrame()
    
    def generate_summary_report(self, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate summary statistics report"""
        try:
            df = self.load_data_as_dataframe(start_date, end_date)
            
            if df.empty:
                return {"error": "No data available for specified period"}
            
            # Calculate summary statistics
            report = {
                "period": {
                    "start": df['timestamp'].min().isoformat(),
                    "end": df['timestamp'].max().isoformat(),
                    "duration_hours": (df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 3600,
                    "total_samples": len(df)
                },
                "particle_statistics": {
                    "total_particles_detected": int(df['particle_count'].sum()),
                    "average_particles_per_sample": float(df['particle_count'].mean()),
                    "max_particles_in_sample": int(df['particle_count'].max()),
                    "samples_with_particles": int((df['particle_count'] > 0).sum())
                },
                "size_statistics": {
                    "mean_particle_size_mm": float(df[df['mean_size_mm'] > 0]['mean_size_mm'].mean()),
                    "std_particle_size_mm": float(df[df['std_size_mm'] > 0]['std_size_mm'].mean()),
                    "min_size_observed_mm": float(df[df['min_size_mm'] > 0]['min_size_mm'].min()),
                    "max_size_observed_mm": float(df['max_size_mm'].max())
                },
                "concentration_statistics": {
                    "mean_concentration_per_ml": float(df['concentration_per_ml'].mean()),
                    "max_concentration_per_ml": float(df['concentration_per_ml'].max()),
                    "std_concentration_per_ml": float(df['concentration_per_ml'].std())
                },
                "system_performance": {
                    "average_fps": float(df[df['detection_fps'] > 0]['detection_fps'].mean()),
                    "uptime_percentage": float((df['detection_fps'] > 0).mean() * 100)
                }
            }
            
            # Add size distribution
            size_data = df[df['mean_size_mm'] > 0]['mean_size_mm']
            if not size_data.empty:
                report["size_distribution"] = {
                    "percentiles": {
                        "25th": float(size_data.quantile(0.25)),
                        "50th": float(size_data.quantile(0.5)),
                        "75th": float(size_data.quantile(0.75)),
                        "95th": float(size_data.quantile(0.95))
                    },
                    "histogram": self._create_size_histogram(size_data)
                }
            
            return report
            
        except Exception as e:
            print(f"Error generating summary report: {e}")
            return {"error": str(e)}
    
    def _create_size_histogram(self, size_data: pd.Series, bins: int = 20) -> Dict[str, List]:
        """Create histogram data for size distribution"""
        try:
            counts, bin_edges = np.histogram(size_data, bins=bins)
            
            # Create bin labels
            bin_labels = []
            for i in range(len(bin_edges) - 1):
                bin_labels.append(f"{bin_edges[i]:.2f}-{bin_edges[i+1]:.2f}")
            
            return {
                "bin_labels": bin_labels,
                "counts": counts.tolist(),
                "bin_edges": bin_edges.tolist()
            }
        except Exception as e:
            print(f"Error creating histogram: {e}")
            return {"bin_labels": [], "counts": [], "bin_edges": []}
    
    def save_current_session(self, session_name: str = None) -> str:
        """Save current session data to separate file"""
        try:
            if not self.current_session_data:
                raise ValueError("No session data to save")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = session_name or f"session_{timestamp}.json"
            filepath = self.export_dir / filename
            
            session_summary = {
                "session_info": {
                    "name": session_name or f"Session {timestamp}",
                    "start_time": self.current_session_data[0]['timestamp'],
                    "end_time": self.current_session_data[-1]['timestamp'],
                    "duration_seconds": len(self.current_session_data) * self.auto_log_interval,
                    "sample_count": len(self.current_session_data)
                },
                "data": self.current_session_data,
                "summary": self._calculate_session_summary()
            }
            
            with open(filepath, 'w') as f:
                json.dump(session_summary, f, indent=2)
            
            print(f"Session saved to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"Error saving session: {e}")
            raise
    
    def _calculate_session_summary(self) -> Dict[str, Any]:
        """Calculate summary statistics for current session"""
        if not self.current_session_data:
            return {}
        
        try:
            df = pd.DataFrame(self.current_session_data)
            
            return {
                "total_particles": int(df['particle_count'].sum()),
                "average_particles_per_sample": float(df['particle_count'].mean()),
                "max_particles": int(df['particle_count'].max()),
                "average_size_mm": float(df[df['mean_size_mm'] > 0]['mean_size_mm'].mean()),
                "average_concentration": float(df['concentration_per_ml'].mean()),
                "max_concentration": float(df['concentration_per_ml'].max()),
                "average_fps": float(df[df['detection_fps'] > 0]['detection_fps'].mean())
            }
        except Exception as e:
            print(f"Error calculating session summary: {e}")
            return {}
    
    def get_recent_data(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get recent data from the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self.lock:
            recent_data = [
                entry for entry in self.current_session_data
                if datetime.fromisoformat(entry['timestamp']) >= cutoff_time
            ]
        
        return recent_data
    
    def get_session_id(self) -> str:
        """Generate or get current session ID"""
        if not hasattr(self, '_session_id'):
            self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._session_id
    
    def reset_session(self):
        """Reset current session data"""
        with self.lock:
            self.current_session_data.clear()
            self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print("Session data reset")
    
    def get_data_stats(self) -> Dict[str, Any]:
        """Get current data statistics"""
        try:
            log_file_size = 0
            if Path(self.log_file).exists():
                log_file_size = Path(self.log_file).stat().st_size
            
            backup_files = list(self.log_dir.glob("detections_*.csv.gz"))
            total_backup_size = sum(f.stat().st_size for f in backup_files)
            
            return {
                "current_log_size_mb": log_file_size / (1024 * 1024),
                "backup_count": len(backup_files),
                "total_backup_size_mb": total_backup_size / (1024 * 1024),
                "session_samples": len(self.current_session_data),
                "auto_log_interval": self.auto_log_interval,
                "last_log_time": self.last_logged_data.get('timestamp', 'Never')
            }
        except Exception as e:
            print(f"Error getting data stats: {e}")
            return {}
    
    def close(self):
        """Close logger and stop background threads"""
        self.running = False
        
        if self.auto_log_thread and self.auto_log_thread.is_alive():
            self.auto_log_thread.join(timeout=5)
        
        # Save any remaining session data
        if self.current_session_data:
            try:
                self.save_current_session("final_session")
            except Exception as e:
                print(f"Error saving final session: {e}")
        
        print("Data logger closed")