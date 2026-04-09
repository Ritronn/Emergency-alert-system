"""
VOSK Hindi Voice Emergency System - NO TELEGRAM VERSION
Hindi keywords: "meri madad karo" (3 times) + "haan" for confirmation
Same functionality but in Hindi - NO messages sent (to avoid spam)
"""

import json
import time
import threading
import os
import urllib.request
import zipfile
from datetime import datetime

# Import our modules
from config import Config
from utils import setup_logging

try:
    import vosk
    import pyaudio
    VOSK_AVAILABLE = True
    print("✅ VOSK offline speech recognition available")
except ImportError:
    VOSK_AVAILABLE = False
    print("❌ VOSK not available - install with: pip install vosk pyaudio")

class VoskHindiVoiceSystem:
    """
    High-accuracy offline Hindi voice emergency system using VOSK
    Keywords: "meri madad karo" (3 times) + "haan" for confirmation
    NO TELEGRAM MESSAGES - Just local testing
    """
    
    def __init__(self):
        self.config = Config.load_from_env()
        self.logger = setup_logging("vosk_hindi.log")
        
        # VOSK components
        self.model = None
        self.recognizer = None
        self.microphone = None
        
        # System state
        self.is_listening = False
        self.listen_thread = None
        
        # Emergency state - Hindi keywords
        self.help_count = 0
        self.last_help_time = 0
        self.help_reset_timeout = 5
        
        # Confirmation state
        self.pending_emergency = False
        self.confirmation_timer = None
        
        self._initialize_vosk_hindi()
        
        print("🎯 VOSK Hindi Emergency System initialized (NO TELEGRAM)")
    
    def _initialize_vosk_hindi(self):
        """Initialize VOSK Hindi speech recognition"""
        if not VOSK_AVAILABLE:
            print("❌ VOSK not available")
            return
        
        try:
            # Download Hindi model if not exists
            model_path = self._ensure_vosk_hindi_model()
            if not model_path:
                return
            
            # Initialize VOSK with Hindi model
            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            
            # Initialize microphone
            self.microphone = pyaudio.PyAudio()
            
            print("✅ VOSK Hindi speech recognition ready")
            print(f"📁 Using Hindi model: {model_path}")
            
            self.logger.info("VOSK Hindi voice detection initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize VOSK Hindi: {e}")
            print(f"❌ VOSK Hindi initialization failed: {e}")
    
    def _ensure_vosk_hindi_model(self):
        """Download VOSK Hindi model if not present"""
        model_dir = "vosk-model-small-hi-0.22"
        model_path = os.path.join(os.getcwd(), model_dir)
        
        if os.path.exists(model_path):
            print(f"✅ VOSK Hindi model found: {model_path}")
            return model_path
        
        print("📥 Downloading VOSK Hindi model (~50MB)...")
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip"
        
        try:
            # Download Hindi model
            zip_path = "vosk-hindi-model.zip"
            print("⏳ Downloading... this may take a moment")
            urllib.request.urlretrieve(model_url, zip_path)
            
            # Extract model
            print("📦 Extracting Hindi model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall()
            
            # Clean up
            os.remove(zip_path)
            
            print(f"✅ VOSK Hindi model downloaded: {model_path}")
            return model_path
            
        except Exception as e:
            print(f"❌ Failed to download VOSK Hindi model: {e}")
            print("   You can manually download from: https://alphacephei.com/vosk/models")
            print("   Look for: vosk-model-small-hi-0.22.zip")
            return None
    
    def start_listening(self):
        """Start VOSK Hindi voice monitoring"""
        if not self.model or not self.recognizer:
            print("❌ Cannot start - VOSK Hindi not initialized")
            return
        
        if self.is_listening:
            print("⚠️ Already listening")
            return
        
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listening_loop, daemon=True)
        self.listen_thread.start()
        
        print("🎤 VOSK Hindi Voice monitoring started")
        print("=" * 60)
        print("🇮🇳 HINDI EMERGENCY SYSTEM - NO TELEGRAM SPAM")
        print("=" * 60)
        print("📢 कहें 'मेरी मदद करो' (3 बार) - Say 'MERI MADAD KARO' (3 times)")
        print("📢 फिर कहें 'हाँ' - Then say 'HAAN' within 10 seconds")
        print("🔒 OFFLINE - No internet required (VOSK Hindi)")
        print("📵 NO TELEGRAM MESSAGES - Just local testing")
        print("Press Ctrl+C to stop")
        print("=" * 60)
    
    def stop_listening(self):
        """Stop voice monitoring"""
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=3)
        
        if self.confirmation_timer:
            self.confirmation_timer.cancel()
        
        if self.microphone:
            self.microphone.terminate()
        
        print("🔇 VOSK Hindi voice monitoring stopped")
    
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
        
        print("🔊 VOSK Hindi listening started...")
        
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
                        print(f"🗣️ VOSK Hindi heard: '{text}'")
                        self._process_recognized_text(text)
                
                # Also check partial results for responsiveness
                else:
                    partial = json.loads(self.recognizer.PartialResult())
                    partial_text = partial.get('partial', '').lower().strip()
                    
                    # Show partial recognition during confirmation for feedback
                    if self.pending_emergency and partial_text:
                        print(f"🔍 Partial: '{partial_text}'", end='\r')
                        
        except Exception as e:
            self.logger.error(f"Error in VOSK Hindi listening loop: {e}")
            print(f"❌ VOSK Hindi listening error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
    
    def _process_recognized_text(self, text):
        """Process recognized Hindi text for commands"""
        # Count Hindi help keywords
        help_count = self._count_hindi_help_keywords(text)
        if help_count > 0:
            self._handle_help_keyword(text, help_count)
        
        # Check for Hindi confirmation during emergency
        elif self.pending_emergency:
            print(f"\n🔍 Checking for Hindi confirmation in: '{text}'")
            if self._contains_hindi_confirmation(text):
                print(f"✅ HINDI CONFIRMATION detected: '{text}'")
                self._handle_confirmation()
            else:
                print(f"❌ No Hindi confirmation in: '{text}'")
    
    def _count_hindi_help_keywords(self, text):
        """Count Hindi help keywords in text"""
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
    
    def _contains_hindi_confirmation(self, text):
        """Check for Hindi confirmation words"""
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
            "theek hai", "thik hai", "sahi", "yes"
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
        if text_clean in ["हाँ", "हां", "haan", "han", "yes"]:
            return True
            
        return False
    
    def _handle_help_keyword(self, text, detected_count):
        """Handle Hindi help keyword detection"""
        current_time = time.time()
        
        # Reset count if too much time passed
        if current_time - self.last_help_time > self.help_reset_timeout:
            self.help_count = 0
        
        self.help_count += detected_count
        self.last_help_time = current_time
        
        print(f"🚨 HINDI HELP detected! Found {detected_count} in phrase. Total: {self.help_count}/{self.config.HELP_COUNT_REQUIRED}")
        
        if self.help_count >= self.config.HELP_COUNT_REQUIRED:
            self._trigger_emergency()
            self.help_count = 0
    
    def _trigger_emergency(self):
        """Trigger VOSK Hindi emergency process - NO TELEGRAM"""
        print("\n" + "="*60)
        print("🚨 HINDI EMERGENCY TRIGGERED! / हिंदी आपातकाल!")
        print("="*60)
        print(f"⏰ आपके पास {self.config.CONFIRMATION_TIMEOUT} सेकंड हैं 'हाँ' कहने के लिए")
        print(f"⏰ You have {self.config.CONFIRMATION_TIMEOUT} seconds to say 'HAAN'")
        print("🗣️ कहें 'हाँ' आपातकाल की पुष्टि के लिए - Say 'HAAN' to confirm")
        print("🎯 VOSK Hindi listening (high accuracy)")
        print("📵 NO TELEGRAM - Just testing")
        print("⏳ Or wait for timeout to cancel")
        print("="*60)
        
        self.pending_emergency = True
        
        # Start confirmation timer
        self.confirmation_timer = threading.Timer(
            self.config.CONFIRMATION_TIMEOUT,
            self._confirmation_timeout
        )
        self.confirmation_timer.start()
        
        self.logger.warning("VOSK Hindi Emergency triggered - waiting for confirmation (NO TELEGRAM)")
    
    def _handle_confirmation(self):
        """Handle VOSK Hindi confirmation - NO TELEGRAM"""
        if not self.pending_emergency:
            return
        
        print("\n" + "="*60)
        print("✅ HINDI CONFIRMATION RECEIVED! / हिंदी पुष्टि प्राप्त!")
        print("="*60)
        
        # Cancel timer
        if self.confirmation_timer:
            self.confirmation_timer.cancel()
        
        self.pending_emergency = False
        
        # Execute emergency response WITHOUT TELEGRAM
        self._execute_hindi_emergency()
        
        print("🚨 Hindi Emergency confirmed! / हिंदी आपातकाल की पुष्टि!")
        print("📹 Recording would start now (30 seconds)")
        print("💾 Alert saved locally (offline)")
        print("📵 NO TELEGRAM MESSAGE SENT")
        print("🇮🇳 Hindi VOSK accuracy: Perfect for testing")
        print("="*60)
        
        self.logger.critical("VOSK Hindi Emergency confirmed and logged (NO TELEGRAM)")
    
    def _confirmation_timeout(self):
        """Handle confirmation timeout - NO TELEGRAM"""
        if not self.pending_emergency:
            return
        
        print("\n" + "="*60)
        print("⏰ HINDI CONFIRMATION TIMEOUT / हिंदी पुष्टि समय समाप्त")
        print("="*60)
        print("❌ Emergency cancelled - no confirmation received")
        print("❌ आपातकाल रद्द - कोई पुष्टि नहीं मिली")
        print("🔄 System continues Hindi monitoring...")
        print("📵 NO TELEGRAM MESSAGE SENT")
        print("="*60)
        
        self.pending_emergency = False
        self.logger.info("VOSK Hindi Emergency cancelled due to timeout (NO TELEGRAM)")
    
    def _execute_hindi_emergency(self):
        """Execute Hindi emergency response WITHOUT local file logging"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Log to system logger only (not to separate text files)
        self.logger.critical(f"HINDI EMERGENCY CONFIRMED at {timestamp}")
        
        print("🇮🇳 Hindi Emergency response completed")
        print("📹 Recording would start now (30 seconds)")
        print("📱 Telegram alert would be sent")
        print("💾 Logged to system log only")

def main():
    """Main VOSK Hindi test function - NO TELEGRAM"""
    print("=" * 60)
    print("🇮🇳 VOSK HINDI EMERGENCY SYSTEM - NO TELEGRAM SPAM")
    print("=" * 60)
    print("Perfect for testing Hindi voice commands!")
    print("")
    print("Hindi Features / हिंदी सुविधाएं:")
    print("• High-accuracy offline Hindi speech recognition")
    print("• Keywords: मेरी मदद करो (meri madad karo) - 3 times")
    print("• Confirmation: हाँ (haan)")
    print("• Same emergency process in Hindi")
    print("• Local logging only")
    print("• NO TELEGRAM MESSAGES")
    print("• NO SPAM to your friend")
    print("=" * 60)
    
    if not VOSK_AVAILABLE:
        print("❌ VOSK not available!")
        print("Install: pip install vosk pyaudio")
        return
    
    try:
        system = VoskHindiVoiceSystem()
        
        if not system.model:
            print("❌ VOSK Hindi model not available")
            return
        
        system.start_listening()
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Hindi NO TELEGRAM system stopped by user")
        if 'system' in locals():
            system.stop_listening()
    except Exception as e:
        print(f"❌ Hindi NO TELEGRAM system failed: {e}")
    finally:
        print("🇮🇳 Hindi NO TELEGRAM test completed")

if __name__ == "__main__":
    main()