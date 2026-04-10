"""
GPS Sensor Module for GY-GPS6MV2
=================================

Reads GPS data from the GY-GPS6MV2 module connected via UART and provides
location coordinates and Google Maps links for emergency alerts.

Hardware:
  - GPS TX -> RPi Pin 10 (GPIO 15 / RXD)
  - GPS RX -> RPi Pin 8  (GPIO 14 / TXD)
"""

import serial
import threading
import time
from typing import Optional, Tuple, Dict, Any

try:
    import pynmea2
except ImportError:
    pynmea2 = None


class GPSSensor:
    """
    GPS sensor interface for the GY-GPS6MV2 module.
    
    Continuously reads GPS data in a background thread and provides
    the latest location on demand.
    """
    
    # Default configuration
    DEFAULT_PORT = "/dev/serial0"
    DEFAULT_BAUD = 9600
    DEFAULT_TIMEOUT = 1
    
    def __init__(self, logger, port: str = None, baud_rate: int = None):
        """
        Initialize GPS sensor.
        
        Args:
            logger: Logger instance
            port: Serial port path (default: /dev/serial0)
            baud_rate: Serial baud rate (default: 9600)
        """
        self.logger = logger
        self.port = port or self.DEFAULT_PORT
        self.baud_rate = baud_rate or self.DEFAULT_BAUD
        
        # Current GPS data (thread-safe access via lock)
        self._lock = threading.Lock()
        self._latitude: Optional[float] = None
        self._longitude: Optional[float] = None
        self._altitude: Optional[float] = None
        self._speed: Optional[float] = None
        self._satellites: int = 0
        self._has_fix: bool = False
        self._last_update: Optional[float] = None
        
        # Background thread
        self._serial: Optional[serial.Serial] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Check for pynmea2
        if pynmea2 is None:
            self.logger.error("pynmea2 not installed. Run: pip install pynmea2")
            raise ImportError("pynmea2 is required for GPS functionality")
    
    def start(self) -> bool:
        """
        Start GPS data collection in background.
        
        Returns:
            True if GPS started successfully
        """
        if self._running:
            self.logger.warning("GPS sensor already running")
            return True
        
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.DEFAULT_TIMEOUT
            )
            self._running = True
            self._thread = threading.Thread(
                target=self._read_loop,
                daemon=True,
                name="GPS-Reader"
            )
            self._thread.start()
            self.logger.info(f"GPS sensor started on {self.port} @ {self.baud_rate} baud")
            return True
            
        except serial.SerialException as e:
            self.logger.error(f"Failed to open GPS serial port: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to start GPS sensor: {e}")
            return False
    
    def stop(self):
        """Stop GPS data collection"""
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        if self._serial and self._serial.is_open:
            self._serial.close()
        
        self.logger.info("GPS sensor stopped")
    
    def _read_loop(self):
        """Background loop to continuously read GPS data"""
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    time.sleep(1)
                    continue
                
                line = self._serial.readline().decode('ascii', errors='replace').strip()
                
                if not line.startswith('$'):
                    continue
                
                try:
                    msg = pynmea2.parse(line)
                except pynmea2.ParseError:
                    continue
                
                self._process_nmea(msg)
                
            except serial.SerialException as e:
                self.logger.error(f"GPS serial error: {e}")
                time.sleep(2)  # Wait before retrying
            except Exception as e:
                self.logger.debug(f"GPS read error: {e}")
                time.sleep(0.1)
    
    def _process_nmea(self, msg):
        """
        Process a parsed NMEA sentence and update stored location.
        
        Args:
            msg: Parsed pynmea2 message
        """
        with self._lock:
            # Process RMC (Recommended Minimum) - most useful for position
            if msg.sentence_type == 'RMC':
                if msg.status == 'A':  # 'A' = Active/Valid fix
                    self._latitude = msg.latitude
                    self._longitude = msg.longitude
                    self._speed = msg.spd_over_grnd if msg.spd_over_grnd else 0.0
                    self._has_fix = True
                    self._last_update = time.time()
                else:
                    self._has_fix = False
            
            # Process GGA - for altitude and satellite count
            elif msg.sentence_type == 'GGA':
                try:
                    self._satellites = int(msg.num_sats) if msg.num_sats else 0
                except (ValueError, AttributeError):
                    pass
                
                if msg.gps_qual > 0:
                    self._latitude = msg.latitude
                    self._longitude = msg.longitude
                    self._altitude = msg.altitude if msg.altitude else None
                    self._has_fix = True
                    self._last_update = time.time()
    
    @property
    def has_fix(self) -> bool:
        """Check if GPS currently has a valid fix"""
        with self._lock:
            # Consider fix stale after 10 seconds of no updates
            if self._last_update and (time.time() - self._last_update) > 10:
                return False
            return self._has_fix
    
    def get_location(self) -> Optional[Tuple[float, float]]:
        """
        Get current GPS coordinates.
        
        Returns:
            Tuple of (latitude, longitude) or None if no fix
        """
        with self._lock:
            if self._has_fix and self._latitude is not None and self._longitude is not None:
                return (self._latitude, self._longitude)
            return None
    
    def get_google_maps_link(self) -> Optional[str]:
        """
        Get a Google Maps link for the current location.
        
        Returns:
            Google Maps URL string or None if no fix
        """
        location = self.get_location()
        if location:
            lat, lon = location
            return f"https://maps.google.com/maps?q={lat:.6f},{lon:.6f}"
        return None
    
    def get_location_details(self) -> Dict[str, Any]:
        """
        Get detailed location information for emergency alerts.
        
        Returns:
            Dictionary with location details
        """
        with self._lock:
            if self._has_fix and self._latitude is not None:
                maps_link = f"https://maps.google.com/maps?q={self._latitude:.6f},{self._longitude:.6f}"
                return {
                    "latitude": self._latitude,
                    "longitude": self._longitude,
                    "altitude": self._altitude,
                    "speed": self._speed,
                    "satellites": self._satellites,
                    "maps_link": maps_link,
                    "has_fix": True,
                    "last_update": self._last_update
                }
            else:
                return {
                    "has_fix": False,
                    "satellites": self._satellites,
                    "maps_link": None
                }
    
    def get_emergency_location_text(self) -> str:
        """
        Get formatted location text for emergency messages.
        
        Returns:
            Formatted string with location info and Google Maps link
        """
        details = self.get_location_details()
        
        if details["has_fix"]:
            lat = details["latitude"]
            lon = details["longitude"]
            sats = details["satellites"]
            maps_link = details["maps_link"]
            
            text = (
                f"📍 GPS Location: {lat:.6f}, {lon:.6f}\n"
                f"📡 Satellites: {sats}\n"
                f"🗺️ Map: {maps_link}"
            )
            
            if details.get("altitude") is not None:
                text += f"\n📏 Altitude: {details['altitude']:.1f}m"
            
            return text
        else:
            return "📍 GPS Location: Unavailable (no satellite fix)"
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in kilometers
        """
        import math
        
        R = 6371.0  # Earth's radius in km
        
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def distance_from(self, target_lat: float, target_lon: float) -> Optional[float]:
        """
        Calculate distance from current position to a target point.
        
        Args:
            target_lat: Target latitude
            target_lon: Target longitude
            
        Returns:
            Distance in km, or None if no GPS fix
        """
        location = self.get_location()
        if location:
            lat, lon = location
            return self.haversine_distance(lat, lon, target_lat, target_lon)
        return None
    
    def cleanup(self):
        """Clean up GPS resources"""
        self.stop()
