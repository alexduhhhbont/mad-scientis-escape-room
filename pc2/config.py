import os
from pathlib import Path

# ─── DMX / FTDI ─────────────────────────────────────
FTDI_VENDOR    = 0x0403   # Enttec Open DMX USB (FTDI FT232R)
FTDI_PRODUCT   = 0x6001
DMX_REFRESH_HZ = 40

CHANNEL_ROLES = ["red", "green", "blue", "intensity", "strobe", "generic"]

# ─── Web API ─────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000
API_KEY  = "change-me-to-something-random"

# ─── Fixtures file ───────────────────────────────────
FIXTURES_FILE = Path(__file__).parent.parent / "fixtures.json"

# ─── PC1 connection ──────────────────────────────────
PC1_URL     = "http://192.168.178.151:8001"
PC1_API_KEY = "change-me-to-something-random"

# ─── GM phone panel ──────────────────────────────────
GM_KEY = "candy-gm"

# ─── Audio ───────────────────────────────────────────
AUDIO_DIR          = "audio"
AUDIO_WAITING      = os.path.join(AUDIO_DIR, "waiting.mp3")
AUDIO_INTRO        = os.path.join(AUDIO_DIR, "intro.mp3")
AUDIO_MAIN_THEME   = os.path.join(AUDIO_DIR, "theme.mp3")
AUDIO_WRONG        = os.path.join(AUDIO_DIR, "wrong.mp3")
AUDIO_STAGE1_STORY = os.path.join(AUDIO_DIR, "stage1_story.wav")
AUDIO_VICTORY      = os.path.join(AUDIO_DIR, "victory.wav")
AUDIO_HINT         = os.path.join(AUDIO_DIR, "hint.wav")

THEME_VOLUME = 0.40
DUCK_VOLUME  = 0.10
SFX_VOLUME   = 0.90
