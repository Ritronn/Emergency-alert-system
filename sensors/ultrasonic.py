"""
Ultrasonic distance sensor module for proximity detection
"""
import time
import threading
from typing import Optional, Callable
from config import Config

try:
    import RPi.GPIO as GPIO
except ImportError:
    # Mock GPIO for development/testing
    class MockGPIO:
        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        
        @staticmethod
        def setmode(mode): pass
        @staticmethod
        def setup(pin, mode): pass
        @staticmethod
        def output(pin, state): pass
        @staticmethod
        def input(pin): return 0
        @staticmethod
        def cleanup(): pass
    
    GPIO = MockGPIO()

class UltrasonicSensor:
    """
    Ultrasonic distance sensor for detecting proximity to dangerous areas
    """
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        self.trig_pin = config.ULTRASONIC_TRIG
        self.echo_pin = config.ULTRASONIC_ECHO
        
        self.is_monitoring = False
        self.monitor_thread = None
        self.callback = None
        
        # Detection state
        self.danger_count = 0
        self.warning_count = 0
        self.last_alert_time = 0
        
        self._setup_gpio()
    
    def _setup_gpio(self):
        """Initialize GPIO pins for ultrasonic sensor"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.trig_pin, GPIO.OUT)
            GPIO.setup(self.echo_pin, GPIO.IN)
            self.logger.info(f"Ultrasonic sensor initialized on pins {self.trig_pin}/{self.echo_pin}")
        except Exception as e:
            self.logger.error(f"Failed to setup ultrasonic GPIO: {e}")
    
    def get_distance(self) -> Optional[float]:
        """
        Get distance measurement from ultrasonic sensor
        
        Returns:
            Distance in centimeters, or None if reading failed
        """
        try:
            # Send trigger pulse
            GPIO.output(self.trig_pin, True)
            time.sleep(0.00001)  # 10 microseconds
            GPIO.output(self.trig_pin, False)
            
            # Measure echo pulse duration
            start_time = time.time()
            stop_time = time.time()
            timeout = time.time() + 0.04  # 40ms timeout
            
            # Wait for echo start
            while GPIO.input(self.echo_pin) == 0:
                start_time = time.time()
                if time.time() > timeout:
                    return None
            
            # Wait for echo end
            timeout = time.time() + 0.04
            while GPIO.input(self.echo_pin) == 1:
                stop_time = time.time()
                if time.time() > timeout:
                    return None
            
            # Calculate distance
            pulse_duration = stop_time - start_time
            distance = round((pulse_duration * 17150), 2)  # Speed of sound / 2
            
            # Validate reading
            if distance < 2 or distance > 400:
                return None
                
            return distance
            
        except Exception as e:
            self.logger.error(f"Ultrasonic reading error: {e}")
            return None
    
    def start_monitoring(self, proximity_callback: Callable[[str, float], None]):
        """
        Start continuous proximity monitoring
        
        Args:
            proximity_callback: Function to call when proximity alert is triggered
                               Signature: callback(alert_level: str, distance: float)
        """
        if self.is_monitoring:
            self.logger.warning("Ultrasonic monitoring already active")
            return
        
        self.callback = proximity_callback
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Ultrasonic monitoring started")
    
    def stop_monitoring(self):
        """Stop proximity monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        self.logger.info("Ultrasonic monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                distance = self.get_distance()
                
                if distance is not None:
                    self._check_and_alert(distance)
                    
                    # Log status
                    if distance <= self.config.DANGER_ZONE_CM:
                        status = "DANGER"
                    elif distance <= self.config.WARNING_ZONE_CM:
                        status = "WARNING"
                    else:
                        status = "Clear"
                    
                    self.logger.debug(f"Distance: {distance:6.1f} cm | Status: {status}")
                else:
                    self.logger.debug("Ultrasonic reading failed, retrying...")
                
                time.sleep(0.5)  # Reading interval
                
            except Exception as e:
                self.logger.error(f"Error in ultrasonic monitoring loop: {e}")
                time.sleep(1)
    
    def _check_and_alert(self, distance: float):
        """
        Check distance and trigger alerts if necessary
        
        Args:
            distance: Current distance reading in cm
        """
        current_time = time.time()
        
        # Check cooldown period
        if current_time - self.last_alert_time < self.config.ALERT_COOLDOWN:
            return
        
        if distance <= self.config.DANGER_ZONE_CM:
            self.danger_count += 1
            self.warning_count = 0
            
            if self.danger_count >= self.config.READINGS_TO_CONFIRM:
                if self.callback:
                    self.callback("DANGER", distance)
                self.last_alert_time = current_time
                self.danger_count = 0
                
        elif distance <= self.config.WARNING_ZONE_CM:
            self.warning_count += 1
            self.danger_count = 0
            
            if self.warning_count >= self.config.READINGS_TO_CONFIRM:
                if self.callback:
                    self.callback("WARNING", distance)
                self.last_alert_time = current_time
                self.warning_count = 0
        else:
            # Clear zone - reset counters
            self.danger_count = 0
            self.warning_count = 0
    
    def cleanup(self):
        """Clean up GPIO resources"""
        self.stop_monitoring()
        try:
            GPIO.cleanup()
            self.logger.info("Ultrasonic sensor GPIO cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up ultrasonic GPIO: {e}")