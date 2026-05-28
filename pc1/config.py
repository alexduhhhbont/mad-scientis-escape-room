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
PC2_URL     = "http://10.0.0.108:8000"
PC2_API_KEY = "change-me-to-something-random"

# ─── PC1 Game Control API ───────────────────────────
PC1_API_PORT = 8001
PC1_API_KEY  = "change-me-to-something-random"

# ─── Intro video ────────────────────────────────────
INTRO_VIDEO = "audio/intro.mp4"   # relative to cwd; set to "" to always use animated fallback

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
