"""
Utility modules for the Emergency Assistance System
"""

from .logger import setup_logging, log_emergency_event, log_sensor_reading

__all__ = ['setup_logging', 'log_emergency_event', 'log_sensor_reading']