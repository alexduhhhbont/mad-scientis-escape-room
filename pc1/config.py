import os

# ─── Game ───────────────────────────────────────────
PASSWORD        = "CHAOS42"
ADMIN_COMBO     = "<Control-Shift-Alt-q>"
TITLE           = "WONKY'S SNOEPFABRIEK CONTROLESYSTEEM v1.0"

SWITCH_SOLUTION = [True, True, False, False, True, False]

SWITCH_LABELS = [
    "SUIKERPOMP",
    "CHOCOLADEVAT",
    "GUMMIVORM",
    "KARAMELMIXER",
    "HAGELSLAG",
    "VERPAKKING",
]

FLAVOR_LINES = [
    "SUIKERNIVEAU: MAXIMAAL",
    "GUMMIBEREN: KOKEN",
    "CHOCOLADESTROOM: ACTIEF",
    "LOLLY BATCH: GEREED",
    "HAGELSLAG TELLING: 1.000.000",
]

FAIL_MSG    = "⚠  VERKEERDE CODE — DE MACHINE IS IN DE WAR!"
SWITCH_FAIL = "⚠  VERKEERDE HENDELS — CHOCOLADE OVERSTROMING!"

# ─── PC2 / Lights ───────────────────────────────────
PC2_URL     = "http://192.168.178.84:8000"
PC2_API_KEY = "change-me-to-something-random"

# ─── PC1 Game Control API ───────────────────────────
PC1_API_PORT = 8001
PC1_API_KEY  = "change-me-to-something-random"

# ─── Audio ──────────────────────────────────────────
AUDIO_DIR          = "audio"
AUDIO_INTRO        = os.path.join(AUDIO_DIR, "intro.wav")
AUDIO_MAIN_THEME   = os.path.join(AUDIO_DIR, "theme.mp3")
AUDIO_WRONG        = os.path.join(AUDIO_DIR, "wrong.wav")
AUDIO_STAGE1_STORY = os.path.join(AUDIO_DIR, "stage1_story.wav")
AUDIO_VICTORY      = os.path.join(AUDIO_DIR, "victory.wav")
AUDIO_HINT         = os.path.join(AUDIO_DIR, "hint.wav")

THEME_VOLUME = 0.40
DUCK_VOLUME  = 0.10
SFX_VOLUME   = 0.90

# ─── Idle lights ────────────────────────────────────
IDLE_LIGHT_INTERVAL_MS = 12_000

# ─── Colour palette ─────────────────────────────────
BG         = "#1a0030"
BG_PANEL   = "#2a0045"
BG_HEADER  = "#3d0060"
PINK       = "#ff69b4"
YELLOW     = "#ffd700"
PURPLE     = "#cc44ff"
ORANGE     = "#ff8c00"
WHITE      = "#fff0ff"
DIM        = "#884488"
BORDER     = "#8800cc"
BTN_OFF_BG = "#3d0060"
BTN_OFF_FG = "#aa55cc"
BTN_ON_BG  = "#cc0077"
BTN_ON_FG  = "#ffffff"
SCAN_LINE  = "#220033"
