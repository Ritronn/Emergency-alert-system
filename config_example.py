"""
Configuration settings for the Emergency Assistance System
EXAMPLE FILE - Copy to config.py and update with your values
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    # === COMMUNICATION SETTINGS ===
    TELEGRAM_BOT_TOKEN: str = "PASTE_YOUR_TOKEN_HERE"
    TELEGRAM_CHAT_ID: str = "PASTE_YOUR_CHAT_ID_HERE"
    
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
        """Load configuration from environment variables"""
        config = cls()
        
        # Override with environment variables if they exist
        config.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config.TELEGRAM_BOT_TOKEN)
        config.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config.TELEGRAM_CHAT_ID)
        
        return config
    
    def validate(self) -> bool:
        """Validate configuration settings"""
        if self.TELEGRAM_BOT_TOKEN == "PASTE_YOUR_TOKEN_HERE":
            print("WARNING: Telegram bot token not configured!")
            return False
            
        if self.TELEGRAM_CHAT_ID == "PASTE_YOUR_CHAT_ID_HERE":
            print("WARNING: Telegram chat ID not configured!")
            return False
            
        return True