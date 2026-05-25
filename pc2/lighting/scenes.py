"""
Per-fixture scene definitions for the escape room.

Fixture layout (8 fixtures):
  1-4  "warm" group — always warm white during gameplay
  5-6  "accent-A" — orange (phase 1) / purple (phase 2)
  7-8  "accent-B" — aqua; also the two that blink red on wrong answers

Animation types:
  static  — fixed colour, no movement
  flash   — hard on/off at frequency_hz
  pulse   — smooth sine-wave brightness
  rainbow — full hue rotation, phase_offset staggers fixtures across the spectrum
"""

import colorsys
import math
from dataclasses import dataclass

# ── Colour palette ────────────────────────────────────────────────────────────
_WARM_WHITE = (255, 160, 60)
_WARM_INT   = 200
_RED        = (255,   0,   0)
_GREEN      = (  0, 220,  60)
_ORANGE     = (255, 120,   0)
_AQUA       = (  0, 200, 180)
_PURPLE     = (160,   0, 220)
_OFF        = (  0,   0,   0)


# ── Data structure ────────────────────────────────────────────────────────────

@dataclass
class FixtureAnim:
    fixture_id:   int
    anim_type:    str    # "static" | "flash" | "pulse" | "rainbow"
    r:            int   = 0
    g:            int   = 0
    b:            int   = 0
    intensity:    int   = 255
    frequency_hz: float = 1.0
    phase_offset: float = 0.0  # 0.0–1.0: rainbow = hue start, pulse = wave phase


def render_fixture_anim(anim: FixtureAnim, t: float) -> tuple:
    """Return (r, g, b, intensity) for this fixture at monotonic time t."""
    if anim.anim_type == "static":
        return (anim.r, anim.g, anim.b, anim.intensity)

    if anim.anim_type == "flash":
        period = 1.0 / anim.frequency_hz
        on     = (t % period) / period < 0.5
        return (anim.r, anim.g, anim.b, anim.intensity if on else 0)

    if anim.anim_type == "pulse":
        phase = anim.phase_offset * 2 * math.pi
        val   = (math.sin(2 * math.pi * anim.frequency_hz * t + phase) + 1) / 2
        return (anim.r, anim.g, anim.b, int(anim.intensity * val))

    if anim.anim_type == "rainbow":
        hue     = (t * anim.frequency_hz + anim.phase_offset) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255), anim.intensity)

    return (anim.r, anim.g, anim.b, anim.intensity)


# ── Scene builder helpers ─────────────────────────────────────────────────────

def _s(fid, rgb, intensity=255):
    return FixtureAnim(fid, "static", *rgb, intensity)

def _f(fid, rgb, intensity=255, hz=1.0):
    return FixtureAnim(fid, "flash", *rgb, intensity, hz)

def _rb(fid, intensity=255, hz=0.08, phase=0.0):
    return FixtureAnim(fid, "rainbow", intensity=intensity, frequency_hz=hz, phase_offset=phase)


# ── Scene registry ────────────────────────────────────────────────────────────

SCENES: dict = {

    # ── Waiting ──────────────────────────────────────────────────────────────
    # Fixtures 1-4 warm white; 5-6 slow red flash (danger); 7-8 off.
    "waiting": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _f(5, _RED, 160, 0.3),
        _f(6, _RED, 160, 0.3),
        _s(7, _OFF, 0),
        _s(8, _OFF, 0),
    ],

    # ── Intro — rainbow sweep ─────────────────────────────────────────────────
    # All 8 fixtures rainbow, each offset 1/8 of the spectrum so every
    # fixture shows a different hue and they slowly cycle into each other.
    "intro": [
        _rb(i, intensity=255, hz=0.10, phase=i / 8) for i in range(1, 9)
    ],

    # ── Persistent rainbow (used after victory) ───────────────────────────────
    "rainbow": [
        _rb(i, intensity=255, hz=0.08, phase=i / 8) for i in range(1, 9)
    ],

    # ── Phase 1 — password stage ──────────────────────────────────────────────
    # Warm white on 1-4; orange on 5-6; aqua on 7-8.
    "phase1": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _ORANGE, 220),
        _s(6, _ORANGE, 220),
        _s(7, _AQUA, 220),
        _s(8, _AQUA, 220),
    ],

    # ── Phase 1 — wrong answer (2 accent-B lights flash red) ─────────────────
    "phase1_wrong": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _ORANGE, 220),
        _s(6, _ORANGE, 220),
        _f(7, _RED, 255, 4.0),
        _f(8, _RED, 255, 4.0),
    ],

    # ── Phase 1 — correct password (4 accent lights turn green) ──────────────
    "phase1_correct": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _GREEN, 255),
        _s(6, _GREEN, 255),
        _s(7, _GREEN, 255),
        _s(8, _GREEN, 255),
    ],

    # ── Phase 2 — switches stage ──────────────────────────────────────────────
    # Warm white on 1-4; purple on 5-6; aqua on 7-8.
    "phase2": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _PURPLE, 220),
        _s(6, _PURPLE, 220),
        _s(7, _AQUA, 220),
        _s(8, _AQUA, 220),
    ],

    # ── Phase 2 — wrong switches (same 2 lights flash red) ───────────────────
    "phase2_wrong": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _PURPLE, 220),
        _s(6, _PURPLE, 220),
        _f(7, _RED, 255, 4.0),
        _f(8, _RED, 255, 4.0),
    ],

    # ── Victory — 4 accent lights green for 8 s, then rainbow auto-restores ──
    "victory_green": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _GREEN, 255),
        _s(6, _GREEN, 255),
        _s(7, _GREEN, 255),
        _s(8, _GREEN, 255),
    ],
}
