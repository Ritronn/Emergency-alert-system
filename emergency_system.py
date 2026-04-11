
import os
import signal
import sys
import time
import threading
from datetime import datetime
from typing import Optional

# Import our modules
from config import Config
from utils import setup_logging, log_emergency_event
from sensors import VoiceDetector, FallDetector, GPSSensor
from communication import TwilioSMS, SupabaseClient
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
        self.sms_client = None
        self.camera_recorder = None
        self.voice_detector = None
        self.fall_detector = None
        self.gps_sensor = None
        
        # System state
        self.is_running = False
        self.confirmation_timer = None
        self.pending_emergency = None
        
        # Geofencing state
        self.safe_zone_lat = None
        self.safe_zone_lon = None
        self.safe_zone_radius_km = self.config.SAFE_ZONE_RADIUS_KM
        self.last_perimeter_alert_time = None
        self.perimeter_alert_interval = self.config.PERIMETER_ALERT_INTERVAL
        
        # Supabase client
        self.supabase = None
        
        # Initialize all components
        self._initialize_components()
        
        self.logger.info("Emergency System initialized successfully")
    
    def _initialize_components(self):
        """Initialize all system components"""
        try:
            # Initialize Supabase client and fetch dynamic data
            emergency_contacts = [self.config.DEFAULT_EMERGENCY_PHONE]  # fallback
            try:
                self.supabase = SupabaseClient(
                    self.config.SUPABASE_URL,
                    self.config.SUPABASE_KEY,
                    self.logger
                )
                data = self.supabase.fetch_all()
                
                # Update contacts from Supabase
                if data["contacts"]:
                    emergency_contacts = data["contacts"]
                else:
                    self.logger.warning("No contacts from Supabase, using default")
                
                # Set safe zone from Supabase
                if data["safe_location"]:
                    self.safe_zone_lat, self.safe_zone_lon = data["safe_location"]
                    self.logger.info(f"Geofence set: {self.safe_zone_lat:.6f}, {self.safe_zone_lon:.6f} (radius: {self.safe_zone_radius_km}km)")
                else:
                    self.logger.warning("No safe location from Supabase - geofencing disabled")
                    
            except Exception as e:
                self.logger.warning(f"Supabase unavailable, using defaults: {e}")
            
            # Initialize Twilio SMS client with contacts
            self.sms_client = TwilioSMS(
                self.config.TWILIO_ACCOUNT_SID,
                self.config.TWILIO_AUTH_TOKEN,
                self.config.TWILIO_PHONE,
                emergency_contacts,
                self.logger
            )
            
            # Initialize camera recorder
            self.camera_recorder = CameraRecorder(self.config, self.logger)
            
            # Initialize sensors
            self.voice_detector = VoiceDetector(self.config, self.logger)
            self.fall_detector = FallDetector(self.config, self.logger)
            
            # Initialize GPS sensor
            try:
                self.gps_sensor = GPSSensor(self.logger)
                if self.gps_sensor.start():
                    self.logger.info("GPS sensor started successfully")
                else:
                    self.logger.warning("GPS sensor failed to start - location will be unavailable")
                    self.gps_sensor = None
            except Exception as e:
                self.logger.warning(f"GPS sensor not available: {e}")
                self.gps_sensor = None
            
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
            # Start sensors
            if self.voice_detector:
                self.voice_detector.start_listening(self._voice_emergency, self._voice_confirmation)
                sensors_list = "Voice, Fall Detection"
            else:
                sensors_list = "Fall Detection (Voice disabled)"
                
            self.fall_detector.start_monitoring(self._fall_detected)
            
            # Log startup (terminal only, no Telegram)
            self.logger.info(f"System started - Sensors: {sensors_list}, Recording: Ready")
            
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
            # Stop sensors
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
            
            # Log shutdown (terminal only, no Telegram)
            self.logger.info("Emergency monitoring system stopped")
            
            self.logger.info("Emergency monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping monitoring: {e}")
    
    def _main_loop(self):
        """Main system monitoring loop"""
        self.logger.info("Entering main monitoring loop...")
        
        try:
            while self.is_running:
                # Check geofence perimeter
                self._check_perimeter()
                
                # Sensors run in their own threads
                time.sleep(5)  # Check every 5 seconds
                
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
        self._trigger_emergency("fall", requires_confirmation=True, auto_confirm=False)
    
    def _check_perimeter(self):
        """Check if user has exceeded the geofence perimeter"""
        # Skip if no safe zone is configured or no GPS
        if not self.safe_zone_lat or not self.safe_zone_lon:
            return
        if not self.gps_sensor or not self.gps_sensor.has_fix:
            return
        
        distance_km = self.gps_sensor.distance_from(self.safe_zone_lat, self.safe_zone_lon)
        if distance_km is None:
            return
        
        # Check if outside safe zone
        if distance_km > self.safe_zone_radius_km:
            current_time = time.time()
            
            # Only alert if: first time OR 30 min since last alert
            should_alert = (
                self.last_perimeter_alert_time is None or
                (current_time - self.last_perimeter_alert_time) >= self.perimeter_alert_interval
            )
            
            if should_alert:
                self.last_perimeter_alert_time = current_time
                self.logger.warning(f"PERIMETER BREACH: {distance_km:.1f} km from safe zone")
                
                # Build alert details with location
                gps_text = self.gps_sensor.get_emergency_location_text()
                maps_link = self.gps_sensor.get_google_maps_link()
                
                details = {
                    "distance_km": distance_km,
                    "gps_info": gps_text,
                    "location": maps_link or "Unknown",
                }
                
                # Send directly — no confirmation needed for perimeter breach
                self.sms_client.send_emergency_alert("perimeter_breach", details)
        else:
            # Back inside safe zone — reset the alert timer
            if self.last_perimeter_alert_time is not None:
                self.logger.info("User returned to safe zone")
                self.last_perimeter_alert_time = None
    
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
            
            # Log confirmation prompt (terminal only, no Telegram)
            self.logger.info(f"Emergency detected! Say 'YES' to confirm or wait {self.config.CONFIRMATION_TIMEOUT}s to cancel")
            
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
        
        self.logger.info("Emergency confirmed by user")
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
        
        # Get GPS location (hardcoded coordinates)
        maps_link = "https://maps.google.com/maps?q=18.486600,73.816300"
        gps_location_text = (
            "GPS Location: 18.486600, 73.816300\n"
            f"Map: {maps_link}"
        )
        self.logger.info(f"GPS location included: {maps_link}")
        
        # Prepare emergency details
        location_str = maps_link if maps_link else "Home - Emergency System"
        details = {
            "location": location_str,
            "gps_info": gps_location_text,
            "recording_status": recording_status,
            "recording_path": recording_path,
            "timeout": self.config.CONFIRMATION_TIMEOUT
        }
        
        # Add source-specific details
        if source == "fall":
            details["impact"] = "High"  # Could be actual sensor reading
        
        # Send emergency alert
        self.sms_client.send_emergency_alert(source, details)
        
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
        
        # Send recording notification if it exists
        if recording_path and os.path.exists(recording_path):
            self.sms_client.send_system_status("recording_completed", {
                "File": os.path.basename(recording_path),
                "Size": f"{os.path.getsize(recording_path)} bytes"
            })
            self.logger.info(f"Recording saved: {recording_path}")
        else:
            self.logger.error("Recording file not found or recording failed")
    
    def cleanup(self):
        """Clean up all system resources"""
        self.logger.info("Cleaning up system resources...")
        
        self.stop_monitoring()
        
        # Clean up components
        if self.voice_detector:
            self.voice_detector.cleanup()
        if self.fall_detector:
            self.fall_detector.cleanup()
        if self.gps_sensor:
            self.gps_sensor.cleanup()
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
        print("  - GPS Location: Google Maps link with emergency alerts")
        print("  - Video Recording: 30-second emergency capture")
        print("  - SMS Alerts: Real-time Twilio SMS notifications")
        print("  - Supabase: Dynamic contacts & safe locations")
        
        if emergency_system.safe_zone_lat:
            print(f"  - Geofencing: {emergency_system.safe_zone_radius_km}km radius | Alert every 30min")
        else:
            print("  - Geofencing: Disabled (no safe location set)")
        
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