"""
Fall detection module using QYF0900 accelerometer with ADS1115 ADC
Based on step tracking reference code but adapted for fall detection
"""
import threading
import time
import math
import numpy as np
from collections import deque
from typing import Callable, Optional

try:
    import Adafruit_ADS1x15
    ADS_AVAILABLE = True
except ImportError:
    print("WARNING: Adafruit_ADS1x15 library not installed")
    print("Install with: sudo pip3 install Adafruit-ADS1x15")
    Adafruit_ADS1x15 = None
    ADS_AVAILABLE = False

from config import Config

class FallDetector:
    """
    Fall detection using QYF0900 accelerometer with ADS1115 ADC
    Based on step tracking reference but optimized for fall detection
    """
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        
        self.is_monitoring = False
        self.monitor_thread = None
        self.callback = None
        
        # ADS1115 ADC for QYF0900
        self.adc = None
        self.adc_address = 0x48
        self.adc_gain = 1
        self.VALMAX = 32767
        
        # Calibration values
        self.baseline_offset = {'x': 0, 'y': 0, 'z': 0}
        self.is_calibrated = False
        
        # Sensitivity parameters (from step tracking reference)
        self.sensitivity = self.VALMAX / 4.096  # ADC units per volt
        self.g_per_volt = 2.0  # 0.5V per g means 2g per volt
        
        # Fall detection parameters
        self.fall_threshold_high = 3.0  # High impact threshold (g)
        self.fall_threshold_low = 0.4   # Free fall threshold (g)
        self.impact_duration = 0.5      # Time window for impact detection (s)
        
        # Data buffers for improved detection
        self.sample_rate = 25  # Hz
        self.buffer_size = int(self.sample_rate * 2)  # 2 second buffer
        self.accel_buffer = deque(maxlen=self.buffer_size)
        
        # Fall detection state
        self.last_fall_time = 0
        self.fall_cooldown = 10  # seconds between fall detections
        
        # Activity monitoring (to reduce false positives)
        self.activity_buffer = deque(maxlen=int(self.sample_rate * 5))  # 5 second activity buffer
        
        self._initialize_sensor()
    
    def _initialize_sensor(self):
        """Initialize QYF0900 sensor with ADS1115 ADC"""
        if not ADS_AVAILABLE:
            self.logger.error("Adafruit_ADS1x15 library not available")
            self.logger.error("Install with: sudo pip3 install Adafruit-ADS1x15")
            return
        
        try:
            self.adc = Adafruit_ADS1x15.ADS1115(address=self.adc_address)
            
            # Test ADC connection by reading a channel
            test_reading = self.adc.read_adc(0, gain=self.adc_gain)
            
            self.logger.info("QYF0900 sensor with ADS1115 initialized successfully")
            self.logger.info(f"ADC address: 0x{self.adc_address:02x}, Test reading: {test_reading}")
            
            # Calibrate sensor
            self._calibrate_sensor()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize QYF0900/ADS1115: {e}")
            self.logger.error("Check I2C wiring and run: i2cdetect -y 1")
            self.adc = None
    
    def _calibrate_sensor(self, samples: int = 200):
        """
        Calibrate QYF0900 sensor by taking baseline readings
        Based on step tracking calibration method
        
        Args:
            samples: Number of samples for calibration
        """
        if not self.adc:
            return
        
        self.logger.info("Calibrating QYF0900 fall detector... Keep device still for 5 seconds")
        
        x_readings, y_readings, z_readings = [], [], []
        
        for i in range(samples):
            try:
                x_raw = self.adc.read_adc(0, gain=self.adc_gain)
                y_raw = self.adc.read_adc(1, gain=self.adc_gain)
                z_raw = self.adc.read_adc(2, gain=self.adc_gain)
                
                x_readings.append(x_raw)
                y_readings.append(y_raw)
                z_readings.append(z_raw)
                
                if i % 40 == 0:  # Progress indicator
                    self.logger.info(f"Calibration progress: {i/samples*100:.0f}%")
                
                time.sleep(0.02)  # 50Hz sampling during calibration
            except Exception as e:
                self.logger.error(f"Calibration reading error: {e}")
        
        if len(x_readings) < samples * 0.8:  # Need at least 80% good readings
            self.logger.error("Calibration failed - too many bad readings")
            return
        
        # Calculate offsets using numpy for better accuracy
        try:
            self.baseline_offset['x'] = np.mean(x_readings)
            self.baseline_offset['y'] = np.mean(y_readings)
            self.baseline_offset['z'] = np.mean(z_readings)
            
            self.is_calibrated = True
            
            self.logger.info("QYF0900 fall detector calibration complete")
            self.logger.info(f"Offsets: X={self.baseline_offset['x']:.0f}, "
                           f"Y={self.baseline_offset['y']:.0f}, Z={self.baseline_offset['z']:.0f}")
            
        except Exception as e:
            self.logger.error(f"Error calculating calibration offsets: {e}")
    
    def _read_sensor_data(self) -> Optional[dict]:
        """
        Read QYF0900 accelerometer data via ADS1115
        Based on step tracking sensor reading method
        
        Returns:
            Accelerometer data in g-forces or None if error
        """
        if not self.adc or not self.is_calibrated:
            return None
        
        try:
            x_raw = self.adc.read_adc(0, gain=self.adc_gain)
            y_raw = self.adc.read_adc(1, gain=self.adc_gain)
            z_raw = self.adc.read_adc(2, gain=self.adc_gain)
            
            # Convert to g-forces (from step tracking reference)
            g_x = ((x_raw - self.baseline_offset['x']) / self.sensitivity) * self.g_per_volt
            g_y = ((y_raw - self.baseline_offset['y']) / self.sensitivity) * self.g_per_volt
            g_z = ((z_raw - self.baseline_offset['z']) / self.sensitivity) * self.g_per_volt + 1.0
            
            return {'x': g_x, 'y': g_y, 'z': g_z}
            
        except Exception as e:
            self.logger.error(f"Error reading QYF0900 sensor: {e}")
            return None
    
    def start_monitoring(self, fall_callback: Callable[[str], None]):
        """
        Start fall detection monitoring
        
        Args:
            fall_callback: Function to call when fall is detected
        """
        if not self.adc:
            self.logger.error("Cannot start fall detection - QYF0900 sensor not initialized")
            return
        
        if not self.is_calibrated:
            self.logger.error("Cannot start fall detection - sensor not calibrated")
            return
        
        if self.is_monitoring:
            self.logger.warning("Fall detection already active")
            return
        
        self.callback = fall_callback
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("QYF0900 fall detection monitoring started")
    
    def stop_monitoring(self):
        """Stop fall detection monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=3)
        
        self.logger.info("QYF0900 fall detection monitoring stopped")
    
    def _monitoring_loop(self):
        """Fall detection monitoring loop for QYF0900"""
        sample_interval = 1.0 / self.sample_rate
        
        while self.is_monitoring:
            loop_start = time.time()
            
            try:
                accel = self._read_sensor_data()
                
                if accel:
                    # Add to buffers
                    self.accel_buffer.append(accel)
                    
                    # Calculate activity level for context
                    accel_magnitude = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
                    self.activity_buffer.append(accel_magnitude)
                    
                    # Check for fall (only if we have enough data)
                    if len(self.accel_buffer) >= 10:  # Need at least 10 samples
                        if self._detect_fall(accel):
                            current_time = time.time()
                            
                            # Prevent duplicate fall alerts
                            if current_time - self.last_fall_time > self.fall_cooldown:
                                self.logger.warning("FALL DETECTED by QYF0900!")
                                if self.callback:
                                    self.callback("fall")
                                self.last_fall_time = current_time
                
                # Maintain sample rate
                elapsed = time.time() - loop_start
                if elapsed < sample_interval:
                    time.sleep(sample_interval - elapsed)
                
            except Exception as e:
                self.logger.error(f"Error in QYF0900 fall detection loop: {e}")
                time.sleep(1)
    
    def _detect_fall(self, accel: dict) -> bool:
        """
        Detect fall based on QYF0900 accelerometer data
        
        Args:
            accel: Accelerometer data in g-forces
            
        Returns:
            True if fall detected
        """
        # Calculate acceleration magnitude
        accel_magnitude = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        
        # Get recent activity context
        if len(self.activity_buffer) >= 5:
            recent_activity = list(self.activity_buffer)[-5:]
            activity_variance = np.var(recent_activity)
            activity_mean = np.mean(recent_activity)
        else:
            activity_variance = 0
            activity_mean = 1.0
        
        # Fall detection criteria for QYF0900
        criteria = {
            'high_impact': accel_magnitude > self.fall_threshold_high,
            'free_fall': accel_magnitude < self.fall_threshold_low,
            'sudden_change': activity_variance > 0.5,  # Sudden activity change
            'not_walking': activity_mean < 2.0  # Not during normal walking
        }
        
        # Log detailed sensor readings for debugging
        self.logger.debug(f"QYF0900 - Accel: {accel_magnitude:.2f}g, "
                         f"Activity: mean={activity_mean:.2f}, var={activity_variance:.2f}")
        
        # Fall detection logic
        fall_detected = False
        
        # High impact fall (sudden impact)
        if criteria['high_impact'] and criteria['not_walking']:
            self.logger.info(f"High impact detected: {accel_magnitude:.2f}g")
            fall_detected = True
        
        # Free fall detection (falling through air)
        elif criteria['free_fall'] and criteria['sudden_change']:
            self.logger.info(f"Free fall detected: {accel_magnitude:.2f}g, activity change: {activity_variance:.2f}")
            fall_detected = True
        
        return fall_detected
    
    def get_sensor_status(self) -> dict:
        """Get current QYF0900 sensor status and readings"""
        if not self.adc or not self.is_calibrated:
            return {'status': 'not_ready', 'message': 'QYF0900 sensor not initialized or calibrated'}
        
        try:
            accel = self._read_sensor_data()
            if accel:
                accel_magnitude = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
                
                return {
                    'status': 'ready',
                    'sensor': 'QYF0900 with ADS1115',
                    'accel_magnitude': round(accel_magnitude, 2),
                    'accel': {k: round(v, 3) for k, v in accel.items()},
                    'is_monitoring': self.is_monitoring
                }
            else:
                return {'status': 'error', 'message': 'Cannot read QYF0900 sensor data'}
                
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def simulate_fall(self):
        """Simulate a fall for testing purposes"""
        self.logger.info("Simulating fall detection...")
        if self.callback:
            self.callback("fall_simulation")
    
    def cleanup(self):
        """Clean up fall detector resources"""
        self.stop_monitoring()
        self.logger.info("QYF0900 fall detector cleaned up")