"""
Quick Twilio SMS Test Script
Tests sending an SMS via Twilio API to verify credentials work.
"""

from twilio.rest import Client

# Twilio credentials
ACCOUNT_SID = "YOUR_TWILIO_ACCOUNT_SID"
AUTH_TOKEN = "YOUR_TWILIO_AUTH_TOKEN"
TWILIO_PHONE = "+16626322267"

# ---- CHANGE THIS to your personal phone number ----
TO_PHONE = "+917498683368"

def test_send_sms():
    """Send a test SMS message."""
    try:
        client = Client(ACCOUNT_SID, AUTH_TOKEN)

        message = client.messages.create(
            body="EMERGENCY ALERT - Emergency System Test - Twilio SMS is working!",
            from_=TWILIO_PHONE,
            to=TO_PHONE,
        )

        print(f"SMS sent successfully!")
        print(f"   Message SID: {message.sid}")
        print(f"   Status: {message.status}")
        print(f"   From: {TWILIO_PHONE}")
        print(f"   To: {TO_PHONE}")

    except Exception as e:
        print(f"Failed to send SMS: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("  Twilio SMS Test")
    print("=" * 50)
    test_send_sms()
