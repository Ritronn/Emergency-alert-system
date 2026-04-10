
"""
Step Counter & Activity Tracker for Raspberry Pi
Uses QYF0s900 accelerometer with ADS1115 ADC
Compatible with existing hardware setup
"""

import time
import math
import numpy as np
from datetime import datetime
from collections import deque
import json
import os
import logging
import Adafruit_ADS1x15

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QYF0900Sensor:
    """Driver for QYF0900 accelerometer using ADS1115 ADC"""
    
    def __init__(self, address=0x48, gain=1):
        self.adc = Adafruit_ADS1x15.ADS1115(address=address)
        self.gain = gain
        self.VALMAX = 32767
        
        # Calibration offsets
        self.baseline_offset = {'x': 0, 'y': 0, 'z': 0}
        self.is_calibrated = False
        
        # Sensitivity parameters
        self.sensitivity = self.VALMAX / 4.096  # ADC units per volt
        self.g_per_volt = 2.0  # 0.5V per g means 2g per volt
        
    def calibrate(self, samples=50):
        """Calibrate the sensor to get baseline offsets"""
        logger.info("Calibrating sensor... Keep device still.")
        x_readings, y_readings, z_readings = [], [], []
        
        for _ in range(samples):
            x_raw = self.adc.read_adc(0, gain=self.gain)
            y_raw = self.adc.read_adc(1, gain=self.gain)
            z_raw = self.adc.read_adc(2, gain=self.gain)
            
            x_readings.append(x_raw)
            y_readings.append(y_raw)
            z_readings.append(z_raw)
            time.sleep(0.02)
        
        self.baseline_offset['x'] = np.mean(x_readings)
        self.baseline_offset['y'] = np.mean(y_readings)
        self.baseline_offset['z'] = np.mean(z_readings)
        
        self.is_calibrated = True
        logger.info(f"Calibration complete. Offsets: X={self.baseline_offset['x']:.0f}, "
                   f"Y={self.baseline_offset['y']:.0f}, Z={self.baseline_offset['z']:.0f}")
    
    def get_accel_data(self):
        """Read accelerometer and return g-forces"""
        if not self.is_calibrated:
            logger.warning("Sensor not calibrated. Run calibrate() first.")
            return {'x': 0, 'y': 0, 'z': 1.0}
        
        try:
            x_raw = self.adc.read_adc(0, gain=self.gain)
            y_raw = self.adc.read_adc(1, gain=self.gain)
            z_raw = self.adc.read_adc(2, gain=self.gain)
            
            g_x = ((x_raw - self.baseline_offset['x']) / self.sensitivity) * self.g_per_volt
            g_y = ((y_raw - self.baseline_offset['y']) / self.sensitivity) * self.g_per_volt
            g_z = ((z_raw - self.baseline_offset['z']) / self.sensitivity) * self.g_per_volt + 1.0
            
            return {'x': g_x, 'y': g_y, 'z': g_z}
            
        except Exception as e:
            logger.error(f"Error reading accelerometer: {str(e)}")
            return {'x': 0, 'y': 0, 'z': 1.0}


class ActivityTracker:
    """Step counter and activity classifier"""
    
    def __init__(self, sensor, sample_rate=25):
        self.sensor = sensor
        self.sample_rate = sample_rate  # Hz (matching your fall detection rate)
        self.sample_interval = 1.0 / sample_rate
        
        # Step detection parameters (tuned for QYF0900)
        self.step_threshold = 0.3  # Lower threshold for analog accelerometer
        self.step_max_threshold = 3.0  # Upper threshold to filter out extreme movements
        self.step_cooldown = 0.4  # seconds between steps
        self.last_step_time = 0
        self.steps_today = 0
        self.total_steps = 0
        
        # Peak detection for better accuracy
        self.accel_history = deque(maxlen=5)
        self.last_peak_value = 0
        
        # Activity classification parameters
        self.window_size = 50  # samples for activity detection (2 seconds at 25Hz)
        self.accel_buffer = deque(maxlen=self.window_size)
        
        # Current activity state
        self.current_activity = "stationary"
        self.activity_start_time = time.time()
        
        # Activity durations (seconds)
        self.activity_durations = {
            'walking': 0,
            'running': 0,
            'stationary': 0,
            'active': 0  # General movement
        }
        
        # User profile for calorie calculation
        self.user_weight_kg = 70
        self.user_height_cm = 170
        self.user_age = 30
        self.user_gender = 'M'
        
        # Data storage
        self.data_file = 'activity_data.json'
        self.daily_stats_file = 'daily_stats.json'
        self.load_data()
        
    def load_data(self):
        """Load saved activity data"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.total_steps = data.get('total_steps', 0)
                    self.steps_today = data.get('steps_today', 0)
                    self.activity_durations = data.get('activity_durations', self.activity_durations)
                    last_date = data.get('last_date', '')
                    
                    # Reset daily steps if it's a new day
                    today = datetime.now().strftime('%Y-%m-%d')
                    if last_date != today:
                        # Archive yesterday's data
                        self.archive_daily_stats(last_date)
                        self.steps_today = 0
                        self.activity_durations = {k: 0 for k in self.activity_durations}
                        
            except Exception as e:
                logger.error(f"Error loading data: {e}")
    
    def archive_daily_stats(self, date):
        """Archive previous day's statistics"""
        if not date:
            return
            
        try:
            archive = {}
            if os.path.exists(self.daily_stats_file):
                with open(self.daily_stats_file, 'r') as f:
                    archive = json.load(f)
            
            archive[date] = {
                'steps': self.steps_today,
                'activity_durations': self.activity_durations,
                'calories': round(self.calculate_calories(), 1),
                'distance_km': round(self.steps_today * 0.0008, 2)
            }
            
            # Keep only last 30 days
            if len(archive) > 30:
                dates = sorted(archive.keys())
                archive = {d: archive[d] for d in dates[-30:]}
            
            with open(self.daily_stats_file, 'w') as f:
                json.dump(archive, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error archiving data: {e}")
    
    def save_data(self):
        """Save activity data"""
        data = {
            'total_steps': self.total_steps,
            'steps_today': self.steps_today,
            'activity_durations': self.activity_durations,
            'last_date': datetime.now().strftime('%Y-%m-%d')
        }
        try:
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def set_user_profile(self, weight_kg, height_cm, age, gender):
        """Set user profile for accurate calorie calculation"""
        self.user_weight_kg = weight_kg
        self.user_height_cm = height_cm
        self.user_age = age
        self.user_gender = gender
        logger.info(f"User profile updated: {weight_kg}kg, {height_cm}cm, {age}y, {gender}")
    
    def calculate_magnitude(self, accel):
        """Calculate acceleration magnitude"""
        return math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
    
    def detect_step_improved(self, accel):
        """Improved step detection using peak detection algorithm"""
        current_time = time.time()
        
        # Calculate magnitude relative to gravity (subtract 1g)
        magnitude = self.calculate_magnitude(accel)
        accel_relative = abs(magnitude - 1.0)
        
        # Add to history
        self.accel_history.append(accel_relative)
        
        if len(self.accel_history) < 5:
            return False
        
        # Check if current value is a peak
        history_list = list(self.accel_history)
        current_val = history_list[2]  # Middle value
        
        # Peak detection: current value is highest in window
        is_peak = (current_val > history_list[0] and 
                   current_val > history_list[1] and
                   current_val > history_list[3] and
                   current_val > history_list[4])
        
        # Check thresholds and cooldown
        if (is_peak and 
            self.step_threshold < current_val < self.step_max_threshold and
            (current_time - self.last_step_time) > self.step_cooldown):
            
            self.last_step_time = current_time
            self.steps_today += 1
            self.total_steps += 1
            self.last_peak_value = current_val
            return True
            
        return False
    
    def classify_activity(self):
        """Classify current activity based on sensor data"""
        if len(self.accel_buffer) < self.window_size:
            return "initializing"
        
        # Convert buffer to numpy array
        accel_data = np.array([[d['x'], d['y'], d['z']] for d in self.accel_buffer])
        
        # Calculate features
        accel_magnitude = np.linalg.norm(accel_data, axis=1)
        accel_variance = np.var(accel_magnitude)
        accel_std = np.std(accel_magnitude)
        accel_mean = np.mean(accel_magnitude)
        
        # Calculate vertical component variance (walking has rhythmic vertical motion)
        z_variance = np.var(accel_data[:, 2])
        
        # Activity classification (tuned for QYF0900 sensitivity)
        if accel_variance < 0.02 and accel_std < 0.15:
            activity = "stationary"
        
        elif accel_variance > 0.4 and accel_std > 0.4:
            activity = "running"
        
        elif 0.08 < accel_variance < 0.4 and z_variance > 0.05:
            activity = "walking"
        
        elif accel_variance > 0.05:
            activity = "active"
        
        else:
            activity = "stationary"
        
        return activity
    
    def update_activity_duration(self, new_activity):
        """Update activity duration tracking"""
        current_time = time.time()
        duration = current_time - self.activity_start_time
        
        if new_activity != self.current_activity:
            # Save duration of previous activity
            self.activity_durations[self.current_activity] += duration
            self.current_activity = new_activity
            self.activity_start_time = current_time
    
    def calculate_calories(self):
        """Calculate calories burned based on activity"""
        # MET (Metabolic Equivalent) values for activities
        met_values = {
            'stationary': 1.3,
            'walking': 3.5,
            'running': 9.0,
            'active': 2.5
        }
        
        total_calories = 0
        
        for activity, duration_sec in self.activity_durations.items():
            duration_hours = duration_sec / 3600.0
            met = met_values.get(activity, 1.0)
            
            # Calories = MET × weight(kg) × duration(hours)
            calories = met * self.user_weight_kg * duration_hours
            total_calories += calories
        
        return total_calories
    
    def get_statistics(self):
        """Get current statistics"""
        stats = {
            'steps_today': self.steps_today,
            'total_steps': self.total_steps,
            'current_activity': self.current_activity,
            'activity_durations_minutes': {
                k: round(v / 60, 1) for k, v in self.activity_durations.items()
            },
            'calories_burned': round(self.calculate_calories(), 1),
            'distance_km': round(self.steps_today * 0.0008, 2),  # Average step = 0.8m
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return stats
    
    def get_weekly_summary(self):
        """Get weekly statistics from archived data"""
        if not os.path.exists(self.daily_stats_file):
            return None
        
        try:
            with open(self.daily_stats_file, 'r') as f:
                archive = json.load(f)
            
            # Get last 7 days
            dates = sorted(archive.keys())[-7:]
            
            total_steps = sum(archive[d]['steps'] for d in dates)
            total_distance = sum(archive[d]['distance_km'] for d in dates)
            total_calories = sum(archive[d]['calories'] for d in dates)
            
            return {
                'days': len(dates),
                'total_steps': total_steps,
                'avg_steps_per_day': round(total_steps / len(dates), 0),
                'total_distance_km': round(total_distance, 2),
                'total_calories': round(total_calories, 1),
                'daily_breakdown': {d: archive[d] for d in dates}
            }
        except Exception as e:
            logger.error(f"Error getting weekly summary: {e}")
            return None
    
    def run(self, duration_seconds=None):
        """Main tracking loop"""
        print("\n" + "="*60)
        print("   ACTIVITY TRACKER STARTED - QYF0900 ACCELEROMETER")
        print("="*60)
        print(f"User Profile: {self.user_weight_kg}kg, {self.user_height_cm}cm, "
              f"{self.user_age}y, {self.user_gender}")
        print(f"Sample Rate: {self.sample_rate}Hz")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        start_time = time.time()
        last_report_time = start_time
        last_save_time = start_time
        report_interval = 10  # Print stats every 10 seconds
        save_interval = 30  # Save data every 30 seconds
        
        try:
            while True:
                loop_start = time.time()
                
                # Read sensor data
                accel = self.sensor.get_accel_data()
                
                # Add to buffer
                self.accel_buffer.append(accel)
                
                # Detect steps
                if self.detect_step_improved(accel):
                    print(f"Step detected! Total today: {self.steps_today} "
                          f"(peak: {self.last_peak_value:.2f}g)")
                
                # Classify activity (when buffer is full)
                if len(self.accel_buffer) >= self.window_size:
                    new_activity = self.classify_activity()
                    self.update_activity_duration(new_activity)
                
                current_time = time.time()
                
                # Periodic reporting
                if current_time - last_report_time >= report_interval:
                    stats = self.get_statistics()
                    print("\n" + "="*60)
                    print(f"Timestamp: {stats['timestamp']}")
                    print(f"Steps Today: {stats['steps_today']} | Total: {stats['total_steps']}")
                    print(f"Current Activity: {stats['current_activity'].upper()}")
                    print(f"Distance: {stats['distance_km']} km")
                    print(f"Calories: {stats['calories_burned']} kcal")
                    print(f"\nActivity Duration (minutes):")
                    for activity, minutes in stats['activity_durations_minutes'].items():
                        if minutes > 0:
                            print(f"   {activity.capitalize():12s}: {minutes:6.1f} min")
                    print("="*60 + "\n")
                    
                    last_report_time = current_time
                
                # Periodic saving
                if current_time - last_save_time >= save_interval:
                    self.save_data()
                    last_save_time = current_time
                
                # Check duration limit
                if duration_seconds and (current_time - start_time) >= duration_seconds:
                    break
                
                # Maintain sample rate
                elapsed = time.time() - loop_start
                if elapsed < self.sample_interval:
                    time.sleep(self.sample_interval - elapsed)
                    
        except KeyboardInterrupt:
            print("\n\nTracker stopped by user")
        finally:
            # Final save and activity duration update
            self.update_activity_duration("stationary")
            self.save_data()
            
            print("\n" + "="*60)
            print("   FINAL STATISTICS")
            print("="*60)
            stats = self.get_statistics()
            for key, value in stats.items():
                if key != 'activity_durations_minutes':
                    print(f"{key:20s}: {value}")
                else:
                    print(f"\nActivity Durations (minutes):")
                    for activity, minutes in value.items():
                        if minutes > 0:
                            print(f"  {activity:12s}: {minutes:6.1f}")
            
            # Show weekly summary if available
            weekly = self.get_weekly_summary()
            if weekly:
                print("\n" + "="*60)
                print("   WEEKLY SUMMARY (Last 7 Days)")
                print("="*60)
                print(f"Total Steps: {weekly['total_steps']}")
                print(f"Avg Steps/Day: {weekly['avg_steps_per_day']}")
                print(f"Total Distance: {weekly['total_distance_km']} km")
                print(f"Total Calories: {weekly['total_calories']} kcal")
            
            print("="*60 + "\n")


def main():
    """Main function to run the activity tracker"""
    print("\nInitializing QYF0900 Accelerometer with ADS1115...")
    
    try:
        # Initialize sensor with your existing connections
        # X-axis: ADC Channel 0
        # Y-axis: ADC Channel 1
        # Z-axis: ADC Channel 2
        sensor = QYF0900Sensor(address=0x48, gain=1)
        print("Sensor initialized successfully!")
        
        # Calibrate sensor
        print("\nCalibrating sensor...")
        print("IMPORTANT: Keep the device COMPLETELY STILL for 3 seconds")
        time.sleep(2)
        sensor.calibrate(samples=50)
        
        # Create activity tracker
        tracker = ActivityTracker(sensor, sample_rate=25)
        
        # Set user profile (CUSTOMIZE THESE VALUES)
        tracker.set_user_profile(
            weight_kg=70,      # Your weight in kg
            height_cm=170,     # Your height in cm
            age=30,            # Your age
            gender='M'         # 'M' or 'F'
        )
        
        # Test sensor reading
        print("\nTesting sensor...")
        accel = sensor.get_accel_data()
        magnitude = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        print(f"Sensor test: X={accel['x']:.2f}g, Y={accel['y']:.2f}g, "
              f"Z={accel['z']:.2f}g, Total={magnitude:.2f}g")
        
        if 0.5 < magnitude < 1.5:
            print("Sensor readings look good!")
        else:
            print("Warning: Unusual sensor readings. Check connections.")
        
        # Run tracker (press Ctrl+C to stop)
        tracker.run()
        
    except KeyboardInterrupt:
        print("\n\nShutdown requested")
    except Exception as e:
        logger.error(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check I2C is enabled: sudo raspi-config -> Interface Options -> I2C")
        print("2. Check sensor connection: i2cdetect -y 1")
        print("3. Verify ADS1115 at address 0x48")
        print("4. Check wiring:")
        print("   ADS1115 VDD  -> RPi 3.3V")
        print("   ADS1115 GND  -> RPi GND")
        print("   ADS1115 SCL  -> RPi SCL (GPIO 3)")
        print("   ADS1115 SDA  -> RPi SDA (GPIO 2)")
        print("   QYF0900 X    -> ADS1115 A0")
        print("   QYF0900 Y    -> ADS1115 A1")
        print("   QYF0900 Z    -> ADS1115 A2")
        print("5. Install dependencies:")
        print("   sudo pip3 install Adafruit-ADS1x15 numpy")


if __name__ == "__main__":
    main()

