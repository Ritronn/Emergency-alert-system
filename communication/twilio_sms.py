"""
Twilio SMS communication module for emergency alerts
Replaces Telegram bot with SMS-based alert routing
"""

from twilio.rest import Client
from typing import Optional, Dict, Any, List
from datetime import datetime


class TwilioSMS:
    """
    Twilio SMS client for sending emergency alerts via text message
    """
    
    def __init__(self, account_sid: str, auth_token: str, from_phone: str, 
                 to_phones: List[str], logger):
        """
        Initialize Twilio SMS client.
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_phone: Twilio phone number (sender)
            to_phones: List of recipient phone numbers
            logger: Logger instance
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_phone = from_phone
        self.to_phones = to_phones
        self.logger = logger
        
        # Initialize Twilio client
        try:
            self.client = Client(account_sid, auth_token)
            self.logger.info(f"Twilio SMS initialized - sending to {len(to_phones)} contacts")
        except Exception as e:
            self.logger.error(f"Failed to initialize Twilio client: {e}")
            raise
    
    def update_contacts(self, phone_numbers: List[str]):
        """
        Update the list of emergency contacts.
        
        Args:
            phone_numbers: New list of recipient phone numbers
        """
        self.to_phones = phone_numbers
        self.logger.info(f"Emergency contacts updated: {len(phone_numbers)} contacts")
    
    def send_message(self, message: str) -> bool:
        """
        Send SMS message to all emergency contacts via Twilio.
        
        Args:
            message: Message text to send
            
        Returns:
            True if at least one message sent successfully
        """
        if not self.to_phones:
            self.logger.error("No emergency contacts configured")
            return False
        
        success_count = 0
        for phone in self.to_phones:
            try:
                sms = self.client.messages.create(
                    body=message,
                    from_=self.from_phone,
                    to=phone
                )
                self.logger.info(f"SMS sent to {phone} (SID: {sms.sid})")
                success_count += 1
            except Exception as e:
                self.logger.error(f"Failed to send SMS to {phone}: {e}")
        
        self.logger.info(f"SMS sent to {success_count}/{len(self.to_phones)} contacts")
        return success_count > 0
    
    def send_emergency_alert(self, alert_type: str, details: Dict[str, Any]) -> bool:
        """
        Send formatted emergency alert via SMS.
        
        Args:
            alert_type: Type of emergency (voice, fall, button, perimeter)
            details: Emergency details dictionary
            
        Returns:
            True if alert sent successfully
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get GPS info if available
        gps_info = details.get('gps_info', '')
        
        if alert_type == "voice":
            message = (
                f"EMERGENCY - Voice Command\n"
                f"Time: {timestamp}\n"
                f"User said the emergency keyword.\n"
            )
        
        elif alert_type == "fall":
            message = (
                f"EMERGENCY - Fall Detected\n"
                f"Time: {timestamp}\n"
                f"Impact: {details.get('impact', 'High')}\n"
                f"Recording: {details.get('recording_status', 'Started')}\n"
            )
        
        elif alert_type == "button":
            message = (
                f"EMERGENCY - Panic Button\n"
                f"Time: {timestamp}\n"
                f"Manual emergency trigger pressed.\n"
            )
        
        elif alert_type == "perimeter_breach":
            distance = details.get('distance_km', '?')
            message = (
                f"PERIMETER ALERT\n"
                f"Time: {timestamp}\n"
                f"User is {distance:.1f} km away from safe zone.\n"
            )
        
        else:
            message = (
                f"EMERGENCY ALERT\n"
                f"Time: {timestamp}\n"
                f"Type: {alert_type}\n"
            )
        
        # Append GPS info
        if gps_info:
            message += f"\n{gps_info}"
        
        message += "\nIMMEDIATE ATTENTION REQUIRED"
        
        return self.send_message(message)
    
    def send_system_status(self, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send system status update via SMS.
        
        Args:
            status: Status type
            details: Optional details
            
        Returns:
            True if message sent successfully
        """
        status_messages = {
            "started": "Emergency System Online",
            "stopped": "Emergency System Offline",
            "recording_completed": "Emergency Recording Saved",
        }
        
        title = status_messages.get(status, f"System: {status}")
        message = f"INFO: {title}"
        
        if details:
            for key, value in details.items():
                message += f"\n{key}: {value}"
        
        return self.send_message(message)
