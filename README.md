# Bedtime Story 🏰

An offline-first, voice-activated epic fantasy story generator for Raspberry Pi 5.
Speak a prompt → Claude crafts a Game-of-Thrones-style story → ElevenLabs narrates
it through your Bluetooth speaker. No screen required.

---

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi 5 | Tested on Pi OS (64-bit, Bookworm) |
| DUNGZDUZ USB microphone | Plug-and-play, auto-detected by name |
| Bluetooth speaker | Paired once manually; auto-reconnects on boot |
| Momentary push button | GPIO 17 → one leg, GND → other leg |

---

## System Dependencies

```bash
sudo apt update
sudo apt install -y \
    mpv \
    bluez \
    bluealsa \
    python3-pip \
    python3-dev \
    portaudio19-dev \
    ffmpeg              # required by openai-whisper
```

---

## Python Setup

```bash
cd bedtime-story
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Tip:** If PyAudio fails to compile, make sure `portaudio19-dev` is installed first.

---

## Bluetooth Speaker Pairing (one-time)

Pair your speaker manually before the first run. The app will reconnect
automatically on every subsequent boot.

```bash
bluetoothctl
> power on
> scan on
# Wait until your speaker appears, then:
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> exit
```

---

## First-Time Setup

Copy the environment template, fill in your API keys, then run the wizard:

```bash
cp .env.example .env
nano .env          # Add ANTHROPIC_API_KEY and ELEVENLABS_API_KEY

python setup.py    # Scans for BT speaker, picks ElevenLabs voice, generates chime.wav
```

`setup.py` will:
1. Scan nearby Bluetooth devices so you can identify your speaker's MAC
2. Fetch your ElevenLabs voice list and let you choose one
3. Generate `sounds/chime.wav` (no external tool needed)

### Recommended ElevenLabs Voices for Epic Fantasy

| Voice | ID | Character |
|---|---|---|
| Clyde | `2EiwWnXFnvU5JabPnv8n` | Deep, gravelly, commanding |
| Arnold | `VR6AewLTigWG4xSOukaG` | Authoritative, measured |
| George | `JBFqnCBsd6RMkjVDRZzb` | Rich, dramatic, British |

> **Note:** ElevenLabs free tier has a monthly character limit (~10,000 chars ≈ 1 short story).
> At 1,000+ words per story the **paid Starter tier** is strongly recommended.
> The app falls back to Google TTS (gTTS) automatically on quota errors.

---

## Run

```bash
python main.py
```

The app logs to stdout. It will:
- Connect to your Bluetooth speaker
- Start the wake-word listener (background thread)
- Start the GPIO button monitor (background thread)
- Wait for a trigger

---

## Triggering a Story

### Wake Word (primary)
Say **"hey Jarvis"** (default) to trigger. The app plays a chime, then listens
for your story prompt.

### GPIO Button (fallback)
- **Short press** (< 2 s): trigger
- **Long press** (≥ 2 s): stop current playback

---

## Example Voice Prompts

After the chime plays, say something like:

```
"a short story about a betrayed king and his scheming adviser"
"something long about two noble houses at war over a cursed throne"
"a story about a sellsword who discovers a dark secret"
"dragons and political intrigue in a dying empire"
```

**Length keywords:**
- "short" / "quick" → ~500 words
- "long" / "longer" → ~1500 words
- Default           → ~1000 words

---

## Wake Word Setup (openWakeWord)

### Install

```bash
pip install openwakeword

# Download pre-trained models (runs on first use, or force it now):
python -c "import openwakeword; openwakeword.utils.download_models()"
```

### Option A — Use the built-in "hey_jarvis" model

No extra steps. Set in `.env`:

```
WAKEWORD_MODEL=hey_jarvis
```

### Option B — Train a custom "hey storyteller" model

openWakeWord includes a training pipeline that needs only a few minutes of
your voice recorded in various environments.

```bash
# 1. Clone the training repo
git clone https://github.com/dscripka/openWakeWord
cd openWakeWord

# 2. Generate synthetic training data (requires Google TTS or real recordings)
python examples/custom_model/generate_training_data.py \
    --target_phrase "hey storyteller" \
    --output_dir ./training_data

# 3. Train
python examples/custom_model/train.py \
    --data_dir ./training_data \
    --output_dir ./models \
    --model_name hey_storyteller

# 4. Copy the .tflite file to your project and update .env:
cp models/hey_storyteller.tflite /path/to/bedtime-story/
```

Then set in `.env`:

```
WAKEWORD_MODEL=/path/to/bedtime-story/hey_storyteller.tflite
WAKEWORD_THRESHOLD=0.5
```

Adjust `WAKEWORD_THRESHOLD` (0.0–1.0) to trade off sensitivity vs. false triggers.

---

## GPIO Button Wiring

```
Pi GPIO 17 (pin 11) ──────┤ button ├────── GND (pin 9 or 14)
```

The input uses the Pi's internal pull-up resistor. No external resistor needed.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key |
| `ELEVENLABS_API_KEY` | — | Strongly recommended. Falls back to gTTS if absent |
| `DEFAULT_VOICE_ID` | — | Set by `setup.py`. ElevenLabs voice ID |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model for story generation |
| `WHISPER_MODEL` | `base` | `tiny` (fastest) / `base` / `small` |
| `GPIO_BUTTON_PIN` | `17` | BCM GPIO pin number |
| `WAKEWORD_MODEL` | `hey_jarvis` | Built-in name or path to `.tflite` |
| `WAKEWORD_THRESHOLD` | `0.5` | Detection sensitivity (0.0–1.0) |
| `BLUETOOTH_SPEAKER_MAC` | — | Set by `setup.py`. Speaker MAC address |

---

## Auto-Start on Boot (systemd)

Create the service file:

```bash
sudo nano /etc/systemd/system/bedtime-story.service
```

Paste:

```ini
[Unit]
Description=Bedtime Story
After=network.target bluetooth.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bedtime-story
ExecStartPre=/bin/sleep 10
ExecStart=/home/pi/bedtime-story/.venv/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bedtime-story.service
sudo systemctl start bedtime-story.service

# Check logs:
journalctl -u bedtime-story -f
```

> **Note:** The `ExecStartPre=/bin/sleep 10` gives Bluetooth time to come up before the app connects.

---

## Performance Tips

| Goal | Setting |
|---|---|
| Fastest transcription | `WHISPER_MODEL=tiny` |
| Best transcription accuracy | `WHISPER_MODEL=small` |
| Lowest API cost | `CLAUDE_MODEL=claude-haiku-4-5` |
| Highest story quality | `CLAUDE_MODEL=claude-opus-4-6` |
| Wake word less sensitive | Raise `WAKEWORD_THRESHOLD` toward 0.8 |
| Wake word more sensitive | Lower `WAKEWORD_THRESHOLD` toward 0.3 |

On a Pi 5, `whisper base` transcribes 8 seconds of audio in ~5–8 seconds.
`tiny` is roughly 3×faster at some accuracy cost.

---

## Project Structure

```
bedtime-story/
├── main.py              Entry point — starts all threads, pipeline loop
├── wake_word.py         openWakeWord detection on background thread
├── gpio_button.py       GPIO button monitor (fallback trigger)
├── voice_input.py       PyAudio (USB mic) + Whisper transcription
├── intent_parser.py     Extract themes & length from transcription
├── story_generator.py   Anthropic API — generate story text (streaming)
├── tts.py               ElevenLabs API — synthesize to MP3 (gTTS fallback)
├── audio_player.py      Bluetooth reconnect + mpv playback
├── setup.py             One-time CLI setup wizard
├── config.py            Load all settings from .env
├── sounds/
│   ├── chime.wav        Generated by setup.py or sounds/generate_chime.py
│   └── generate_chime.py  Standalone chime generator (no external deps)
├── .env                 Your secrets (not committed)
├── .env.example         Template
└── requirements.txt
```

---

## Troubleshooting

**No audio from speaker**
- Run `bluetoothctl info XX:XX:XX:XX:XX:XX` to verify the speaker is trusted
- Check `bluealsa` is running: `systemctl status bluealsa`
- Test directly: `mpv --audio-device=alsa/bluealsa /path/to/file.mp3`

**Wake word never triggers**
- Lower `WAKEWORD_THRESHOLD` (try 0.3)
- Make sure you downloaded model files: `python -c "import openwakeword; openwakeword.utils.download_models()"`
- Check mic is detected: look for "Found USB mic" in startup logs

**Whisper transcription is empty or wrong**
- Speak clearly, closer to the mic
- Try `WHISPER_MODEL=small` for better accuracy
- Check mic levels with `arecord -D hw:CARD=DUNGZDUZ,DEV=0 -f S16_LE -r 16000 -d 5 test.wav && aplay test.wav`

**ElevenLabs quota error**
- The app automatically falls back to gTTS — you will hear a robotic voice
- Upgrade to ElevenLabs Starter ($5/month) for ~30,000 chars/month

**gpiozero import error on non-Pi machine**
- Normal on macOS/Linux dev machines — the GPIO button is silently disabled
- The wake word and API pipeline still work normally
