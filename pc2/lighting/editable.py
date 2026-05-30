"""
Shared editable-lighting helpers.

Translates between the low-level ``FixtureAnim`` (used by the renderer/DMX path)
and the high-level *editable* representation — a (color name, effect name,
opacity %) triple — used by the GUI editors and the JSON override files.

Both the Scene Editor (static phase scenes) and the Timeline Editor (intro cue
sequence) build on these so the on-screen controls and persisted format stay
consistent across features.
"""

from pc2.lighting.scenes import FixtureAnim

# ── Editable palettes ──────────────────────────────────────────────────────────

SCENE_COLORS: dict = {
    "Off":        (  0,   0,   0),
    "Warm White": (255, 160,  60),
    "White":      (255, 255, 255),
    "Red":        (255,   0,   0),
    "Green":      (  0, 255,   0),
    "Blue":       (  0,  60, 255),
    "Purple":     (160,   0, 220),
    "Pink":       (255,   0, 140),
    "Yellow":     (255, 190,   0),
    "Orange":     (255, 120,   0),
    "Aqua":       (  0, 200, 180),
}

# effect name → (anim_type, frequency_hz)
SCENE_EFFECTS: dict = {
    "Static":     ("static",  0.0),
    "Flash Slow": ("flash",   0.5),
    "Flash Fast": ("flash",   4.0),
    "Pulse Slow": ("pulse",   0.3),
    "Pulse Fast": ("pulse",   1.2),
    "Candle":     ("candle",  0.0),
    "Rainbow":    ("rainbow", 0.08),
}


# ── FixtureAnim ⇄ editable representation ────────────────────────────────────────

def _closest_color_name(r: int, g: int, b: int) -> str:
    best, best_d = "Off", float("inf")
    for name, (cr, cg, cb) in SCENE_COLORS.items():
        d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if d < best_d:
            best_d, best = d, name
    return best


def _closest_effect_name(anim_type: str, hz: float) -> str:
    if anim_type == "static":  return "Static"
    if anim_type == "candle":  return "Candle"
    if anim_type == "rainbow": return "Rainbow"
    if anim_type == "flash":   return "Flash Slow" if hz <= 1.0 else "Flash Fast"
    if anim_type == "pulse":   return "Pulse Slow" if hz <= 0.6 else "Pulse Fast"
    return "Static"


def fixture_anim_to_editable(anim: "FixtureAnim") -> tuple:
    """Return (color_name, effect_name, opacity_pct) for a FixtureAnim."""
    return (
        _closest_color_name(anim.r, anim.g, anim.b),
        _closest_effect_name(anim.anim_type, anim.frequency_hz),
        round(anim.intensity / 255 * 100),
    )


def editable_to_fixture_anim(fixture_id: int, color: str, effect: str,
                             opacity: int, stagger_idx: int = 0) -> "FixtureAnim":
    """Build a FixtureAnim from editor values."""
    r, g, b       = SCENE_COLORS.get(color, (0, 0, 0))
    anim_type, hz = SCENE_EFFECTS.get(effect, ("static", 0.0))
    return FixtureAnim(
        fixture_id   = fixture_id,
        anim_type    = anim_type,
        r=r, g=g, b=b,
        intensity    = round(opacity / 100 * 255),
        frequency_hz = hz if hz > 0 else 1.0,
        phase_offset = stagger_idx / 8,
    )
