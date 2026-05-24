# Wonky's Candy Factory Escape Room — System Setup

Two machines work together to run the room. **PC 1** runs the player-facing terminal (puzzle interface). **PC 2** runs the DMX lighting controller and serves the **GM phone panel**. The Game Master controls everything from their phone by connecting to PC 2.

```
                        ┌─────────────────────────────────┐
  GM phone              │  PC 2 — controller.py           │
  browser  ──HTTP──▶   │  FastAPI :8000                  │
                        │  • /gm  GM phone panel          │──▶ Enttec Open DMX USB
                        │  • /lights/*  PC1 events        │         │
                        │  • /gm/ctrl/game/*  proxied ──────▶  PC 1 — escape_room.py
                        └─────────────────────────────────┘    FastAPI :8001
                                                                 • /game/*  game control
                                                                 • /game/audio/*  audio
```

---

## PC 1 — Player Terminal

Runs a full-screen Tkinter puzzle interface locked to the desktop.

**Intro sequence:** A startup screen plays with audio and a rainbow light sweep before the game begins.

**Stage 1 — Password:** Players enter the secret code (`CHAOS42` by default).

**Stage 2 — Switches:** Players configure six levers in the correct combination.

**Stage 3 — Victory:** Success screen with victory audio and celebration lights.

Each wrong answer fires a wrong-answer sound effect over the ducked background theme, plus a red light flash. Each stage transition fires story audio and a light sequence. An ambient idle light pulse runs every 12 seconds between events.

### Setup

```bash
pip install -r requirements_pc1.txt
mkdir audio
```

Place audio files in the `audio/` folder:

| File | When it plays |
|------|---------------|
| `audio/intro.wav` | Once at startup; main theme auto-starts after |
| `audio/main_theme.wav` | Looping background music throughout the game |
| `audio/wrong.wav` | Wrong password or wrong switches (plays over ducked theme) |
| `audio/stage1_story.wav` | Story narration after password is accepted |
| `audio/victory.wav` | Final win fanfare |
| `audio/hint.wav` | Optional — triggered from the GM panel |

### Configuration (`escape_room.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PASSWORD` | `CHAOS42` | Stage 1 password |
| `SWITCH_SOLUTION` | `[True, True, False, False, True, False]` | Correct lever states (index 0 = lever 1) |
| `PC2_URL` | `http://192.168.178.84:8000` | **Set to PC 2's LAN IP** |
| `PC2_API_KEY` | `change-me-to-something-random` | Must match PC 2's `API_KEY` |
| `PC1_API_PORT` | `8001` | Port PC 1 listens on for game-control commands from PC 2 |
| `PC1_API_KEY` | `change-me-to-something-random` | Must match PC 2's `PC1_API_KEY` |
| `THEME_VOLUME` | `0.40` | Background music volume (0.0–1.0) |
| `DUCK_VOLUME` | `0.10` | Theme volume while a SFX plays |
| `IDLE_LIGHT_INTERVAL_MS` | `12000` | Milliseconds between ambient light pulses |

### Run

```bash
python3 escape_room.py
```

Press **Ctrl+Shift+Alt+Q** or **F12 three times** to exit.

---

## GM Panel (Phone Controller)

With PC 2 running, open this URL on any phone or tablet on the same WiFi:

```
http://<PC2-IP>:8000/gm?key=candy-gm
```

PC 2 prints the exact URL in its log window on startup.

The panel provides:

| Section | Buttons |
|---------|---------|
| **Audio** | Intro, Theme, Wrong SFX, Story, Victory, Hint, Restore, Stop All |
| **Lights** | Rainbow, Suspense, Warning, Celebrate, Blackout |
| **Game Control** | Play Hint, Skip to Stage 2, Force Win, Reset Game |

Audio and game commands are proxied by PC 2 through to PC 1. Lights are handled directly by PC 2. The status bar refreshes every 3 seconds showing current stage, fail count, and DMX state.

> **Security:** set `GM_KEY` in `controller.py` to something private before your event.

---

## PC 2 — DMX Lighting Controller

Runs a FastAPI web server that receives light events from PC 1 and drives the DMX fixtures.

### Hardware

- **DMX adapter:** Enttec Open DMX USB (FTDI FT232R, `0x0403:0x6001`)
- **Fixture:** Eurolite LED PARty RGB Spot — DMX start address **1**, 6-channel mode

DMX is driven via **libftdi1** (the same library QLC+ uses), which talks directly to the FTDI chip over USB and bypasses the `ftdi_sio` kernel driver.

### System dependencies

```bash
sudo apt install python3-tk libftdi1-2
```

### Python dependencies

```bash
pip install -r requirements_pc2.txt
```

### One-time udev rule (run once, no sudo needed after)

```bash
sudo cp 99-enttec-opendmx.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Unplug and replug the Enttec adapter. After this, `controller.py` runs as a normal user.

### Configuration (`controller.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `FTDI_VENDOR` | `0x0403` | Enttec Open DMX USB vendor ID |
| `FTDI_PRODUCT` | `0x6001` | Enttec Open DMX USB product ID |
| `API_PORT` | `8000` | Port the web server listens on (PC1 events + GM panel) |
| `API_KEY` | `change-me-to-something-random` | Key PC 1 sends when calling PC 2 — must match PC 1's `PC2_API_KEY` |
| `PC1_URL` | `http://192.168.178.XX:8001` | **Set to PC 1's LAN IP** |
| `PC1_API_KEY` | `change-me-to-something-random` | Key PC 2 sends when calling PC 1 — must match PC 1's `PC1_API_KEY` |
| `GM_KEY` | `candy-gm` | **Change this** — used to access the GM phone panel |

### Fixture channel map (Eurolite LED PARty RGB Spot)

| Offset | Channel | Function |
|--------|---------|----------|
| +0 | start | Red |
| +1 | start+1 | Green |
| +2 | start+2 | Blue |
| +3 | start+3 | Master dimmer |
| +4 | start+4 | Strobe / effects |

### Run

```bash
python3 controller.py
```

The GM panel shows **DMX: ONLINE** when the adapter is detected.

### API endpoints

All write endpoints require the header `X-API-Key: <API_KEY>`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/lights/static` | Set fixture colours or raw channels |
| `POST` | `/lights/sequence` | Start a timed flash / pulse / strobe |
| `POST` | `/lights/blackout` | All channels to zero |
| `GET` | `/status` | DMX status + active sequence info |

**Example — set fixture 1 to red:**
```bash
curl -X POST http://<PC2_IP>:8000/lights/static \
  -H "X-API-Key: change-me-to-something-random" \
  -H "Content-Type: application/json" \
  -d '{"fixtures": [{"id": 1, "r": 255, "g": 0, "b": 0, "intensity": 255}]}'
```

**Example — pink pulse for 10 seconds:**
```bash
curl -X POST http://<PC2_IP>:8000/lights/sequence \
  -H "X-API-Key: change-me-to-something-random" \
  -H "Content-Type: application/json" \
  -d '{"type": "pulse", "color": [255, 105, 180], "intensity": 255, "frequency_hz": 0.5, "duration_sec": 10}'
```
