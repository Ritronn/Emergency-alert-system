"""
Main Emergency Assistance System for Raspberry Pi

A comprehensive emergency detection and response system that provides:
- Voice-activated emergency detection ("help help help")
- Fall detection using accelerometer/gyroscope
- Proximity detection using ultrasonic sensor
- Manual emergency button
- 30-second video recording during emergencies
- Telegram alerts with location and status
"""

import signal
import sys
import time
import threading
from datetime import datetime
from typing import Optional

# Import our modules
from config import Config
from utils import setup_logging, log_emergency_event
from sensors import UltrasonicSensor, VoiceDetector, FallDetector
from communication import TelegramBot
from recording import CameraRecorder

try:
    import RPi.GPIO as GPIO
except ImportError:
    # Mock GPIO for development/testing
    class MockGPIO:
        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        FALLING = "FALLING"
        PUD_UP = "PUD_UP"
        
        @staticmethod
        def setmode(mode): pass
        @staticmethod
        def setup(pin, mode, **kwargs): pass
        @staticmethod
        def output(pin, state): pass
        @staticmethod
        def input(pin): return 1  # Button not pressed
        @staticmethod
        def add_event_detect(pin, edge, **kwargs): pass
        @staticmethod
        def cleanup(): pass
    
    GPIO = MockGPIO()

class EmergencySystem:
    """
    Main Emergency Assistance System Controller
    """
    
    def __init__(self):
        # Load configuration
        self.config = Config.load_from_env()
        
        # Setup logging
        self.logger = setup_logging(self.config.LOG_FILE)
        
        # Validate configuration
        if not self.config.validate():
            self.logger.error("Configuration validation failed!")
            sys.exit(1)
        
        # Initialize components
        self.telegram_bot = None
        self.camera_recorder = None
        self.ultrasonic_sensor = None
        self.voice_detector = None
        self.fall_detector = None
        
        # System state
        self.is_running = False
        self.confirmation_timer = None
        self.pending_emergency = None
        
        # Initialize all components
        self._initialize_components()
        
        self.logger.info("Emergency System initialized successfully")
    
    def _initialize_components(self):
        """Initialize all system components"""
        try:
            # Initialize Telegram bot
            self.telegram_bot = TelegramBot(
                self.config.TELEGRAM_BOT_TOKEN,
                self.config.TELEGRAM_CHAT_ID,
                self.logger
            )
            
            # Initialize camera recorder
            self.camera_recorder = CameraRecorder(self.config, self.logger)
            
            # Initialize sensors
            self.ultrasonic_sensor = UltrasonicSensor(self.config, self.logger)
            self.voice_detector = VoiceDetector(self.config, self.logger)
            self.fall_detector = FallDetector(self.config, self.logger)
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    def start_monitoring(self):
        """Start all monitoring systems"""
        if self.is_running:
            self.logger.warning("System already running")
            return
        
        self.is_running = True
        
        try:
            # Start all sensors
            self.ultrasonic_sensor.start_monitoring(self._proximity_alert)
            self.voice_detector.start_listening(self._voice_emergency, self._voice_confirmation)
            self.fall_detector.start_monitoring(self._fall_detected)
            
            # Send startup notification
            self.telegram_bot.send_system_status("started", {
                "Location": "Emergency monitoring active",
                "Sensors": "Voice, Fall, Proximity",
                "Recording": "Ready"
            })
            
            self.logger.info("Emergency monitoring started - all systems active")
            
            # Main monitoring loop
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Error starting monitoring: {e}")
            self.stop_monitoring()
    
    def stop_monitoring(self):
        """Stop all monitoring systems"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        try:
            # Stop all sensors
            if self.ultrasonic_sensor:
                self.ultrasonic_sensor.stop_monitoring()
            if self.voice_detector:
                self.voice_detector.stop_listening()
            if self.fall_detector:
                self.fall_detector.stop_monitoring()
            
            # Stop any ongoing recording
            if self.camera_recorder:
                self.camera_recorder.stop_recording()
            
            # Cancel any pending confirmation
            if self.confirmation_timer:
                self.confirmation_timer.cancel()
            
            # Send shutdown notification
            self.telegram_bot.send_system_status("stopped")
            
            self.logger.info("Emergency monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping monitoring: {e}")
    
    def _main_loop(self):
        """Main system monitoring loop"""
        self.logger.info("Entering main monitoring loop...")
        
        try:
            while self.is_running:
                # Simple monitoring loop - sensors run in their own threads
                time.sleep(3)  # Check every 3 seconds
                
        except KeyboardInterrupt:
            self.logger.info("Shutdown requested by user")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.stop_monitoring()
    
    def _voice_emergency(self, source: str):
        """Handle voice emergency detection"""
        self.logger.warning(f"Voice emergency detected from {source}")
        
        # Voice commands require confirmation
        self._trigger_emergency("voice", requires_confirmation=True)
    
    def _voice_confirmation(self):
        """Handle voice confirmation"""
        if self.pending_emergency:
            self.logger.info("Voice confirmation received")
            self._confirm_emergency()
        else:
            self.logger.debug("Voice confirmation received but no pending emergency")
    
    def _fall_detected(self, source: str):
        """Handle fall detection"""
        self.logger.warning(f"Fall detected: {source}")
        
        # Falls require confirmation but auto-confirm if no response
        self._trigger_emergency("fall", requires_confirmation=True, auto_confirm=True)
    
    def _proximity_alert(self, level: str, distance: float):
        """Handle proximity alerts"""
        self.logger.warning(f"Proximity alert: {level} at {distance} cm")
        
        # Send proximity notification (not full emergency)
        details = {
            "level": level,
            "distance": distance,
            "location": "Staircase area"
        }
        
        self.telegram_bot.send_emergency_alert("proximity", details)
    
    def _trigger_emergency(self, source: str, requires_confirmation: bool = True, auto_confirm: bool = False):
        """
        Trigger emergency alert process
        
        Args:
            source: Source of emergency (voice, fall, button, etc.)
            requires_confirmation: Whether confirmation is needed
            auto_confirm: Whether to auto-confirm if no response
        """
        current_time = datetime.now()
        
        # Log emergency event
        log_emergency_event(self.logger, source, {
            "timestamp": current_time.isoformat(),
            "requires_confirmation": requires_confirmation,
            "auto_confirm": auto_confirm
        })
        
        if not requires_confirmation:
            # Immediate emergency (button press)
            self._execute_emergency(source)
        else:
            # Start confirmation process
            self.pending_emergency = {
                "source": source,
                "timestamp": current_time,
                "auto_confirm": auto_confirm
            }
            
            # Send confirmation prompt
            self.telegram_bot.send_confirmation_prompt(self.config.CONFIRMATION_TIMEOUT)
            
            # Start confirmation timer
            self.confirmation_timer = threading.Timer(
                self.config.CONFIRMATION_TIMEOUT,
                self._confirmation_timeout
            )
            self.confirmation_timer.start()
            
            self.logger.info(f"Waiting for confirmation ({self.config.CONFIRMATION_TIMEOUT}s)")
    
    def _confirm_emergency(self):
        """Confirm pending emergency"""
        if not self.pending_emergency:
            return
        
        # Cancel timer
        if self.confirmation_timer:
            self.confirmation_timer.cancel()
        
        source = self.pending_emergency["source"]
        self.pending_emergency = None
        
        self.telegram_bot.send_system_status("confirmation_received")
        self._execute_emergency(source)
    
    def _confirmation_timeout(self):
        """Handle confirmation timeout"""
        if not self.pending_emergency:
            return
        
        source = self.pending_emergency["source"]
        auto_confirm = self.pending_emergency.get("auto_confirm", False)
        
        if auto_confirm:
            # Auto-confirm for falls (user might be unconscious)
            self.logger.warning(f"Auto-confirming emergency due to timeout: {source}")
            self._execute_emergency(source)
        else:
            # Cancel for voice commands
            self.logger.info(f"Emergency cancelled due to timeout: {source}")
            self.telegram_bot.send_system_status("alert_cancelled")
        
        self.pending_emergency = None
    
    def _execute_emergency(self, source: str):
        """
        Execute emergency response
        
        Args:
            source: Source of emergency
        """
        self.logger.critical(f"EXECUTING EMERGENCY RESPONSE - Source: {source}")
        
        # Start video recording
        recording_path = None
        if self.camera_recorder:
            recording_path = self.camera_recorder.start_recording()
            recording_status = "Started" if recording_path else "Failed"
        else:
            recording_status = "Not available"
        
        # Prepare emergency details
        details = {
            "location": "Home - Emergency System",
            "recording_status": recording_status,
            "recording_path": recording_path,
            "timeout": self.config.CONFIRMATION_TIMEOUT
        }
        
        # Add source-specific details
        if source == "fall":
            details["impact"] = "High"  # Could be actual sensor reading
        
        # Send emergency alert
        self.telegram_bot.send_emergency_alert(source, details)
        
        # Send recording when complete (in background)
        if recording_path:
            threading.Thread(
                target=self._send_recording_when_complete,
                args=(recording_path,),
                daemon=True
            ).start()
    
    def _send_recording_when_complete(self, recording_path: str):
        """
        Send recording to Telegram when recording is complete
        
        Args:
            recording_path: Path to recording file
        """
        # Wait for recording to complete
        timeout = self.config.RECORDING_DURATION + 10  # Extra time for processing
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not self.camera_recorder.is_recording:
                break
            time.sleep(1)
        
        # Send recording if it exists
        if recording_path and os.path.exists(recording_path):
            caption = f"Emergency Recording - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            if self.telegram_bot.send_video(recording_path, caption):
                self.telegram_bot.send_system_status("recording_completed", {
                    "File": os.path.basename(recording_path),
                    "Size": f"{os.path.getsize(recording_path)} bytes"
                })
            else:
                self.logger.error("Failed to send emergency recording")
        else:
            self.logger.error("Recording file not found or recording failed")
    
    def cleanup(self):
        """Clean up all system resources"""
        self.logger.info("Cleaning up system resources...")
        
        self.stop_monitoring()
        
        # Clean up components
        if self.ultrasonic_sensor:
            self.ultrasonic_sensor.cleanup()
        if self.voice_detector:
            self.voice_detector.cleanup()
        if self.fall_detector:
            self.fall_detector.cleanup()
        if self.camera_recorder:
            self.camera_recorder.cleanup()
        
        # Clean up GPIO
        try:
            GPIO.cleanup()
        except Exception as e:
            self.logger.error(f"Error cleaning up GPIO: {e}")
        
        self.logger.info("System cleanup complete")

# Global system instance for signal handling
emergency_system = None

def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown"""
    global emergency_system
    
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    
    if emergency_system:
        emergency_system.cleanup()
    
    sys.exit(0)

def main():
    """Main entry point"""
    global emergency_system
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create and start emergency system
        emergency_system = EmergencySystem()
        
        print("=" * 60)
        print("EMERGENCY ASSISTANCE SYSTEM STARTING")
        print("=" * 60)
        print("Features:")
        print("  - Voice Commands: Say 'help help help' 3 times (VOSK offline)")
        print("  - Fall Detection: Automatic detection via sensor")
        print("  - Proximity Alerts: Staircase safety monitoring")
        print("  - Video Recording: 30-second emergency capture")
        print("  - Telegram Alerts: Real-time notifications")
        print("=" * 60)
        print("Press Ctrl+C to stop")
        print("=" * 60)
        
        # Start monitoring
        emergency_system.start_monitoring()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        if emergency_system:
            emergency_system.cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()