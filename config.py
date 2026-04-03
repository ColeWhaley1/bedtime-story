"""Load all configuration from .env file."""
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Voice / Model
DEFAULT_VOICE_ID = os.getenv("DEFAULT_VOICE_ID", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Hardware
GPIO_BUTTON_PIN = int(os.getenv("GPIO_BUTTON_PIN", "17"))
BLUETOOTH_SPEAKER_MAC = os.getenv("BLUETOOTH_SPEAKER_MAC", "")

# Wake word
WAKEWORD_MODEL = os.getenv("WAKEWORD_MODEL", "hey_jarvis")
WAKEWORD_THRESHOLD = float(os.getenv("WAKEWORD_THRESHOLD", "0.5"))

# Audio recording
RECORD_SAMPLE_RATE = 16000
RECORD_CHANNELS = 1
RECORD_CHUNK_SIZE = 1024
RECORD_MAX_SECONDS = 8
RECORD_SILENCE_THRESHOLD = 500   # RMS below this = silence
RECORD_SILENCE_DURATION = 1.5    # seconds of silence before stopping

# Story lengths (words)
STORY_LENGTH_SHORT = 500
STORY_LENGTH_MEDIUM = 1000
STORY_LENGTH_LONG = 1500

# Paths
CHIME_PATH = os.path.join(os.path.dirname(__file__), "sounds", "chime.wav")
RECORDING_PATH = "/tmp/recording.wav"

# Bluetooth connection
BT_CONNECT_TIMEOUT = 10   # seconds to wait for BT connection
BT_RETRY_COUNT = 1        # number of reconnection retries
