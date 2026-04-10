"""
Sensor modules for the Emergency Assistance System
"""

from .voice_detector import VoiceDetector
from .fall_detector import FallDetector
from .gps_sensor import GPSSensor

__all__ = ['VoiceDetector', 'FallDetector', 'GPSSensor']