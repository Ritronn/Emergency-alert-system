#!/bin/bash

# Emergency Assistance System Installation Script for Raspberry Pi
# This script installs all dependencies and configures the system

set -e  # Exit on any error

echo "=========================================="
echo "Emergency Assistance System Installer"
echo "=========================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "WARNING: This doesn't appear to be a Raspberry Pi"
    echo "   Some features may not work properly"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

echo "Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    portaudio19-dev \
    python3-pyaudio \
    python3-opencv \
    i2c-tools \
    python3-smbus \
    libatlas-base-dev \
    git \
    curl

echo "Enabling I2C and Camera interfaces..."
# Enable I2C
if ! grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
fi

# Enable Camera
if ! grep -q "start_x=1" /boot/config.txt; then
    echo "start_x=1" | sudo tee -a /boot/config.txt
fi

# Increase GPU memory for camera
if ! grep -q "gpu_mem=128" /boot/config.txt; then
    echo "gpu_mem=128" | sudo tee -a /boot/config.txt
fi

# Add user to required groups
echo "Adding user to required groups..."
sudo usermod -a -G dialout,i2c,gpio,video $USER

echo "Creating Python virtual environment..."
python3 -m venv emergency_env
source emergency_env/bin/activate

echo "Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Creating required directories..."
mkdir -p recordings
mkdir -p logs

echo "Setting up permissions..."
# Make sure the user can access GPIO
sudo chmod 666 /dev/gpiomem 2>/dev/null || true

# Make sure the user can access I2C
sudo chmod 666 /dev/i2c-* 2>/dev/null || true

echo "Creating systemd service..."
cat > emergency-system.service << EOF
[Unit]
Description=Emergency Assistance System
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/emergency_env/bin
ExecStart=$(pwd)/emergency_env/bin/python $(pwd)/emergency_system.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv emergency-system.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "Testing hardware connections..."

echo "  • Testing I2C bus..."
if command -v i2cdetect >/dev/null 2>&1; then
    echo "    I2C devices found:"
    sudo i2cdetect -y 1 | grep -v "^     " | grep -v "^--" || echo "    No I2C devices detected"
else
    echo "    i2cdetect not available"
fi

echo "  • Testing camera..."
if command -v vcgencmd >/dev/null 2>&1; then
    camera_status=$(vcgencmd get_camera)
    echo "    Camera status: $camera_status"
else
    echo "    vcgencmd not available (not on Raspberry Pi)"
fi

echo "  • Testing GPIO access..."
if [ -c /dev/gpiomem ]; then
    echo "    GPIO access: Available"
else
    echo "    GPIO access: Not available"
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo ""
echo "1. Configure your settings:"
echo "   Edit the config.py file and update:"
echo "   - TELEGRAM_BOT_TOKEN"
echo "   - TELEGRAM_CHAT_ID"
echo "   - Hardware pin assignments (if different)"
echo ""
echo "2. Connect your hardware:"
echo "   - USB Camera"
echo "   - USB Microphone (for VOSK voice recognition)"
echo "   - MPU6050 sensor (I2C: SDA=GPIO2, SCL=GPIO3)"
echo "   - Ultrasonic sensor (TRIG=GPIO17, ECHO=GPIO27)"
echo ""
echo "3. Test the system:"
echo "   source emergency_env/bin/activate"
echo "   python emergency_system.py"
echo ""
echo "4. Enable auto-start (optional):"
echo "   sudo systemctl enable emergency-system"
echo "   sudo systemctl start emergency-system"
echo ""
echo "5. Get Telegram credentials:"
echo "   - Message @BotFather on Telegram"
echo "   - Send /newbot and follow instructions"
echo "   - Get your chat ID from @userinfobot"
echo ""
echo "IMPORTANT: Reboot required for interface changes!"
echo "   sudo reboot"
echo ""
echo "For troubleshooting, check the logs:"
echo "   tail -f emergency_system.log"
echo "   sudo journalctl -u emergency-system -f"
echo ""
echo "=========================================="