# Mad Scientist Escape Room — System Setup

Two machines work together to run the room. **PC 1** runs the player-facing terminal (puzzle interface). **PC 2** runs the Game Master controller and drives the DMX lighting.

```
[ PC 1 — Player terminal ]  ──HTTP──▶  [ PC 2 — GM controller + DMX ]
      escape_room.py                          controller.py
                                                    │
                                              Enttec Open DMX USB
                                                    │
                                          Eurolite LED PARty RGB Spot
```

---

## PC 1 — Player Terminal

Runs a full-screen Tkinter puzzle interface locked to the desktop.

**Stage 1 — Password:** Players enter the authorization code (`CHAOS42` by default).  
**Stage 2 — Switches:** Players configure six switches in the correct combination.  
**Stage 3 — Success screen** is shown when both stages are complete.

Each failed attempt and each stage transition fires an HTTP event to PC 2 to trigger a lighting effect.

### Setup

```bash
pip install -r requirements_pc1.txt
```

### Configuration (`escape_room.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PASSWORD` | `CHAOS42` | Stage 1 password |
| `SWITCH_SOLUTION` | `[True, True, False, False, True, False]` | Correct switch states (index 0 = switch 1) |
| `PC2_URL` | `http://192.168.1.XX:8000` | **Set this to PC 2's LAN IP** |
| `PC2_API_KEY` | `change-me-to-something-random` | Must match PC 2's `API_KEY` |

### Run

```bash
python3 escape_room.py
```

Press **Ctrl+Shift+Alt+Q** or **F12 three times** to exit.

---

## PC 2 — Game Master Controller

Runs a Tkinter GM panel, a FastAPI web server (receives events from PC 1), and a DMX streaming thread.

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

### One-time udev rule (run without sudo)

```bash
sudo cp 99-enttec-opendmx.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then unplug and replug the Enttec adapter. After this, `controller.py` runs as a normal user.

### Configuration (`controller.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `FTDI_VENDOR` | `0x0403` | Enttec Open DMX USB vendor ID |
| `FTDI_PRODUCT` | `0x6001` | Enttec Open DMX USB product ID |
| `API_PORT` | `8000` | Port the web server listens on |
| `API_KEY` | `change-me-to-something-random` | Shared secret — set on both PCs |
| `FIXTURES` | `{1: 1, 2: 10, 3: 19}` | Fixture ID → DMX start channel |

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

**Example — green pulse for 10 seconds:**
```bash
curl -X POST http://<PC2_IP>:8000/lights/sequence \
  -H "X-API-Key: change-me-to-something-random" \
  -H "Content-Type: application/json" \
  -d '{"type": "pulse", "color": [0, 255, 65], "intensity": 255, "frequency_hz": 0.5, "duration_sec": 10}'
```
