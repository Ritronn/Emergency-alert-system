"""
Fall detection module using accelerometer/gyroscope sensor
"""
import threading
import time
import math
from typing import Callable, Optional, Tuple

try:
    import smbus
except ImportError:
    print("WARNING: smbus library not installed (needed for I2C)")
    smbus = None

from config import Config

class FallDetector:
    """
    Fall detection using MPU6050 accelerometer/gyroscope sensor
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
        
        # Calibration values
        self.accel_offset = {'x': 0, 'y': 0, 'z': 0}
        self.gyro_offset = {'x': 0, 'y': 0, 'z': 0}
        
        # Fall detection state
        self.baseline_accel = 1.0  # 1g baseline
        self.fall_detected = False
        self.last_fall_time = 0
        
        self._initialize_sensor()
    
    def _initialize_sensor(self):
        """Initialize MPU6050 sensor"""
        if not smbus:
            self.logger.error("smbus library not available for I2C communication")
            return
        
        try:
            self.bus = smbus.SMBus(1)  # I2C bus 1
            
            # Wake up the MPU6050
            self.bus.write_byte_data(self.MPU6050_ADDR, self.PWR_MGMT_1, 0)
            time.sleep(0.1)
            
            self.logger.info("MPU6050 sensor initialized")
            
            # Calibrate sensor
            self._calibrate_sensor()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MPU6050: {e}")
            self.bus = None
    
    def _calibrate_sensor(self, samples: int = 100):
        """
        Calibrate sensor by taking baseline readings
        
        Args:
            samples: Number of samples for calibration
        """
        if not self.bus:
            return
        
        self.logger.info("Calibrating fall detector...")
        
        accel_sum = {'x': 0, 'y': 0, 'z': 0}
        gyro_sum = {'x': 0, 'y': 0, 'z': 0}
        
        for _ in range(samples):
            try:
                accel, gyro = self._read_sensor_data()
                if accel and gyro:
                    accel_sum['x'] += accel['x']
                    accel_sum['y'] += accel['y']
                    accel_sum['z'] += accel['z']
                    gyro_sum['x'] += gyro['x']
                    gyro_sum['y'] += gyro['y']
                    gyro_sum['z'] += gyro['z']
                
                time.sleep(0.01)
            except Exception as e:
                self.logger.error(f"Calibration reading error: {e}")
        
        # Calculate offsets
        self.accel_offset['x'] = accel_sum['x'] / samples
        self.accel_offset['y'] = accel_sum['y'] / samples
        self.accel_offset['z'] = (accel_sum['z'] / samples) - 1.0  # Subtract 1g for gravity
        
        self.gyro_offset['x'] = gyro_sum['x'] / samples
        self.gyro_offset['y'] = gyro_sum['y'] / samples
        self.gyro_offset['z'] = gyro_sum['z'] / samples
        
        self.logger.info("Fall detector calibration complete")
    
    def _read_sensor_data(self) -> Tuple[Optional[dict], Optional[dict]]:
        """
        Read raw sensor data from MPU6050
        
        Returns:
            Tuple of (accelerometer_data, gyroscope_data) or (None, None) if error
        """
        if not self.bus:
            return None, None
        
        try:
            # Read accelerometer data
            accel_x = self._read_word_2c(self.ACCEL_XOUT_H) / 16384.0
            accel_y = self._read_word_2c(self.ACCEL_YOUT_H) / 16384.0
            accel_z = self._read_word_2c(self.ACCEL_ZOUT_H) / 16384.0
            
            # Read gyroscope data
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
            self.monitor_thread.join(timeout=2)
        
        self.logger.info("Fall detection monitoring stopped")
    
    def _monitoring_loop(self):
        """Main fall detection monitoring loop"""
        while self.is_monitoring:
            try:
                accel, gyro = self._read_sensor_data()
                
                if accel and gyro:
                    # Apply calibration offsets
                    corrected_accel = {
                        'x': accel['x'] - self.accel_offset['x'],
                        'y': accel['y'] - self.accel_offset['y'],
                        'z': accel['z'] - self.accel_offset['z']
                    }
                    
                    # Check for fall
                    if self._detect_fall(corrected_accel, gyro):
                        current_time = time.time()
                        
                        # Prevent duplicate fall alerts
                        if current_time - self.last_fall_time > 5:  # 5 second cooldown
                            self.logger.warning("FALL DETECTED!")
                            if self.callback:
                                self.callback("fall")
                            self.last_fall_time = current_time
                
                time.sleep(0.1)  # 10Hz sampling rate
                
            except Exception as e:
                self.logger.error(f"Error in fall detection loop: {e}")
                time.sleep(1)
    
    def _detect_fall(self, accel: dict, gyro: dict) -> bool:
        """
        Detect fall based on accelerometer and gyroscope data
        
        Args:
            accel: Accelerometer data (corrected)
            gyro: Gyroscope data
            
        Returns:
            True if fall detected
        """
        # Calculate total acceleration magnitude
        total_accel = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        
        # Calculate total gyroscope magnitude
        total_gyro = math.sqrt(gyro['x']**2 + gyro['y']**2 + gyro['z']**2)
        
        # Fall detection algorithm:
        # 1. Sudden acceleration change (impact or free fall)
        # 2. High rotation rate (tumbling)
        
        fall_conditions = [
            total_accel > self.config.FALL_THRESHOLD,  # High impact
            total_accel < 0.3,  # Free fall (low acceleration)
            total_gyro > 200   # High rotation rate (degrees/second)
        ]
        
        # Log sensor readings for debugging
        self.logger.debug(f"Accel: {total_accel:.2f}g, Gyro: {total_gyro:.1f}°/s")
        
        # Fall detected if any condition is met
        return any(fall_conditions)
    
    def simulate_fall(self):
        """Simulate a fall for testing purposes"""
        self.logger.info("Simulating fall detection...")
        if self.callback:
            self.callback("fall_simulation")
    
    def cleanup(self):
        """Clean up fall detector resources"""
        self.stop_monitoring()
        self.logger.info("Fall detector cleaned up")