"""
Telegram bot communication module for emergency alerts
"""
import requests
import time
from typing import Optional, Dict, Any
from datetime import datetime

class TelegramBot:
    """
    Telegram bot for sending emergency alerts and notifications
    """
    
    def __init__(self, bot_token: str, chat_id: str, logger):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logger
        
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self):
        """Test Telegram bot connection"""
        try:
            response = self._make_request("getMe")
            if response and response.get('ok'):
                bot_info = response.get('result', {})
                self.logger.info(f"Telegram bot connected: {bot_info.get('first_name', 'Unknown')}")
            else:
                self.logger.error("Failed to connect to Telegram bot")
        except Exception as e:
            self.logger.error(f"Telegram connection test failed: {e}")
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a text message via Telegram
        
        Args:
            message: Message text to send
            parse_mode: Message formatting (HTML or Markdown)
            
        Returns:
            True if message sent successfully
        """
        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        response = self._make_request("sendMessage", data)
        
        if response and response.get('ok'):
            self.logger.info(f"Telegram message sent: {message[:50]}...")
            return True
        else:
            self.logger.error(f"Failed to send Telegram message: {response}")
            return False
    
    def send_emergency_alert(self, alert_type: str, details: Dict[str, Any]) -> bool:
        """
        Send formatted emergency alert
        
        Args:
            alert_type: Type of emergency (voice, fall, proximity, button)
            details: Emergency details dictionary
            
        Returns:
            True if alert sent successfully
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format message based on alert type
        if alert_type == "voice":
            message = (
                f"EMERGENCY ALERT - Voice Command\n\n"
                f"Time: {timestamp}\n"
                f"Trigger: Voice command detected\n"
                f"Location: {details.get('location', 'Unknown')}\n"
                f"Status: Waiting for confirmation\n\n"
                f"You have {details.get('timeout', 10)} seconds to confirm or cancel."
            )
        
        elif alert_type == "fall":
            message = (
                f"EMERGENCY ALERT - Fall Detected\n\n"
                f"Time: {timestamp}\n"
                f"Trigger: Fall detection sensor\n"
                f"Impact: {details.get('impact', 'Unknown')} g-force\n"
                f"Location: {details.get('location', 'Unknown')}\n"
                f"Recording: {details.get('recording_status', 'Starting...')}\n\n"
                f"IMMEDIATE ATTENTION REQUIRED"
            )
        
        elif alert_type == "proximity":
            level = details.get('level', 'WARNING')
            distance = details.get('distance', 'Unknown')
            
            if level == "DANGER":
                urgency = "IMMEDIATE DANGER"
            else:
                urgency = "WARNING"
            
            message = (
                f"{urgency} - Proximity Alert\n\n"
                f"Time: {timestamp}\n"
                f"Distance: {distance} cm\n"
                f"Someone is near the staircase edge!\n"
                f"Location: {details.get('location', 'Staircase area')}\n\n"
                f"Please check immediately!"
            )
        
        elif alert_type == "button":
            message = (
                f"EMERGENCY ALERT - Manual Trigger\n\n"
                f"Time: {timestamp}\n"
                f"Trigger: Emergency button pressed\n"
                f"Location: {details.get('location', 'Unknown')}\n"
                f"Recording: {details.get('recording_status', 'Starting...')}\n\n"
                f"IMMEDIATE ATTENTION REQUIRED"
            )
        
        else:
            message = (
                f"EMERGENCY ALERT\n\n"
                f"Time: {timestamp}\n"
                f"Type: {alert_type}\n"
                f"Location: {details.get('location', 'Unknown')}\n\n"
                f"Please check the situation immediately."
            )
        
        return self.send_message(message)
    
    def send_confirmation_prompt(self, timeout: int = 10) -> bool:
        """
        Send confirmation prompt message
        
        Args:
            timeout: Confirmation timeout in seconds
            
        Returns:
            True if message sent successfully
        """
        message = (
            f"Emergency Confirmation Required\n\n"
            f"Say 'YES' to confirm emergency\n"
            f"Or wait {timeout} seconds to cancel\n\n"
            f"Listening for your response..."
        )
        
        return self.send_message(message)
    
    def send_system_status(self, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send system status update
        
        Args:
            status: Status message (started, stopped, error, etc.)
            details: Optional status details
            
        Returns:
            True if message sent successfully
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        status_messages = {
            "started": "Emergency System Started",
            "stopped": "Emergency System Stopped",
            "error": "System Error",
            "recording_started": "Emergency Recording Started",
            "recording_completed": "Emergency Recording Completed",
            "alert_cancelled": "Emergency Alert Cancelled",
            "confirmation_received": "Emergency Confirmed"
        }
        
        title = status_messages.get(status, f"System Update: {status}")
        
        message = f"{title}\n\nTime: {timestamp}"
        
        if details:
            for key, value in details.items():
                message += f"\n{key}: {value}"
        
        return self.send_message(message)
    
    def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """
        Send a photo via Telegram
        
        Args:
            photo_path: Path to photo file
            caption: Photo caption
            
        Returns:
            True if photo sent successfully
        """
        try:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption
                }
                
                response = requests.post(
                    f"{self.base_url}/sendPhoto",
                    files=files,
                    data=data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        self.logger.info(f"Photo sent successfully: {photo_path}")
                        return True
                
                self.logger.error(f"Failed to send photo: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending photo: {e}")
            return False
    
    def send_video(self, video_path: str, caption: str = "") -> bool:
        """
        Send a video via Telegram
        
        Args:
            video_path: Path to video file
            caption: Video caption
            
        Returns:
            True if video sent successfully
        """
        try:
            with open(video_path, 'rb') as video:
                files = {'video': video}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption
                }
                
                response = requests.post(
                    f"{self.base_url}/sendVideo",
                    files=files,
                    data=data,
                    timeout=60  # Longer timeout for video uploads
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        self.logger.info(f"Video sent successfully: {video_path}")
                        return True
                
                self.logger.error(f"Failed to send video: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending video: {e}")
            return False
    
    def _make_request(self, method: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to Telegram API
        
        Args:
            method: API method name
            data: Request data
            
        Returns:
            Response JSON or None if failed
        """
        try:
            url = f"{self.base_url}/{method}"
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error("Telegram request timeout")
            return None
        except Exception as e:
            self.logger.error(f"Telegram request error: {e}")
            return None