"""
Hindi voice detection module for emergency keyword recognition using VOSK
Keywords: "meri madad karo" (3 times) + "haan" for confirmation
For future use - not integrated in main system yet
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
except ImportError:
    print("WARNING: VOSK libraries not installed")
    print("Run: pip install vosk pyaudio")
    VOSK_AVAILABLE = False
    vosk = None
    pyaudio = None

from config import Config

class HindiVoiceDetector:
    """
    Hindi voice detection system using VOSK for high-accuracy offline recognition
    Keywords: "meri madad karo" (3 times) + "haan" for confirmation
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
        
        self._initialize_vosk_hindi()
    
    def _initialize_vosk_hindi(self):
        """Initialize VOSK Hindi speech recognition"""
        if not VOSK_AVAILABLE:
            self.logger.error("VOSK libraries not available")
            return
        
        try:
            # Ensure VOSK Hindi model exists
            model_path = self._ensure_vosk_hindi_model()
            if not model_path:
                return
            
            # Initialize VOSK with Hindi model
            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            
            # Initialize microphone
            self.microphone = pyaudio.PyAudio()
            
            self.logger.info("VOSK Hindi voice detection initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize VOSK Hindi: {e}")
            self.model = None
            self.recognizer = None
    
    def _ensure_vosk_hindi_model(self):
        """Download VOSK Hindi model if not present"""
        model_dir = "vosk-model-small-hi-0.22"
        model_path = os.path.join(os.getcwd(), model_dir)
        
        if os.path.exists(model_path):
            self.logger.info(f"VOSK Hindi model found: {model_path}")
            return model_path
        
        self.logger.info("Downloading VOSK Hindi model (~50MB)...")
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip"
        
        try:
            # Download Hindi model
            zip_path = "vosk-hindi-model.zip"
            urllib.request.urlretrieve(model_url, zip_path)
            
            # Extract model
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall()
            
            # Clean up
            os.remove(zip_path)
            
            self.logger.info(f"VOSK Hindi model downloaded: {model_path}")
            return model_path
            
        except Exception as e:
            self.logger.error(f"Failed to download VOSK Hindi model: {e}")
            return None
    
    def start_listening(self, keyword_callback: Callable[[str], None], 
                       confirmation_callback: Callable[[], None]):
        """
        Start listening for Hindi voice commands using VOSK
        
        Args:
            keyword_callback: Function called when emergency keywords detected
            confirmation_callback: Function called when confirmation received
        """
        if not self.model or not self.recognizer:
            self.logger.error("Cannot start Hindi voice detection - VOSK not initialized")
            return
        
        if self.is_listening:
            self.logger.warning("Hindi voice detection already active")
            return
        
        self.keyword_callback = keyword_callback
        self.confirmation_callback = confirmation_callback
        
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listening_loop, daemon=True)
        self.listen_thread.start()
        
        self.logger.info("VOSK Hindi voice detection started")
    
    def stop_listening(self):
        """Stop Hindi voice detection"""
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=3)
        
        if self.microphone:
            self.microphone.terminate()
        
        self.logger.info("VOSK Hindi voice detection stopped")
    
    def _listening_loop(self):
        """Main VOSK Hindi listening loop"""
        # Audio stream settings
        stream = self.microphone.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=8000
        )
        stream.start_stream()
        
        self.logger.info("VOSK Hindi listening started")
        
        try:
            while self.is_listening:
                # Read audio data
                data = stream.read(4000, exception_on_overflow=False)
                
                # Process with VOSK Hindi
                if self.recognizer.AcceptWaveform(data):
                    # Complete phrase recognized
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').lower().strip()
                    
                    if text:
                        self.logger.debug(f"VOSK Hindi recognized: '{text}'")
                        self._process_recognized_hindi_text(text)
                        
        except Exception as e:
            self.logger.error(f"Error in VOSK Hindi listening loop: {e}")
        finally:
            stream.stop_stream()
            stream.close()
    
    def _process_recognized_hindi_text(self, text):
        """
        Process recognized Hindi text for emergency keywords and confirmation
        
        Args:
            text: Recognized Hindi speech text
        """
        # Check for Hindi emergency keywords
        help_count = self._count_hindi_emergency_keywords(text)
        if help_count > 0:
            self._handle_emergency_keyword(text, help_count)
        
        # Check for Hindi confirmation
        elif self._contains_hindi_confirmation(text):
            self._handle_confirmation()
    
    def _count_hindi_emergency_keywords(self, text: str) -> int:
        """
        Count how many Hindi emergency keywords are in the text
        
        Args:
            text: Recognized Hindi speech text
            
        Returns:
            Number of Hindi emergency keywords found
        """
        # Hindi emergency phrases
        hindi_help_phrases = [
            "मेरी मदद करो",  # meri madad karo
            "मदद करो",      # madad karo  
            "मदद",          # madad
            "बचाओ",         # bachao (save me)
            "सहायता"        # sahayata (help/assistance)
        ]
        
        # Also check romanized versions in case model recognizes them
        romanized_help = [
            "meri madad karo",
            "madad karo", 
            "madad",
            "bachao",
            "sahayata"
        ]
        
        count = 0
        
        # Check Hindi phrases
        for phrase in hindi_help_phrases:
            count += text.count(phrase)
        
        # Check romanized versions
        for phrase in romanized_help:
            count += text.count(phrase)
        
        return count
    
    def _contains_hindi_confirmation(self, text: str) -> bool:
        """
        Check if text contains Hindi confirmation keywords
        
        Args:
            text: Recognized Hindi speech text
            
        Returns:
            True if Hindi confirmation keywords found
        """
        # Hindi confirmation words
        hindi_confirm_words = [
            "हाँ",      # haan (yes)
            "हां",      # haan (alternative spelling)
            "जी हाँ",   # ji haan (yes sir/madam)
            "ठीक है",   # theek hai (okay)
            "सही",      # sahi (correct)
        ]
        
        # Romanized versions
        romanized_confirm = [
            "haan", "han", "ji haan", "ji han",
            "theek hai", "thik hai", "sahi"
        ]
        
        text_clean = text.lower().strip()
        
        # Check Hindi confirmation words
        for word in hindi_confirm_words:
            if word in text_clean:
                return True
        
        # Check romanized versions
        for word in romanized_confirm:
            if word in text_clean:
                return True
        
        # Check exact matches for short responses
        if text_clean in ["हाँ", "हां", "haan", "han"]:
            return True
            
        return False
    
    def _handle_emergency_keyword(self, text: str, detected_count: int):
        """
        Handle detection of Hindi emergency keywords
        
        Args:
            text: The recognized Hindi text containing keywords
            detected_count: Number of help keywords detected in this phrase
        """
        current_time = time.time()
        
        # Reset count if too much time has passed
        if current_time - self.last_help_time > self.help_reset_timeout:
            self.help_count = 0
        
        # Add the detected count to total
        self.help_count += detected_count
        self.last_help_time = current_time
        
        self.logger.info(f"Hindi emergency keywords detected: found {detected_count} in '{text}'. Total: {self.help_count}/{self.config.HELP_COUNT_REQUIRED}")
        
        if self.help_count >= self.config.HELP_COUNT_REQUIRED:
            self.logger.warning(f"Hindi emergency triggered by voice command!")
            if self.keyword_callback:
                self.keyword_callback("hindi_voice")
            
            # Reset counter
            self.help_count = 0
    
    def _handle_confirmation(self):
        """Handle Hindi confirmation response"""
        self.logger.info("Hindi voice confirmation received")
        if self.confirmation_callback:
            self.confirmation_callback()
    
    def cleanup(self):
        """Clean up Hindi voice detection resources"""
        self.stop_listening()
        self.logger.info("VOSK Hindi voice detector cleaned up")