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
