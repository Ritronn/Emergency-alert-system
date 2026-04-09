# Emergency Assistance System for Raspberry Pi

A comprehensive emergency detection and response system that provides multiple ways to trigger emergency alerts and automatically records evidence.

## Features

- **Voice-Activated Emergency**: Say "help help help" 3 times to trigger (VOSK offline recognition)
- **Fall Detection**: Automatic detection using MPU6050 gyroscope/accelerometer
- **30-Second Video Recording**: Automatic video capture during emergencies
- **Telegram Alerts**: Real-time notifications with location and status
- **Confirmation System**: 10-second timer to prevent false alarms
- **Offline Operation**: Works without internet (except for sending alerts)
- **High Accuracy**: VOSK speech recognition (much better than PocketSphinx)

## Hardware Requirements

### Core Components
- **Raspberry Pi 4B** (8GB RAM recommended)
- **MicroSD card** (32GB+ recommended)
- **Power supply** (official Raspberry Pi power adapter)

### Sensors and Modules
- **USB Camera**: Any USB webcam or Raspberry Pi Camera Module
- **USB Microphone**: For voice detection (VOSK offline recognition)
- **MPU6050**: Gyroscope/accelerometer for fall detection (I2C)

### Wiring Connections

```
GPIO Connections (BCM numbering):
┌─────────────────────────────────────┐
│ Component        │ GPIO Pin         │
├─────────────────────────────────────┤
│ MPU6050 SDA     │ GPIO 2 (I2C)      │
│ MPU6050 SCL     │ GPIO 3 (I2C)      │
└─────────────────────────────────────┘

Power Connections:
• 3.3V: MPU6050 VCC
• GND: All components ground
```

## Installation

### 1. Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Enable I2C and Camera
sudo raspi-config
# Navigate to Interface Options > I2C > Enable
# Navigate to Interface Options > Camera > Enable
# Reboot when prompted
```

### 2. Install the System

```bash
# Clone or download the project files
# Make installation script executable (on Raspberry Pi)
chmod +x install.sh

# Run installation script
./install.sh
```

### 3. Configure Settings

Edit `config.py` and update your Telegram credentials:

```python
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"
```

### 4. Get Telegram Bot Credentials

1. **Create Bot**: Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token to `TELEGRAM_BOT_TOKEN`
4. **Get Chat ID**: Start a chat with your bot and send any message
5. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
6. Copy your chat ID to `TELEGRAM_CHAT_ID`

## Usage

### Starting the System

**Manual start:**
```bash
source emergency_env/bin/activate
python emergency_system.py
```

**Auto-start service:**
```bash
sudo systemctl enable emergency-system
sudo systemctl start emergency-system
```

### Emergency Triggers

1. **Voice Commands**: Say "help help help" clearly (3 times)
2. **Fall Detection**: System automatically detects falls

### Confirmation Process

- **Voice/Fall Detection**: 10-second confirmation timer
  - Say "yes" to confirm emergency
  - Voice alerts cancelled if no confirmation
  - Fall alerts auto-confirm (user may be unconscious)

## System Status

**Check system status:**
```bash
sudo systemctl status emergency-system
```

**View live logs:**
```bash
tail -f emergency_system.log
# or
sudo journalctl -u emergency-system -f
```

**Test hardware:**
```bash
# Test I2C devices
sudo i2cdetect -y 1

# Test camera
raspistill -o test.jpg

# Test GPIO access
ls -l /dev/gpiomem
```

## Configuration

### Detection Thresholds

Edit `config.py` to adjust sensitivity:

```python
# Voice detection
HELP_COUNT_REQUIRED = 3        # Number of "help" needed
CONFIRMATION_TIMEOUT = 10      # Confirmation time (seconds)

# Fall detection
FALL_THRESHOLD = 2.5          # G-force threshold
FALL_TIME_WINDOW = 0.5        # Detection window (seconds)
```

### Hardware Pins

Adjust GPIO pin assignments in `config.py`:

```python
# Hardware pins (GPIO BCM numbering)
BUZZER = 19  # Optional buzzer for audio feedback
```

## Project Structure

```
emergency_system/
├── emergency_system.py          # Main application (English voice)
├── emergency_system_hindi.py    # Hindi version (for future use)
├── config.py                    # Configuration settings
├── requirements.txt             # Python dependencies (VOSK-based)
├── install.sh                   # Installation script
├── README.md                    # This file
├── sensors/                     # Sensor modules
│   ├── __init__.py
│   ├── voice_detector.py       # English voice recognition (VOSK)
│   ├── voice_detector_hindi.py # Hindi voice recognition (VOSK)
│   └── fall_detector.py        # Fall detection
├── communication/               # Communication modules
│   ├── __init__.py
│   └── telegram_bot.py         # Telegram integration
├── recording/                   # Recording modules
│   ├── __init__.py
│   └── camera_recorder.py      # Video recording
├── utils/                       # Utility modules
│   ├── __init__.py
│   └── logger.py               # Logging utilities
├── vosk-model-small-en-us-0.15/ # English VOSK model (auto-downloaded)
├── vosk-model-small-hi-0.22/   # Hindi VOSK model (for future use)
└── recordings/                  # Video recordings (auto-created)
```

## Troubleshooting

### Common Issues

**Permission denied errors:**
```bash
sudo usermod -a -G dialout,i2c,gpio,video $USER
# Then logout and login again
```

**Camera not working:**
```bash
# Check if camera is enabled
vcgencmd get_camera
# Should show: supported=1 detected=1

# Test camera
raspistill -o test.jpg
```

**I2C sensor not detected:**
```bash
# Check I2C is enabled
sudo raspi-config

# Check connected devices
sudo i2cdetect -y 1
# Should show device at address 0x68 (MPU6050)
```

**Audio issues:**
```bash
# Test microphone
arecord -l

# Test recording
arecord -d 5 test.wav

# Test playback
aplay test.wav
```

### Logs and Debugging

**System logs:**
```bash
tail -f emergency_system.log
```

**Service logs:**
```bash
sudo journalctl -u emergency-system -f
```

**Test individual components:**
```bash
# Test voice detection
python -c "from sensors import VoiceDetector; print('Voice detection available')"

# Test camera
python -c "import cv2; print('Camera available:', cv2.VideoCapture(0).isOpened())"
```

## Safety and Legal Considerations

- This system supplements, not replaces, professional emergency services
- Test the system regularly to ensure proper operation
- Ensure emergency contacts are aware they may receive alerts
- Consider local laws regarding recording and privacy
- Keep the system charged and connected to power
- Regularly backup important data and configurations

## Modular vs Single File Approach

**Why Modular Approach is Better:**

1. **Maintainability**: Easy to debug and update individual features
2. **Reusability**: Components can be used in other projects
3. **Testing**: Each module can be tested independently
4. **Collaboration**: Multiple people can work on different features
5. **Performance**: Only load what you need
6. **Organization**: Clear separation of concerns

**vs Single File Approach:**
- Single file becomes unwieldy (1000+ lines)
- Hard to debug when everything is mixed together
- Difficult to reuse components
- Testing becomes complex
- Version control conflicts when multiple people edit

## Future Enhancements

- **GPS Integration**: Add location tracking
- **SMS Alerts**: Backup communication method
- **Web Dashboard**: Remote monitoring interface
- **Mobile App**: Dedicated smartphone app
- **Multiple Sensors**: Additional fall detection methods
- **AI Enhancement**: Machine learning for better detection

## Contributing

This is an open-source project. Contributions welcome for:
- Additional sensor support
- New notification methods
- Improved detection algorithms
- Bug fixes and optimizations

## License

This project is provided as-is for educational and personal use. Use at your own risk.

---

**Remember**: This system is designed to help in emergencies, but always ensure you have proper emergency contacts and procedures in place!