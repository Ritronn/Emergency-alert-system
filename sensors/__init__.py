"""
Sensor modules for the Emergency Assistance System
"""

from .voice_detector import VoiceDetector
from .fall_detector import FallDetector

__all__ = ['VoiceDetector', 'FallDetector']