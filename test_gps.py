#!/usr/bin/env python3
"""
GPS Module Test Script for GY-GPS6MV2
======================================

Hardware Setup:
  - GPS Module TX  -> RPi Pin 10 (GPIO 15 / RXD)
  - GPS Module RX  -> RPi Pin 8  (GPIO 14 / TXD)
  - GPS Module VCC -> RPi 3.3V or 5V
  - GPS Module GND -> RPi GND

Prerequisites:
  1. Enable UART on Raspberry Pi:
     - sudo raspi-config -> Interface Options -> Serial Port
     - Disable serial login shell: YES
     - Enable serial port hardware: YES
     - Reboot
  
  2. Install pynmea2:
     pip install pynmea2 pyserial

Usage:
  python3 test_gps.py
"""

import serial
import time
import sys

try:
    import pynmea2
except ImportError:
    print("ERROR: pynmea2 not installed. Run: pip install pynmea2")
    sys.exit(1)


# ── Configuration ────────────────────────────────────────────────────────────
GPS_SERIAL_PORT = "/dev/serial0"   # Default UART on RPi (pins 8 & 10)
GPS_BAUD_RATE   = 9600             # GY-GPS6MV2 default baud rate
GPS_TIMEOUT     = 1                # Serial read timeout in seconds
MAX_ATTEMPTS    = 120              # Max seconds to wait for GPS fix
# ─────────────────────────────────────────────────────────────────────────────


def test_serial_connection():
    """Test 1: Verify serial port is accessible"""
    print("=" * 60)
    print("TEST 1: Serial Port Connection")
    print("=" * 60)
    
    try:
        ser = serial.Serial(
            port=GPS_SERIAL_PORT,
            baudrate=GPS_BAUD_RATE,
            timeout=GPS_TIMEOUT
        )
        print(f"  ✓ Serial port opened: {GPS_SERIAL_PORT}")
        print(f"  ✓ Baud rate: {GPS_BAUD_RATE}")
        print(f"  ✓ Port is open: {ser.is_open}")
        ser.close()
        return True
    except serial.SerialException as e:
        print(f"  ✗ Failed to open serial port: {e}")
        print()
        print("  Troubleshooting:")
        print("    1. Enable UART: sudo raspi-config -> Interface Options -> Serial Port")
        print("    2. Disable serial login shell, enable serial hardware")
        print("    3. Check wiring: GPS TX -> RPi Pin 10, GPS RX -> RPi Pin 8")
        print("    4. Try: ls -la /dev/serial* /dev/ttyS0 /dev/ttyAMA0")
        print("    5. Add your user to dialout group: sudo usermod -aG dialout $USER")
        return False


def test_raw_data():
    """Test 2: Read raw NMEA data from GPS"""
    print()
    print("=" * 60)
    print("TEST 2: Raw NMEA Data")
    print("=" * 60)
    print("  Reading raw data for 10 seconds...")
    print()
    
    try:
        ser = serial.Serial(
            port=GPS_SERIAL_PORT,
            baudrate=GPS_BAUD_RATE,
            timeout=GPS_TIMEOUT
        )
        
        lines_read = 0
        start_time = time.time()
        
        while time.time() - start_time < 10:
            line = ser.readline().decode('ascii', errors='replace').strip()
            if line:
                lines_read += 1
                if lines_read <= 10:  # Show first 10 lines
                    print(f"  [{lines_read:02d}] {line}")
        
        ser.close()
        
        if lines_read > 0:
            print(f"\n  ✓ Received {lines_read} NMEA sentences in 10 seconds")
            return True
        else:
            print("  ✗ No data received from GPS module")
            print()
            print("  Troubleshooting:")
            print("    1. Check if GPS module LED is blinking (indicates power)")
            print("    2. Verify wiring connections")
            print("    3. GPS module needs clear sky view for satellite lock")
            return False
            
    except Exception as e:
        print(f"  ✗ Error reading data: {e}")
        return False


def test_gps_parsing():
    """Test 3: Parse NMEA sentences and extract GPS data"""
    print()
    print("=" * 60)
    print("TEST 3: NMEA Parsing")
    print("=" * 60)
    print("  Parsing NMEA sentences for 15 seconds...")
    print()
    
    try:
        ser = serial.Serial(
            port=GPS_SERIAL_PORT,
            baudrate=GPS_BAUD_RATE,
            timeout=GPS_TIMEOUT
        )
        
        sentence_types = {}
        start_time = time.time()
        
        while time.time() - start_time < 15:
            line = ser.readline().decode('ascii', errors='replace').strip()
            if line.startswith('$'):
                try:
                    msg = pynmea2.parse(line)
                    msg_type = msg.sentence_type
                    sentence_types[msg_type] = sentence_types.get(msg_type, 0) + 1
                except pynmea2.ParseError:
                    pass
        
        ser.close()
        
        if sentence_types:
            print("  NMEA Sentence Types Received:")
            for stype, count in sorted(sentence_types.items()):
                description = {
                    'GGA': 'GPS Fix Data (position, altitude, satellites)',
                    'GSA': 'GPS DOP and Active Satellites',
                    'GSV': 'Satellites in View',
                    'RMC': 'Recommended Minimum (position, velocity, time)',
                    'VTG': 'Track Made Good and Ground Speed',
                    'GLL': 'Geographic Position (lat/lon)',
                }.get(stype, 'Other')
                print(f"    {stype}: {count:3d} sentences  ({description})")
            print(f"\n  ✓ Successfully parsed {sum(sentence_types.values())} NMEA sentences")
            return True
        else:
            print("  ✗ No parseable NMEA sentences found")
            return False
            
    except Exception as e:
        print(f"  ✗ Error parsing data: {e}")
        return False


def test_gps_fix():
    """Test 4: Wait for GPS fix and get coordinates"""
    print()
    print("=" * 60)
    print("TEST 4: GPS Fix & Location Coordinates")
    print("=" * 60)
    print(f"  Waiting for GPS fix (max {MAX_ATTEMPTS} seconds)...")
    print("  NOTE: GPS needs clear sky view. First fix can take 1-5 minutes.")
    print()
    
    try:
        ser = serial.Serial(
            port=GPS_SERIAL_PORT,
            baudrate=GPS_BAUD_RATE,
            timeout=GPS_TIMEOUT
        )
        
        start_time = time.time()
        fix_found = False
        satellites_seen = 0
        
        while time.time() - start_time < MAX_ATTEMPTS:
            line = ser.readline().decode('ascii', errors='replace').strip()
            
            if not line.startswith('$'):
                continue
                
            try:
                msg = pynmea2.parse(line)
            except pynmea2.ParseError:
                continue
            
            # Check GGA for satellite count
            if msg.sentence_type == 'GGA':
                try:
                    satellites_seen = int(msg.num_sats) if msg.num_sats else 0
                except (ValueError, AttributeError):
                    satellites_seen = 0
                    
                elapsed = int(time.time() - start_time)
                sys.stdout.write(f"\r  Searching... Satellites: {satellites_seen} | Time: {elapsed}s   ")
                sys.stdout.flush()
            
            # Check RMC for valid fix
            if msg.sentence_type == 'RMC' and msg.status == 'A':
                latitude = msg.latitude
                longitude = msg.longitude
                speed_knots = msg.spd_over_grnd if msg.spd_over_grnd else 0
                timestamp = msg.timestamp
                date = msg.datestamp
                
                print(f"\n\n  ✓ GPS FIX ACQUIRED!")
                print(f"  ─────────────────────────────────────")
                print(f"  Latitude:    {latitude:.6f}°")
                print(f"  Longitude:   {longitude:.6f}°")
                print(f"  Speed:       {speed_knots} knots")
                print(f"  Satellites:  {satellites_seen}")
                print(f"  UTC Time:    {timestamp}")
                print(f"  UTC Date:    {date}")
                print(f"  ─────────────────────────────────────")
                print()
                
                # Generate Google Maps link
                maps_link = f"https://maps.google.com/maps?q={latitude},{longitude}"
                print(f"  📍 Google Maps Link:")
                print(f"     {maps_link}")
                print()
                
                # Generate emergency message format
                print(f"  📱 Sample Emergency Message:")
                print(f"     ──────────────────────────────────")
                print(f"     🚨 EMERGENCY ALERT!")
                print(f"     📍 Location: {latitude:.6f}, {longitude:.6f}")
                print(f"     🗺️  Map: {maps_link}")
                print(f"     🕐 Time: {timestamp}")
                print(f"     ──────────────────────────────────")
                
                fix_found = True
                break
            
            # Also check GGA for fix
            if msg.sentence_type == 'GGA' and msg.gps_qual > 0:
                latitude = msg.latitude
                longitude = msg.longitude
                altitude = msg.altitude if msg.altitude else 'N/A'
                
                print(f"\n\n  ✓ GPS FIX ACQUIRED (via GGA)!")
                print(f"  ─────────────────────────────────────")
                print(f"  Latitude:    {latitude:.6f}°")
                print(f"  Longitude:   {longitude:.6f}°")
                print(f"  Altitude:    {altitude} {msg.altitude_units if msg.altitude_units else 'm'}")
                print(f"  Satellites:  {satellites_seen}")
                print(f"  Fix Quality: {msg.gps_qual}")
                print(f"  ─────────────────────────────────────")
                print()
                
                # Generate Google Maps link
                maps_link = f"https://maps.google.com/maps?q={latitude},{longitude}"
                print(f"  📍 Google Maps Link:")
                print(f"     {maps_link}")
                print()
                
                # Generate emergency message format
                print(f"  📱 Sample Emergency Message:")
                print(f"     ──────────────────────────────────")
                print(f"     🚨 EMERGENCY ALERT!")
                print(f"     📍 Location: {latitude:.6f}, {longitude:.6f}")
                print(f"     🗺️  Map: {maps_link}")
                print(f"     📡 Satellites: {satellites_seen}")
                print(f"     ──────────────────────────────────")
                
                fix_found = True
                break
        
        ser.close()
        
        if not fix_found:
            print(f"\n\n  ✗ No GPS fix obtained in {MAX_ATTEMPTS} seconds")
            print(f"    Satellites visible: {satellites_seen}")
            print()
            print("  Troubleshooting:")
            print("    1. Move to an open area with clear sky view")
            print("    2. Wait longer - cold start can take up to 12 minutes")
            print("    3. Ensure GPS antenna is connected and facing up")
            print("    4. Check that the GPS module's LED is blinking")
        
        return fix_found
        
    except Exception as e:
        print(f"  ✗ Error getting GPS fix: {e}")
        return False


def test_continuous_tracking():
    """Test 5: Continuous GPS tracking for 30 seconds"""
    print()
    print("=" * 60)
    print("TEST 5: Continuous GPS Tracking (30 seconds)")
    print("=" * 60)
    print("  Tracking position updates...")
    print()
    
    try:
        ser = serial.Serial(
            port=GPS_SERIAL_PORT,
            baudrate=GPS_BAUD_RATE,
            timeout=GPS_TIMEOUT
        )
        
        start_time = time.time()
        fix_count = 0
        
        print(f"  {'#':>3} | {'Latitude':>12} | {'Longitude':>12} | {'Sats':>4} | {'Speed':>8} | Google Maps Link")
        print(f"  {'─'*3}─┼─{'─'*12}─┼─{'─'*12}─┼─{'─'*4}─┼─{'─'*8}─┼─{'─'*40}")
        
        while time.time() - start_time < 30:
            line = ser.readline().decode('ascii', errors='replace').strip()
            
            if not line.startswith('$'):
                continue
                
            try:
                msg = pynmea2.parse(line)
            except pynmea2.ParseError:
                continue
            
            if msg.sentence_type == 'RMC' and msg.status == 'A':
                fix_count += 1
                lat = msg.latitude
                lon = msg.longitude
                speed = msg.spd_over_grnd if msg.spd_over_grnd else 0.0
                maps_link = f"https://maps.google.com/maps?q={lat},{lon}"
                
                print(f"  {fix_count:3d} | {lat:12.6f} | {lon:12.6f} | {'--':>4} | {speed:6.1f}kn | {maps_link}")
        
        ser.close()
        
        if fix_count > 0:
            print(f"\n  ✓ Received {fix_count} position fixes in 30 seconds")
            return True
        else:
            print(f"\n  ✗ No position fixes received in 30 seconds")
            return False
            
    except Exception as e:
        print(f"  ✗ Error during tracking: {e}")
        return False


def main():
    """Run all GPS tests"""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       GY-GPS6MV2 Module Test Suite for RPi             ║")
    print("║                                                         ║")
    print("║  Wiring:  GPS TX -> RPi Pin 10 (RXD)                   ║")
    print("║           GPS RX -> RPi Pin 8  (TXD)                   ║")
    print("║           GPS VCC -> RPi 3.3V/5V                       ║")
    print("║           GPS GND -> RPi GND                           ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    
    results = {}
    
    # Test 1: Serial connection
    results['Serial Connection'] = test_serial_connection()
    if not results['Serial Connection']:
        print("\n  ⚠ Cannot continue without serial connection. Fix and retry.")
        print_summary(results)
        return
    
    # Test 2: Raw data
    results['Raw NMEA Data'] = test_raw_data()
    if not results['Raw NMEA Data']:
        print("\n  ⚠ No data from GPS. Check wiring and power.")
        print_summary(results)
        return
    
    # Test 3: NMEA parsing
    results['NMEA Parsing'] = test_gps_parsing()
    
    # Test 4: GPS fix
    results['GPS Fix'] = test_gps_fix()
    
    # Test 5: Continuous tracking (only if fix was obtained)
    if results['GPS Fix']:
        results['Continuous Tracking'] = test_continuous_tracking()
    else:
        results['Continuous Tracking'] = False
        print("\n  ⚠ Skipping continuous tracking (no GPS fix)")
    
    # Print summary
    print_summary(results)


def print_summary(results):
    """Print test summary"""
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}  {test_name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("  ✓ ALL TESTS PASSED - GPS module is working correctly!")
        print("    The GPS location link can now be included in emergency messages.")
    else:
        print("  ⚠ Some tests failed. Check the details above for troubleshooting.")
    print("=" * 60)


if __name__ == "__main__":
    main()
