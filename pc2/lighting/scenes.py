"""
Per-fixture scene definitions for the escape room.

Fixture layout (8 fixtures):
  1-4  "warm" group — always warm white during gameplay
  5-6  "accent-A"
  7-8  "accent-B"

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
_WARM_WHITE = (255, 160,  60)
_WARM_INT   = 200
_RED        = (255,   0,   0)
_GREEN      = (  0, 220,  60)
_ORANGE     = (255, 120,   0)
_AQUA       = (  0, 200, 180)
_PURPLE     = (160,   0, 220)
_PINK       = (255,   0, 140)
_YELLOW     = (255, 190,   0)
_BLUE       = (  0,  60, 255)
_WHITE      = (255, 255, 255)
_OFF        = (  0,   0,   0)

# ── Intro brightness levels ───────────────────────────────────────────────────
_W50 = 128   # 50% of max — ambient warm-white from intro cue 40s onwards
_W20 =  51   # 20% of max — dimmed accents (cues 45s–59s)
_ACC = 220   # standard accent intensity


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

def _p(fid, rgb, intensity=255, hz=1.0, phase=0.0):
    return FixtureAnim(fid, "pulse", *rgb, intensity, hz, phase)

def _rb(fid, intensity=255, hz=0.08, phase=0.0):
    return FixtureAnim(fid, "rainbow", intensity=intensity, frequency_hz=hz, phase_offset=phase)


# ── Scene registry ────────────────────────────────────────────────────────────

SCENES: dict = {

    # ── Waiting ──────────────────────────────────────────────────────────────
    # 1-3: warm white; 4: pink accent; 5-8: off
    "waiting": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _PINK,       _ACC),
        _s(5, _OFF,        0),
        _s(6, _OFF,        0),
        _s(7, _OFF,        0),
        _s(8, _OFF,        0),
    ],

    # ── Intro (legacy fallback — API intercepts "intro" to start timeline) ────
    "intro": [
        _rb(i, intensity=255, hz=0.10, phase=i / 8) for i in range(1, 9)
    ],

    # ── Intro timeline cue scenes ─────────────────────────────────────────────
    # Fired in sequence by pc2/lighting/timeline.py

    # t=0s: pink circles through 1-4 (staggered pulse), 5-8 off
    "intro_0": [
        _p(1, _PINK, _ACC, hz=0.4, phase=0.00),
        _p(2, _PINK, _ACC, hz=0.4, phase=0.25),
        _p(3, _PINK, _ACC, hz=0.4, phase=0.50),
        _p(4, _PINK, _ACC, hz=0.4, phase=0.75),
        _s(5, _OFF,  0),
        _s(6, _OFF,  0),
        _s(7, _OFF,  0),
        _s(8, _OFF,  0),
    ],

    # t=12s: 1-5 warm white, 6-8 off
    "intro_12": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _WARM_WHITE, _WARM_INT),
        _s(6, _OFF,        0),
        _s(7, _OFF,        0),
        _s(8, _OFF,        0),
    ],

    # t=16s: 1-6 warm white, 7-8 off
    "intro_16": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _WARM_WHITE, _WARM_INT),
        _s(6, _WARM_WHITE, _WARM_INT),
        _s(7, _OFF,        0),
        _s(8, _OFF,        0),
    ],

    # t=17s: 1-7 warm white, 8 off
    "intro_17": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _WARM_WHITE, _WARM_INT),
        _s(6, _WARM_WHITE, _WARM_INT),
        _s(7, _WARM_WHITE, _WARM_INT),
        _s(8, _OFF,        0),
    ],

    # t=18s: all 8 warm white
    "intro_18": [
        _s(i, _WARM_WHITE, _WARM_INT) for i in range(1, 9)
    ],

    # t=20s: 1-6 warm white; 7 green ↔ 8 pink slow alternate pulse
    "intro_20": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _WARM_WHITE, _WARM_INT),
        _s(6, _WARM_WHITE, _WARM_INT),
        _p(7, _GREEN, _ACC, hz=0.25, phase=0.0),
        _p(8, _PINK,  _ACC, hz=0.25, phase=0.5),
    ],

    # t=27s: 1-7 warm white; 8 red slow blink
    "intro_27": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _WARM_WHITE, _WARM_INT),
        _s(6, _WARM_WHITE, _WARM_INT),
        _s(7, _WARM_WHITE, _WARM_INT),
        _f(8, _RED,        _ACC, hz=0.4),
    ],

    # t=35s: 1-4 warm white; 5 yellow; 6-7 warm white; 8 aqua
    "intro_35": [
        _s(1, _WARM_WHITE, _WARM_INT),
        _s(2, _WARM_WHITE, _WARM_INT),
        _s(3, _WARM_WHITE, _WARM_INT),
        _s(4, _WARM_WHITE, _WARM_INT),
        _s(5, _YELLOW,     _ACC),
        _s(6, _WARM_WHITE, _WARM_INT),
        _s(7, _WARM_WHITE, _WARM_INT),
        _s(8, _AQUA,       _ACC),
    ],

    # t=40s: 1-4 warm white 50%; 5 yellow; 6 green; 7 orange; 8 aqua
    "intro_40": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _YELLOW,     _ACC),
        _s(6, _GREEN,      _ACC),
        _s(7, _ORANGE,     _ACC),
        _s(8, _AQUA,       _ACC),
    ],

    # t=45s: 1-4 warm white 50%; 5 yellow 20%; 6 green 20%; 7 white 100%; 8 aqua 20%
    "intro_45": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _YELLOW,     _W20),
        _s(6, _GREEN,      _W20),
        _s(7, _WHITE,      255),
        _s(8, _AQUA,       _W20),
    ],

    # t=54s: 1-4 warm white 50%; 5-6 warm white 20%; 7 white 100%; 8 warm white 20%
    "intro_54": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _WARM_WHITE, _W20),
        _s(6, _WARM_WHITE, _W20),
        _s(7, _WHITE,      255),
        _s(8, _WARM_WHITE, _W20),
    ],

    # t=59s: same as 54s but 8 off
    "intro_59": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _WARM_WHITE, _W20),
        _s(6, _WARM_WHITE, _W20),
        _s(7, _WHITE,      255),
        _s(8, _OFF,        0),
    ],

    # t=59.5s: 5 off, 6 warm white 20%, 7 white 100%, 8 off
    "intro_59_5": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _OFF,        0),
        _s(6, _WARM_WHITE, _W20),
        _s(7, _WHITE,      255),
        _s(8, _OFF,        0),
    ],

    # t=60s: 1-4 warm white 50%; 5-6 off; 7 fast rainbow; 8 off
    "intro_60": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _OFF,        0),
        _s(6, _OFF,        0),
        _rb(7, intensity=_ACC, hz=0.6),
        _s(8, _OFF,        0),
    ],

    # t=66s: 1-4 warm white 50%; 5-6 green; 7 warm white; 8 green
    # (start of 4s fade to phase1)
    "intro_66": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _GREEN,      _ACC),
        _s(6, _GREEN,      _ACC),
        _s(7, _WARM_WHITE, _WARM_INT),
        _s(8, _GREEN,      _ACC),
    ],

    # ── Persistent rainbow (used after victory) ───────────────────────────────
    "rainbow": [
        _rb(i, intensity=255, hz=0.08, phase=i / 8) for i in range(1, 9)
    ],

    # ── Phase 1 — password stage (= intro t=70s) ──────────────────────────────
    # 1-4 warm white 50%; 5 warm white; 6 pink; 7 blue; 8 warm white
    "phase1": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _WARM_WHITE, _WARM_INT),
        _s(6, _PINK,       _ACC),
        _s(7, _BLUE,       _ACC),
        _s(8, _WARM_WHITE, _WARM_INT),
    ],

    # ── Phase 1 — wrong answer (7 and 8 flash red) ───────────────────────────
    "phase1_wrong": [
        _s(1, _WARM_WHITE, _W50),
        _s(2, _WARM_WHITE, _W50),
        _s(3, _WARM_WHITE, _W50),
        _s(4, _WARM_WHITE, _W50),
        _s(5, _WARM_WHITE, _WARM_INT),
        _s(6, _PINK,       _ACC),
        _f(7, _RED,        255, 4.0),
        _f(8, _RED,        255, 4.0),
    ],

    # ── Phase 1 — correct password (accent lights flash green) ───────────────
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
        _s(7, _AQUA,   220),
        _s(8, _AQUA,   220),
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

    # ── Victory — accent lights green for 8 s, then rainbow auto-restores ────
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
