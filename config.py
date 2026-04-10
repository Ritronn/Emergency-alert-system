"""
Configuration settings for the Emergency Assistance System
"""
from dataclasses import dataclass

@dataclass
class Config:
    # === COMMUNICATION SETTINGS ===
    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = "YOUR_TWILIO_ACCOUNT_SID"
    TWILIO_AUTH_TOKEN: str = "YOUR_TWILIO_AUTH_TOKEN"
    TWILIO_PHONE: str = "+16626322267"
    
    # Default emergency contact (fallback if Supabase is unavailable)
    DEFAULT_EMERGENCY_PHONE: str = "+917498683368"
    
    # Supabase (for dynamic contacts & safe locations)
    SUPABASE_URL: str = "https://ohwmquomashztbjqeqcn.supabase.co"
    SUPABASE_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9od21xdW9tYXNoenRianFlcWNuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNjI1ODAsImV4cCI6MjA5MDYzODU4MH0.C6K9GiEk4eZtcDswzHTd8-Ki3tT0d-0aobw4xOt-jjY"
    
    # Geofencing
    SAFE_ZONE_RADIUS_KM: float = 5.0  # km
    PERIMETER_ALERT_INTERVAL: int = 1800  # 30 minutes in seconds
    
    # Legacy Telegram (kept for reference)
    # TELEGRAM_BOT_TOKEN: str = "8673950449:AAGT9GTD9NM31CJY576iSM7cgD0o_SG-RQM"
    # TELEGRAM_CHAT_ID: str = "1530447839"
    
    # === HARDWARE PINS (GPIO BCM) ===
    # Optional buzzer for audio feedback
    BUZZER: int = 19
    
    # === DETECTION THRESHOLDS ===
    # Voice detection
    HELP_KEYWORD: str = "help"
    HELP_COUNT_REQUIRED: int = 3
    CONFIRMATION_KEYWORD: str = "yes"
    CONFIRMATION_TIMEOUT: int = 10  # seconds
    
    # Fall detection (accelerometer/gyroscope)
    FALL_THRESHOLD: float = 2.5  # g-force
    FALL_TIME_WINDOW: float = 0.5  # seconds
    
    # === RECORDING SETTINGS ===
    RECORDING_DURATION: int = 30  # seconds
    RECORDINGS_DIR: str = "recordings"
    VIDEO_RESOLUTION: tuple = (640, 480)
    VIDEO_FPS: int = 15
    
    # === SYSTEM SETTINGS ===
    DATABASE_PATH: str = "emergency_system.db"
    LOG_FILE: str = "emergency_system.log"
    ENCRYPTION_KEY_FILE: str = "encryption.key"
    
    # Alert cooldown to prevent spam
    ALERT_COOLDOWN: int = 15  # seconds
    
    # === AUDIO SETTINGS ===
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHUNK_SIZE: int = 1024
    AUDIO_CHANNELS: int = 1
    
    @classmethod
    def load_from_env(cls) -> 'Config':
        """Load configuration"""
        return cls()
    
    def validate(self) -> bool:
        """Validate configuration settings"""
        if not self.TWILIO_ACCOUNT_SID or self.TWILIO_ACCOUNT_SID == "PASTE_YOUR_SID_HERE":
            print("WARNING: Twilio Account SID not configured!")
            return False
            
        if not self.TWILIO_AUTH_TOKEN or self.TWILIO_AUTH_TOKEN == "PASTE_YOUR_TOKEN_HERE":
            print("WARNING: Twilio Auth Token not configured!")
            return False
            
        return True