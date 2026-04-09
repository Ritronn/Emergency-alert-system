"""
Logging utilities for the Emergency Assistance System
"""
import logging
import os
from datetime import datetime
from typing import Optional

def setup_logging(log_file: str = "emergency_system.log", level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging configuration
    
    Args:
        log_file: Path to log file
        level: Logging level
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Create logger
    logger = logging.getLogger('EmergencySystem')
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger

def log_emergency_event(logger: logging.Logger, event_type: str, details: dict):
    """
    Log an emergency event with structured data
    
    Args:
        logger: Logger instance
        event_type: Type of emergency event
        details: Event details dictionary
    """
    timestamp = datetime.now().isoformat()
    log_message = f"EMERGENCY EVENT - {event_type} - {timestamp}"
    
    for key, value in details.items():
        log_message += f" | {key}: {value}"
    
    logger.critical(log_message)

def log_sensor_reading(logger: logging.Logger, sensor_type: str, value: float, unit: str = ""):
    """
    Log sensor readings
    
    Args:
        logger: Logger instance
        sensor_type: Type of sensor
        value: Sensor reading value
        unit: Unit of measurement
    """
    logger.debug(f"SENSOR - {sensor_type}: {value} {unit}")