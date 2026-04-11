"""
Standalone Panic Button Script
===============================

Monitors a push button on GPIO 13 & 14 and sends an emergency SMS
via Twilio when the button is pressed twice within a short window.

Runs independently from the main emergency system.

Wiring:
  - Button pin 1 -> GPIO 13 (BCM)
  - Button pin 2 -> GPIO 14 (BCM) / GND
"""

import time
import sys

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("ERROR: RPi.GPIO not available. This script must run on a Raspberry Pi.")
    sys.exit(1)

from config import Config
from communication import TwilioSMS, SupabaseClient
from utils import setup_logging

# --- Configuration ---
BUTTON_PIN = 27          # GPIO 27 (BCM) = physical pin 13
DOUBLE_PRESS_WINDOW = 1.0  # Max seconds between two presses
DEBOUNCE_MS = 200        # Debounce time in milliseconds
COOLDOWN = 30            # Seconds before another alert can be sent

# Hardcoded location
LAT = 18.4866
LON = 73.8163
MAPS_LINK = f"https://maps.google.com/maps?q={LAT:.6f},{LON:.6f}"


def setup_gpio():
    """Configure GPIO for push button input."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def send_emergency_sms(sms_client, logger):
    """Send the emergency SMS with location."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    message = (
        f"EMERGENCY - Panic Button\n"
        f"Time: {timestamp}\n"
        f"Manual emergency trigger pressed.\n"
        f"\n"
        f"GPS Location: {LAT:.6f}, {LON:.6f}\n"
        f"Map: {MAPS_LINK}\n"
        f"\n"
        f"IMMEDIATE ATTENTION REQUIRED"
    )

    success = sms_client.send_message(message)
    if success:
        logger.info("Emergency SMS sent successfully")
    else:
        logger.error("Failed to send emergency SMS")
    return success


def main():
    """Main loop: wait for double-press, then send alert."""
    # Setup
    config = Config.load_from_env()
    logger = setup_logging("button.log")
    logger.info("Panic button script starting...")

    # Fetch contacts from Supabase (fall back to default)
    emergency_contacts = [config.DEFAULT_EMERGENCY_PHONE]
    try:
        supabase = SupabaseClient(config.SUPABASE_URL, config.SUPABASE_KEY, logger)
        data = supabase.fetch_all()
        if data["contacts"]:
            emergency_contacts = data["contacts"]
            logger.info(f"Loaded {len(emergency_contacts)} contacts from Supabase")
        else:
            logger.warning("No contacts from Supabase, using default")
    except Exception as e:
        logger.warning(f"Supabase unavailable, using default contact: {e}")

    # Initialize Twilio
    sms_client = TwilioSMS(
        config.TWILIO_ACCOUNT_SID,
        config.TWILIO_AUTH_TOKEN,
        config.TWILIO_PHONE,
        emergency_contacts,
        logger
    )

    # Setup GPIO
    setup_gpio()

    print("=" * 50)
    print("PANIC BUTTON ACTIVE")
    print(f"Pin: GPIO {BUTTON_PIN}")
    print(f"Contacts: {len(emergency_contacts)}")
    print("Press button TWICE to trigger emergency alert")
    print("=" * 50)

    last_press_time = 0
    press_count = 0
    last_alert_time = 0

    try:
        while True:
            # Wait for button press (active LOW with pull-up)
            GPIO.wait_for_edge(BUTTON_PIN, GPIO.FALLING, bouncetime=DEBOUNCE_MS)

            now = time.time()

            # Reset count if too much time passed since last press
            if now - last_press_time > DOUBLE_PRESS_WINDOW:
                press_count = 0

            press_count += 1
            last_press_time = now

            if press_count == 1:
                logger.info("First press detected, waiting for second press...")
                print("First press detected. Press again to confirm.")

            elif press_count >= 2:
                # Check cooldown
                if now - last_alert_time < COOLDOWN:
                    remaining = int(COOLDOWN - (now - last_alert_time))
                    print(f"Cooldown active. Wait {remaining}s before next alert.")
                    logger.info(f"Alert blocked by cooldown ({remaining}s remaining)")
                    press_count = 0
                    continue

                print("DOUBLE PRESS CONFIRMED - Sending emergency alert!")
                logger.warning("Double press confirmed - triggering emergency SMS")
                send_emergency_sms(sms_client, logger)
                last_alert_time = time.time()
                press_count = 0

    except KeyboardInterrupt:
        print("\nShutting down panic button...")
        logger.info("Panic button script stopped by user")
    finally:
        GPIO.cleanup()
        logger.info("GPIO cleaned up")


if __name__ == "__main__":
    main()
