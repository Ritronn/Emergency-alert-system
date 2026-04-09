"""
Camera recording module for emergency video capture
"""
import os
import threading
import time
from datetime import datetime
from typing import Optional

try:
    import cv2
except ImportError:
    print("WARNING: OpenCV not installed - camera recording disabled")
    cv2 = None

from config import Config

class CameraRecorder:
    """
    Camera recording system for emergency video capture
    """
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        
        self.camera = None
        self.is_recording = False
        self.record_thread = None
        self.current_recording_path = None
        
        # Create recordings directory
        os.makedirs(config.RECORDINGS_DIR, exist_ok=True)
        
        self._initialize_camera()
    
    def _initialize_camera(self):
        """Initialize camera for recording"""
        if not cv2:
            self.logger.error("OpenCV not available - camera recording disabled")
            return
        
        try:
            # Try different camera indices (0, 1, 2) to find available camera
            for camera_index in range(3):
                self.camera = cv2.VideoCapture(camera_index)
                if self.camera.isOpened():
                    # Set camera properties
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.VIDEO_RESOLUTION[0])
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.VIDEO_RESOLUTION[1])
                    self.camera.set(cv2.CAP_PROP_FPS, self.config.VIDEO_FPS)
                    
                    self.logger.info(f"Camera initialized on index {camera_index}")
                    return
                else:
                    self.camera.release()
            
            self.logger.error("No camera found")
            self.camera = None
            
        except Exception as e:
            self.logger.error(f"Failed to initialize camera: {e}")
            self.camera = None
    
    def start_recording(self, duration: int = None) -> Optional[str]:
        """
        Start emergency video recording
        
        Args:
            duration: Recording duration in seconds (uses config default if None)
            
        Returns:
            Path to recording file or None if failed
        """
        if not self.camera:
            self.logger.error("Cannot start recording - camera not available")
            return None
        
        if self.is_recording:
            self.logger.warning("Recording already in progress")
            return self.current_recording_path
        
        if duration is None:
            duration = self.config.RECORDING_DURATION
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"emergency_{timestamp}.mp4"
        filepath = os.path.join(self.config.RECORDINGS_DIR, filename)
        
        self.current_recording_path = filepath
        self.is_recording = True
        
        # Start recording in separate thread
        self.record_thread = threading.Thread(
            target=self._record_video,
            args=(filepath, duration),
            daemon=True
        )
        self.record_thread.start()
        
        self.logger.info(f"Started emergency recording: {filename} ({duration}s)")
        return filepath
    
    def _record_video(self, filepath: str, duration: int):
        """
        Record video to file
        
        Args:
            filepath: Output video file path
            duration: Recording duration in seconds
        """
        try:
            # Define video codec and create VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(
                filepath,
                fourcc,
                self.config.VIDEO_FPS,
                self.config.VIDEO_RESOLUTION
            )
            
            start_time = time.time()
            frame_count = 0
            
            while self.is_recording and (time.time() - start_time) < duration:
                ret, frame = self.camera.read()
                
                if ret:
                    # Add timestamp overlay
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(
                        frame,
                        f"EMERGENCY - {timestamp}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),  # Red color
                        2
                    )
                    
                    out.write(frame)
                    frame_count += 1
                else:
                    self.logger.error("Failed to read frame from camera")
                    break
                
                # Small delay to maintain frame rate
                time.sleep(1.0 / self.config.VIDEO_FPS)
            
            # Clean up
            out.release()
            
            # Verify recording
            if frame_count > 0:
                file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                self.logger.info(f"Recording completed: {filepath} ({frame_count} frames, {file_size} bytes)")
            else:
                self.logger.error(f"Recording failed: no frames captured")
                if os.path.exists(filepath):
                    os.remove(filepath)
                filepath = None
            
        except Exception as e:
            self.logger.error(f"Error during video recording: {e}")
            filepath = None
        
        finally:
            self.is_recording = False
            if filepath != self.current_recording_path:
                self.current_recording_path = None
    
    def stop_recording(self):
        """Stop current recording"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        if self.record_thread:
            self.record_thread.join(timeout=5)
        
        self.logger.info("Recording stopped")
    
    def take_photo(self) -> Optional[str]:
        """
        Take a single photo
        
        Returns:
            Path to photo file or None if failed
        """
        if not self.camera:
            self.logger.error("Cannot take photo - camera not available")
            return None
        
        try:
            ret, frame = self.camera.read()
            
            if ret:
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"emergency_photo_{timestamp}.jpg"
                filepath = os.path.join(self.config.RECORDINGS_DIR, filename)
                
                # Add timestamp overlay
                timestamp_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(
                    frame,
                    f"EMERGENCY - {timestamp_text}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )
                
                # Save photo
                cv2.imwrite(filepath, frame)
                
                self.logger.info(f"Emergency photo saved: {filename}")
                return filepath
            else:
                self.logger.error("Failed to capture photo")
                return None
                
        except Exception as e:
            self.logger.error(f"Error taking photo: {e}")
            return None
    
    def get_recording_status(self) -> dict:
        """
        Get current recording status
        
        Returns:
            Dictionary with recording status information
        """
        return {
            'is_recording': self.is_recording,
            'current_file': self.current_recording_path,
            'camera_available': self.camera is not None and self.camera.isOpened(),
            'recordings_dir': self.config.RECORDINGS_DIR
        }
    
    def list_recordings(self) -> list:
        """
        List all recorded files
        
        Returns:
            List of recording file paths
        """
        try:
            if not os.path.exists(self.config.RECORDINGS_DIR):
                return []
            
            recordings = []
            for filename in os.listdir(self.config.RECORDINGS_DIR):
                if filename.endswith(('.mp4', '.avi', '.jpg', '.png')):
                    filepath = os.path.join(self.config.RECORDINGS_DIR, filename)
                    recordings.append(filepath)
            
            return sorted(recordings, reverse=True)  # Most recent first
            
        except Exception as e:
            self.logger.error(f"Error listing recordings: {e}")
            return []
    
    def cleanup(self):
        """Clean up camera resources"""
        self.stop_recording()
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.logger.info("Camera recorder cleaned up")