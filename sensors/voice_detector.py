"""
Voice detection module for emergency keyword recognition using VOSK
High-accuracy offline speech recognition for Raspberry Pi
"""
import json
import threading
import time
import os
import urllib.request
import zipfile
from typing import Callable, Optional

try:
    import vosk
    import pyaudio
    VOSK_AVAILABLE = True
    print("VOSK offline speech recognition available")
except ImportError as e:
    print(f"WARNING: VOSK libraries not available: {e}")
    print("Voice detection will be disabled")
    print("To fix: pip install vosk pyaudio")
    VOSK_AVAILABLE = False
    vosk = None
    pyaudio = None

from config import Config

class VoiceDetector:
    """
    Voice detection system using VOSK for high-accuracy offline recognition
    """
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        
        self.is_listening = False
        self.listen_thread = None
        
        # Callbacks
        self.keyword_callback = None
        self.confirmation_callback = None
        
        # Detection state
        self.help_count = 0
        self.last_help_time = 0
        self.help_reset_timeout = 5  # Reset count after 5 seconds
        
        # VOSK components
        self.model = None
        self.recognizer = None
        self.microphone = None
        
        self._initialize_vosk()
    
    def _initialize_vosk(self):
        """Initialize VOSK speech recognition"""
        if not VOSK_AVAILABLE:
            self.logger.error("VOSK libraries not available")
            return
        
        try:
            # Ensure VOSK model exists
            model_path = self._ensure_vosk_model()
            if not model_path:
                return
            
            # Initialize VOSK
            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            
            # Initialize microphone
            self.microphone = pyaudio.PyAudio()
            
            self.logger.info("VOSK voice detection initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize VOSK: {e}")
            self.model = None
            self.recognizer = None
    
    def _ensure_vosk_model(self):
        """Download VOSK English model if not present"""
        model_dir = "vosk-model-small-en-us-0.15"
        model_path = os.path.join(os.getcwd(), model_dir)
        
        if os.path.exists(model_path):
            self.logger.info(f"VOSK model found: {model_path}")
            return model_path
        
        self.logger.info("Downloading VOSK English model (50MB)...")
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        
        try:
            # Download model
            zip_path = "vosk-model.zip"
            urllib.request.urlretrieve(model_url, zip_path)
            
            # Extract model
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall()
            
            # Clean up
            os.remove(zip_path)
            
            self.logger.info(f"VOSK model downloaded: {model_path}")
            return model_path
            
        except Exception as e:
            self.logger.error(f"Failed to download VOSK model: {e}")
            return None
    
    def start_listening(self, keyword_callback: Callable[[str], None], 
                       confirmation_callback: Callable[[], None]):
        """
        Start listening for voice commands using VOSK
        
        Args:
            keyword_callback: Function called when emergency keywords detected
            confirmation_callback: Function called when confirmation received
        """
        if not VOSK_AVAILABLE:
            self.logger.error("Cannot start voice detection - VOSK not available")
            self.logger.error("Voice detection is disabled")
            return
        
        if not self.model or not self.recognizer:
            self.logger.error("Cannot start voice detection - VOSK not initialized")
            return
        
        if self.is_listening:
            self.logger.warning("Voice detection already active")
            return
        
        self.keyword_callback = keyword_callback
        self.confirmation_callback = confirmation_callback
        
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listening_loop, daemon=True)
        self.listen_thread.start()
        
        self.logger.info("VOSK voice detection started")
    
    def stop_listening(self):
        """Stop voice detection"""
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=3)
        
        if self.microphone:
            self.microphone.terminate()
        
        self.logger.info("VOSK voice detection stopped")
    
    def _listening_loop(self):
        """Main VOSK listening loop"""
        # Audio stream settings
        stream = self.microphone.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=8000
        )
        stream.start_stream()
        
        self.logger.info("VOSK listening started")
        
        try:
            while self.is_listening:
                # Read audio data
                data = stream.read(4000, exception_on_overflow=False)
                
                # Process with VOSK
                if self.recognizer.AcceptWaveform(data):
                    # Complete phrase recognized
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').lower().strip()
                    
                    if text:
                        self.logger.debug(f"VOSK recognized: '{text}'")
                        self._process_recognized_text(text)
                        
        except Exception as e:
            self.logger.error(f"Error in VOSK listening loop: {e}")
        finally:
            stream.stop_stream()
            stream.close()
    
    def _process_recognized_text(self, text):
        """
        Process recognized text for emergency keywords and confirmation
        
        Args:
            text: Recognized speech text
        """
        # Check for emergency keywords
        help_count = self._count_emergency_keywords(text)
        if help_count > 0:
            self._handle_emergency_keyword(text, help_count)
        
        # Check for confirmation
        elif self._contains_confirmation(text):
            self._handle_confirmation()
    
    def _count_emergency_keywords(self, text: str) -> int:
        """
        Count how many emergency keywords are in the text
        
        Args:
            text: Recognized speech text
            
        Returns:
            Number of emergency keywords found
        """
        emergency_words = [
            self.config.HELP_KEYWORD,
            "emergency",
            "help me",
            "assistance"
        ]
        
        count = 0
        for word in emergency_words:
            count += text.count(word)
        return count
    
    def _contains_confirmation(self, text: str) -> bool:
        """
        Check if text contains confirmation keywords
        
        Args:
            text: Recognized speech text
            
        Returns:
            True if confirmation keywords found
        """
        confirmation_words = [
            self.config.CONFIRMATION_KEYWORD,
            "yeah", "yep", "confirm",
            "affirmative", "correct", "true",
            "ok", "okay"
        ]
        
        text_lower = text.lower().strip()
        
        # Check for matches
        for word in confirmation_words:
            if word in text_lower:
                return True
        
        # Also check if the entire text is just a confirmation word
        if text_lower in ["yes", "yeah", "yep", "y", "ok", "okay"]:
            return True
            
        return False
    
    def _handle_emergency_keyword(self, text: str, detected_count: int):
        """
        Handle detection of emergency keywords
        
        Args:
            text: The recognized text containing keywords
            detected_count: Number of help keywords detected in this phrase
        """
        current_time = time.time()
        
        # Reset count if too much time has passed
        if current_time - self.last_help_time > self.help_reset_timeout:
            self.help_count = 0
        
        # Add the detected count to total
        self.help_count += detected_count
        self.last_help_time = current_time
        
        self.logger.info(f"Emergency keywords detected: found {detected_count} in '{text}'. Total: {self.help_count}/{self.config.HELP_COUNT_REQUIRED}")
        
        if self.help_count >= self.config.HELP_COUNT_REQUIRED:
            self.logger.warning(f"Emergency triggered by voice command!")
            if self.keyword_callback:
                self.keyword_callback("voice")
            
            # Reset counter
            self.help_count = 0
    
    def _handle_confirmation(self):
        """Handle confirmation response"""
        self.logger.info("Voice confirmation received")
        if self.confirmation_callback:
            self.confirmation_callback()
    
    def cleanup(self):
        """Clean up voice detection resources"""
        self.stop_listening()
        self.logger.info("VOSK voice detector cleaned up")