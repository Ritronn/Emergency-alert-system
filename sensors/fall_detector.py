"""
Fall detection module using MPU6050 accelerometer/gyroscope sensor
Improved with better algorithms and calibration from step tracking reference
"""
import threading
import time
import math
import numpy as np
from collections import deque
from typing import Callable, Optional, Tuple

try:
    import smbus
    SMBUS_AVAILABLE = True
except ImportError:
    print("WARNING: smbus library not installed (needed for I2C)")
    print("Install with: sudo apt install python3-smbus")
    smbus = None
    SMBUS_AVAILABLE = False

from config import Config

class FallDetector:
    """
    Advanced fall detection using MPU6050 accelerometer/gyroscope sensor
    Uses improved algorithms for better accuracy and fewer false positives
    """
    
    # MPU6050 I2C address and registers
    MPU6050_ADDR = 0x68
    PWR_MGMT_1 = 0x6B
    ACCEL_XOUT_H = 0x3B
    ACCEL_YOUT_H = 0x3D
    ACCEL_ZOUT_H = 0x3F
    GYRO_XOUT_H = 0x43
    GYRO_YOUT_H = 0x45
    GYRO_ZOUT_H = 0x47
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        
        self.is_monitoring = False
        self.monitor_thread = None
        self.callback = None
        
        # I2C bus
        self.bus = None
        
        # Calibration values (improved calibration)
        self.accel_offset = {'x': 0, 'y': 0, 'z': 0}
        self.gyro_offset = {'x': 0, 'y': 0, 'z': 0}
        self.is_calibrated = False
        
        # Fall detection parameters (improved thresholds)
        self.fall_threshold_high = 3.0  # High impact threshold (g)
        self.fall_threshold_low = 0.4   # Free fall threshold (g)
        self.gyro_threshold = 250       # High rotation threshold (deg/s)
        self.impact_duration = 0.5      # Time window for impact detection (s)
        
        # Data buffers for improved detection
        self.sample_rate = 25  # Hz (matching step tracker)
        self.buffer_size = int(self.sample_rate * 2)  # 2 second buffer
        self.accel_buffer = deque(maxlen=self.buffer_size)
        self.gyro_buffer = deque(maxlen=self.buffer_size)
        
        # Fall detection state
        self.last_fall_time = 0
        self.fall_cooldown = 10  # seconds between fall detections
        
        # Activity monitoring (to reduce false positives)
        self.activity_buffer = deque(maxlen=int(self.sample_rate * 5))  # 5 second activity buffer
        
        self._initialize_sensor()
    
    def _initialize_sensor(self):
        """Initialize MPU6050 sensor with improved error handling"""
        if not SMBUS_AVAILABLE:
            self.logger.error("smbus library not available for I2C communication")
            self.logger.error("Install with: sudo apt install python3-smbus")
            return
        
        try:
            self.bus = smbus.SMBus(1)  # I2C bus 1
            
            # Test I2C connection
            try:
                self.bus.read_byte_data(self.MPU6050_ADDR, 0x75)  # WHO_AM_I register
            except Exception as e:
                self.logger.error(f"MPU6050 not found at address 0x{self.MPU6050_ADDR:02x}")
                self.logger.error("Check I2C wiring and run: i2cdetect -y 1")
                self.bus = None
                return
            
            # Wake up the MPU6050
            self.bus.write_byte_data(self.MPU6050_ADDR, self.PWR_MGMT_1, 0)
            time.sleep(0.1)
            
            # Configure accelerometer (±2g range)
            self.bus.write_byte_data(self.MPU6050_ADDR, 0x1C, 0x00)
            
            # Configure gyroscope (±250°/s range)
            self.bus.write_byte_data(self.MPU6050_ADDR, 0x1B, 0x00)
            
            self.logger.info("MPU6050 sensor initialized successfully")
            
            # Calibrate sensor
            self._calibrate_sensor()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MPU6050: {e}")
            self.bus = None
    
    def _calibrate_sensor(self, samples: int = 200):
        """
        Improved sensor calibration with more samples and better averaging
        
        Args:
            samples: Number of samples for calibration
        """
        if not self.bus:
            return
        
        self.logger.info("Calibrating fall detector... Keep device still for 5 seconds")
        
        accel_readings = {'x': [], 'y': [], 'z': []}
        gyro_readings = {'x': [], 'y': [], 'z': []}
        
        for i in range(samples):
            try:
                accel, gyro = self._read_sensor_data()
                if accel and gyro:
                    accel_readings['x'].append(accel['x'])
                    accel_readings['y'].append(accel['y'])
                    accel_readings['z'].append(accel['z'])
                    gyro_readings['x'].append(gyro['x'])
                    gyro_readings['y'].append(gyro['y'])
                    gyro_readings['z'].append(gyro['z'])
                
                if i % 40 == 0:  # Progress indicator
                    self.logger.info(f"Calibration progress: {i/samples*100:.0f}%")
                
                time.sleep(0.02)  # 50Hz sampling during calibration
            except Exception as e:
                self.logger.error(f"Calibration reading error: {e}")
        
        if len(accel_readings['x']) < samples * 0.8:  # Need at least 80% good readings
            self.logger.error("Calibration failed - too many bad readings")
            return
        
        # Calculate offsets using numpy for better accuracy
        try:
            self.accel_offset['x'] = np.mean(accel_readings['x'])
            self.accel_offset['y'] = np.mean(accel_readings['y'])
            self.accel_offset['z'] = np.mean(accel_readings['z']) - 1.0  # Subtract 1g for gravity
            
            self.gyro_offset['x'] = np.mean(gyro_readings['x'])
            self.gyro_offset['y'] = np.mean(gyro_readings['y'])
            self.gyro_offset['z'] = np.mean(gyro_readings['z'])
            
            self.is_calibrated = True
            
            self.logger.info("Fall detector calibration complete")
            self.logger.info(f"Accel offsets: X={self.accel_offset['x']:.3f}, "
                           f"Y={self.accel_offset['y']:.3f}, Z={self.accel_offset['z']:.3f}")
            self.logger.info(f"Gyro offsets: X={self.gyro_offset['x']:.1f}, "
                           f"Y={self.gyro_offset['y']:.1f}, Z={self.gyro_offset['z']:.1f}")
            
        except Exception as e:
            self.logger.error(f"Error calculating calibration offsets: {e}")
    
    def _read_sensor_data(self) -> Tuple[Optional[dict], Optional[dict]]:
        """
        Read raw sensor data from MPU6050 with improved error handling
        
        Returns:
            Tuple of (accelerometer_data, gyroscope_data) or (None, None) if error
        """
        if not self.bus:
            return None, None
        
        try:
            # Read accelerometer data (±2g range, 16384 LSB/g)
            accel_x = self._read_word_2c(self.ACCEL_XOUT_H) / 16384.0
            accel_y = self._read_word_2c(self.ACCEL_YOUT_H) / 16384.0
            accel_z = self._read_word_2c(self.ACCEL_ZOUT_H) / 16384.0
            
            # Read gyroscope data (±250°/s range, 131 LSB/°/s)
            gyro_x = self._read_word_2c(self.GYRO_XOUT_H) / 131.0
            gyro_y = self._read_word_2c(self.GYRO_YOUT_H) / 131.0
            gyro_z = self._read_word_2c(self.GYRO_ZOUT_H) / 131.0
            
            accel_data = {'x': accel_x, 'y': accel_y, 'z': accel_z}
            gyro_data = {'x': gyro_x, 'y': gyro_y, 'z': gyro_z}
            
            return accel_data, gyro_data
            
        except Exception as e:
            self.logger.error(f"Error reading sensor data: {e}")
            return None, None
    
    def _read_word_2c(self, addr: int) -> int:
        """
        Read 16-bit signed value from I2C register
        
        Args:
            addr: Register address
            
        Returns:
            16-bit signed integer value
        """
        high = self.bus.read_byte_data(self.MPU6050_ADDR, addr)
        low = self.bus.read_byte_data(self.MPU6050_ADDR, addr + 1)
        val = (high << 8) + low
        
        # Convert to signed value
        if val >= 0x8000:
            return -((65535 - val) + 1)
        else:
            return val
    
    def start_monitoring(self, fall_callback: Callable[[str], None]):
        """
        Start fall detection monitoring
        
        Args:
            fall_callback: Function to call when fall is detected
        """
        if not self.bus:
            self.logger.error("Cannot start fall detection - sensor not initialized")
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
        
        self.logger.info("Fall detection monitoring started")
    
    def stop_monitoring(self):
        """Stop fall detection monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=3)
        
        self.logger.info("Fall detection monitoring stopped")
    
    def _monitoring_loop(self):
        """Improved fall detection monitoring loop with better algorithms"""
        sample_interval = 1.0 / self.sample_rate
        
        while self.is_monitoring:
            loop_start = time.time()
            
            try:
                accel, gyro = self._read_sensor_data()
                
                if accel and gyro:
                    # Apply calibration offsets
                    corrected_accel = {
                        'x': accel['x'] - self.accel_offset['x'],
                        'y': accel['y'] - self.accel_offset['y'],
                        'z': accel['z'] - self.accel_offset['z']
                    }
                    
                    corrected_gyro = {
                        'x': gyro['x'] - self.gyro_offset['x'],
                        'y': gyro['y'] - self.gyro_offset['y'],
                        'z': gyro['z'] - self.gyro_offset['z']
                    }
                    
                    # Add to buffers
                    self.accel_buffer.append(corrected_accel)
                    self.gyro_buffer.append(corrected_gyro)
                    
                    # Calculate activity level for context
                    accel_magnitude = math.sqrt(corrected_accel['x']**2 + 
                                              corrected_accel['y']**2 + 
                                              corrected_accel['z']**2)
                    self.activity_buffer.append(accel_magnitude)
                    
                    # Check for fall (only if we have enough data)
                    if len(self.accel_buffer) >= 10:  # Need at least 10 samples
                        if self._detect_fall_improved(corrected_accel, corrected_gyro):
                            current_time = time.time()
                            
                            # Prevent duplicate fall alerts
                            if current_time - self.last_fall_time > self.fall_cooldown:
                                self.logger.warning("FALL DETECTED!")
                                if self.callback:
                                    self.callback("fall")
                                self.last_fall_time = current_time
                
                # Maintain sample rate
                elapsed = time.time() - loop_start
                if elapsed < sample_interval:
                    time.sleep(sample_interval - elapsed)
                
            except Exception as e:
                self.logger.error(f"Error in fall detection loop: {e}")
                time.sleep(1)
    
    def _detect_fall_improved(self, accel: dict, gyro: dict) -> bool:
        """
        Improved fall detection algorithm with multiple criteria and context awareness
        
        Args:
            accel: Accelerometer data (corrected)
            gyro: Gyroscope data (corrected)
            
        Returns:
            True if fall detected
        """
        # Calculate magnitudes
        accel_magnitude = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        gyro_magnitude = math.sqrt(gyro['x']**2 + gyro['y']**2 + gyro['z']**2)
        
        # Get recent activity context
        if len(self.activity_buffer) >= 5:
            recent_activity = list(self.activity_buffer)[-5:]
            activity_variance = np.var(recent_activity)
            activity_mean = np.mean(recent_activity)
        else:
            activity_variance = 0
            activity_mean = 1.0
        
        # Fall detection criteria (improved algorithm)
        criteria = {
            'high_impact': accel_magnitude > self.fall_threshold_high,
            'free_fall': accel_magnitude < self.fall_threshold_low,
            'high_rotation': gyro_magnitude > self.gyro_threshold,
            'sudden_change': activity_variance > 0.5,  # Sudden activity change
            'not_walking': activity_mean < 2.0  # Not during normal walking
        }
        
        # Log detailed sensor readings for debugging
        self.logger.debug(f"Accel: {accel_magnitude:.2f}g, Gyro: {gyro_magnitude:.1f}°/s, "
                         f"Activity: mean={activity_mean:.2f}, var={activity_variance:.2f}")
        
        # Fall detection logic (more sophisticated)
        fall_detected = False
        
        # High impact fall (sudden impact)
        if criteria['high_impact'] and criteria['not_walking']:
            self.logger.info(f"High impact detected: {accel_magnitude:.2f}g")
            fall_detected = True
        
        # Free fall detection (falling through air)
        elif criteria['free_fall'] and criteria['high_rotation']:
            self.logger.info(f"Free fall detected: {accel_magnitude:.2f}g, rotation: {gyro_magnitude:.1f}°/s")
            fall_detected = True
        
        # Sudden movement with high rotation (tumbling)
        elif criteria['sudden_change'] and criteria['high_rotation'] and criteria['not_walking']:
            self.logger.info(f"Tumbling detected: rotation: {gyro_magnitude:.1f}°/s, activity change: {activity_variance:.2f}")
            fall_detected = True
        
        return fall_detected
    
    def get_sensor_status(self) -> dict:
        """Get current sensor status and readings"""
        if not self.bus or not self.is_calibrated:
            return {'status': 'not_ready', 'message': 'Sensor not initialized or calibrated'}
        
        try:
            accel, gyro = self._read_sensor_data()
            if accel and gyro:
                # Apply calibration
                corrected_accel = {
                    'x': accel['x'] - self.accel_offset['x'],
                    'y': accel['y'] - self.accel_offset['y'],
                    'z': accel['z'] - self.accel_offset['z']
                }
                
                accel_magnitude = math.sqrt(corrected_accel['x']**2 + 
                                          corrected_accel['y']**2 + 
                                          corrected_accel['z']**2)
                
                return {
                    'status': 'ready',
                    'accel_magnitude': round(accel_magnitude, 2),
                    'accel': {k: round(v, 3) for k, v in corrected_accel.items()},
                    'gyro': {k: round(v, 1) for k, v in gyro.items()},
                    'is_monitoring': self.is_monitoring
                }
            else:
                return {'status': 'error', 'message': 'Cannot read sensor data'}
                
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
        self.logger.info("Fall detector cleaned up")