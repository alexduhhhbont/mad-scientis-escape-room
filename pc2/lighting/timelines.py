"""
Time-based lighting timelines — ordered cue sequences fired on a schedule.

A :class:`Timeline` is an ordered list of :class:`TimelineCue`s. Each cue fires
at ``time`` seconds from the start, crossfading into its target over ``fade``
seconds. A cue's target is either a per-fixture list of ``FixtureAnim``
(``anims``) or a *live reference* to a named scene in ``SCENES`` (``scene_ref``)
— the latter lets the intro hand off to the editable ``phase1`` scene so Scene
Editor edits flow through automatically.

The :class:`TimelinePlayer` singleton (``timeline_player``) schedules cues with
``threading.Timer``. If ``Timeline.loop`` is set it re-arms the whole timeline
after ``effective_length()`` seconds.

The default ``intro`` timeline below is a verbatim translation of the previously
hardcoded cue list — same timecodes, fades and per-fixture states — so the intro
plays identically with no configuration. Edits are persisted to
``timeline_overrides.json`` (created only on first save) and ``reset_timeline_to_defaults``
restores this faithful copy.
"""

import copy
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pc2.lighting.controller import controller
from pc2.lighting.editable import (
    SCENE_COLORS, fixture_anim_to_editable, editable_to_fixture_anim,
)
from pc2.lighting.scenes import SCENES, FixtureAnim


# ── Data model ──────────────────────────────────────────────────────────────────

@dataclass
class TimelineCue:
    time:      float                 # offset seconds from timeline start
    fade:      float                 # crossfade duration into this cue
    label:     str  = ""
    scene_ref: str  = ""             # if set → resolve SCENES[scene_ref] live at fire time
    anims:     list = field(default_factory=list)   # list[FixtureAnim], used when scene_ref == ""


@dataclass
class Timeline:
    name:   str
    loop:   bool  = False
    length: float = 0.0              # 0 → derive from last cue (see effective_length)
    cues:   list  = field(default_factory=list)      # list[TimelineCue]

    def effective_length(self) -> float:
        """Loop point: the explicit length, or the last cue's time + fade."""
        if self.length and self.length > 0:
            return self.length
        if not self.cues:
            return 0.0
        return max(c.time + c.fade for c in self.cues)

    def sorted_cues(self) -> list:
        return sorted(self.cues, key=lambda c: c.time)


# ── Player ──────────────────────────────────────────────────────────────────────

class TimelinePlayer:
    """Schedules a Timeline's cues via threading.Timer; optionally loops."""

    def __init__(self):
        self._lock   = threading.Lock()
        self._timers: list = []
        self._active: Optional[Timeline] = None

    def start(self, timeline: Timeline) -> None:
        with self._lock:
            self._cancel_locked()
            self._active = timeline
            for cue in timeline.cues:
                timer = threading.Timer(max(0.0, cue.time), self._fire, args=(cue,))
                timer.daemon = True
                timer.start()
                self._timers.append(timer)
            if timeline.loop:
                length = timeline.effective_length()
                if length > 0:
                    rearm = threading.Timer(length, self._loop_restart, args=(timeline,))
                    rearm.daemon = True
                    rearm.start()
                    self._timers.append(rearm)

    def cancel(self) -> None:
        with self._lock:
            self._cancel_locked()
            self._active = None

    def is_running(self) -> bool:
        with self._lock:
            return self._active is not None and bool(self._timers)

    # ── internals ──
    def _cancel_locked(self) -> None:
        for t in self._timers:
            t.cancel()
        self._timers.clear()

    def _loop_restart(self, timeline: Timeline) -> None:
        # Runs in a finished Timer thread (not holding the lock), so start()
        # can safely re-acquire it.
        self.start(timeline)

    def _fire(self, cue: TimelineCue) -> None:
        jobs = SCENES.get(cue.scene_ref, []) if cue.scene_ref else cue.anims
        controller.set_scene(list(jobs), fade_sec=cue.fade)


timeline_player = TimelinePlayer()


# ── Default intro timeline (verbatim translation of the old hardcoded cues) ──────

# Colour palette (all drawn from the shared editable palette)
_WW     = SCENE_COLORS["Warm White"]
_RED    = SCENE_COLORS["Red"]
_GREEN  = SCENE_COLORS["Green"]
_ORANGE = SCENE_COLORS["Orange"]
_AQUA   = SCENE_COLORS["Aqua"]
_PINK   = SCENE_COLORS["Pink"]
_YELLOW = SCENE_COLORS["Yellow"]
_WHITE  = SCENE_COLORS["White"]
_OFF    = SCENE_COLORS["Off"]

# Brightness levels
_W50      = 128   # 50% warm white
_W20      =  51   # 20% dimmed accents
_ACC      = 220   # standard accent intensity
_WARM_INT = 200   # standard warm-white intensity


def _s(fid, rgb, intensity=255):
    return FixtureAnim(fid, "static", *rgb, intensity)

def _f(fid, rgb, intensity=255, hz=1.0):
    return FixtureAnim(fid, "flash", *rgb, intensity, hz)

def _p(fid, rgb, intensity=255, hz=1.0, phase=0.0):
    return FixtureAnim(fid, "pulse", *rgb, intensity, hz, phase)

def _rb(fid, intensity=255, hz=0.08, phase=0.0):
    return FixtureAnim(fid, "rainbow", intensity=intensity, frequency_hz=hz, phase_offset=phase)


# (time, fade, label, scene_ref, anims) — mirrors the previous _CUES + intro_* scenes
_INTRO_CUES = [
    TimelineCue(0.0, 1.0, "Pink chase", anims=[
        _p(1, _PINK, _ACC, hz=0.4, phase=0.00),
        _p(2, _PINK, _ACC, hz=0.4, phase=0.25),
        _p(3, _PINK, _ACC, hz=0.4, phase=0.50),
        _p(4, _PINK, _ACC, hz=0.4, phase=0.75),
        _s(5, _OFF, 0), _s(6, _OFF, 0), _s(7, _OFF, 0), _s(8, _OFF, 0),
    ]),
    TimelineCue(12.0, 1.0, "Fill 1-5", anims=[
        _s(1, _WW, _WARM_INT), _s(2, _WW, _WARM_INT), _s(3, _WW, _WARM_INT),
        _s(4, _WW, _WARM_INT), _s(5, _WW, _WARM_INT),
        _s(6, _OFF, 0), _s(7, _OFF, 0), _s(8, _OFF, 0),
    ]),
    TimelineCue(16.0, 0.5, "Fill 1-6", anims=[
        _s(1, _WW, _WARM_INT), _s(2, _WW, _WARM_INT), _s(3, _WW, _WARM_INT),
        _s(4, _WW, _WARM_INT), _s(5, _WW, _WARM_INT), _s(6, _WW, _WARM_INT),
        _s(7, _OFF, 0), _s(8, _OFF, 0),
    ]),
    TimelineCue(17.0, 0.5, "Fill 1-7", anims=[
        _s(1, _WW, _WARM_INT), _s(2, _WW, _WARM_INT), _s(3, _WW, _WARM_INT),
        _s(4, _WW, _WARM_INT), _s(5, _WW, _WARM_INT), _s(6, _WW, _WARM_INT),
        _s(7, _WW, _WARM_INT), _s(8, _OFF, 0),
    ]),
    TimelineCue(18.0, 0.5, "All warm", anims=[
        _s(i, _WW, _WARM_INT) for i in range(1, 9)
    ]),
    TimelineCue(20.0, 1.0, "Green/Pink pulse", anims=[
        _s(1, _WW, _WARM_INT), _s(2, _WW, _WARM_INT), _s(3, _WW, _WARM_INT),
        _s(4, _WW, _WARM_INT), _s(5, _WW, _WARM_INT), _s(6, _WW, _WARM_INT),
        _p(7, _GREEN, _ACC, hz=0.25, phase=0.0),
        _p(8, _PINK,  _ACC, hz=0.25, phase=0.5),
    ]),
    TimelineCue(27.0, 1.0, "Red blink", anims=[
        _s(1, _WW, _WARM_INT), _s(2, _WW, _WARM_INT), _s(3, _WW, _WARM_INT),
        _s(4, _WW, _WARM_INT), _s(5, _WW, _WARM_INT), _s(6, _WW, _WARM_INT),
        _s(7, _WW, _WARM_INT), _f(8, _RED, _ACC, hz=0.4),
    ]),
    TimelineCue(35.0, 1.0, "Yellow/Aqua accents", anims=[
        _s(1, _WW, _WARM_INT), _s(2, _WW, _WARM_INT), _s(3, _WW, _WARM_INT),
        _s(4, _WW, _WARM_INT), _s(5, _YELLOW, _ACC),
        _s(6, _WW, _WARM_INT), _s(7, _WW, _WARM_INT), _s(8, _AQUA, _ACC),
    ]),
    TimelineCue(40.0, 1.0, "Colour accents", anims=[
        _s(1, _WW, _W50), _s(2, _WW, _W50), _s(3, _WW, _W50), _s(4, _WW, _W50),
        _s(5, _YELLOW, _ACC), _s(6, _GREEN, _ACC), _s(7, _ORANGE, _ACC), _s(8, _AQUA, _ACC),
    ]),
    TimelineCue(45.0, 1.0, "Spotlight 7", anims=[
        _s(1, _WW, _W50), _s(2, _WW, _W50), _s(3, _WW, _W50), _s(4, _WW, _W50),
        _s(5, _YELLOW, _W20), _s(6, _GREEN, _W20), _s(7, _WHITE, 255), _s(8, _AQUA, _W20),
    ]),
    TimelineCue(54.0, 1.0, "Dim warm + spot 7", anims=[
        _s(1, _WW, _W50), _s(2, _WW, _W50), _s(3, _WW, _W50), _s(4, _WW, _W50),
        _s(5, _WW, _W20), _s(6, _WW, _W20), _s(7, _WHITE, 255), _s(8, _WW, _W20),
    ]),
    TimelineCue(59.0, 0.5, "Drop 8", anims=[
        _s(1, _WW, _W50), _s(2, _WW, _W50), _s(3, _WW, _W50), _s(4, _WW, _W50),
        _s(5, _WW, _W20), _s(6, _WW, _W20), _s(7, _WHITE, 255), _s(8, _OFF, 0),
    ]),
    TimelineCue(59.5, 0.3, "Narrow to 6-7", anims=[
        _s(1, _WW, _W50), _s(2, _WW, _W50), _s(3, _WW, _W50), _s(4, _WW, _W50),
        _s(5, _OFF, 0), _s(6, _WW, _W20), _s(7, _WHITE, 255), _s(8, _OFF, 0),
    ]),
    TimelineCue(60.0, 0.3, "Rainbow burst 7", anims=[
        _s(1, _WW, _W50), _s(2, _WW, _W50), _s(3, _WW, _W50), _s(4, _WW, _W50),
        _s(5, _OFF, 0), _s(6, _OFF, 0), _rb(7, intensity=_ACC, hz=0.6), _s(8, _OFF, 0),
    ]),
    TimelineCue(66.0, 0.5, "Green reveal", anims=[
        _s(1, _WW, _W50), _s(2, _WW, _W50), _s(3, _WW, _W50), _s(4, _WW, _W50),
        _s(5, _GREEN, _ACC), _s(6, _GREEN, _ACC), _s(7, _WW, _WARM_INT), _s(8, _GREEN, _ACC),
    ]),
    # Immediately begin a 3.9s fade to the live phase1 scene → arrives at t=70s.
    TimelineCue(66.1, 3.9, "→ Phase 1", scene_ref="phase1"),
]

_DEFAULT_TIMELINES: dict = {
    "intro": Timeline(name="intro", loop=False, length=70.0, cues=_INTRO_CUES),
}

# Live registry (mutated by the editor / overrides). Deep-copied so edits never
# touch the factory defaults used by reset.
TIMELINES: dict = {
    name: copy.deepcopy(tl) for name, tl in _DEFAULT_TIMELINES.items()
}


# ── Persistence (timeline_overrides.json) ────────────────────────────────────────

_OVERRIDES_FILE = Path(__file__).parent.parent.parent / "timeline_overrides.json"


def _cue_to_dict(cue: TimelineCue) -> dict:
    d = {
        "time":      cue.time,
        "fade":      cue.fade,
        "label":     cue.label,
        "scene_ref": cue.scene_ref,
    }
    if not cue.scene_ref:
        fixtures = []
        for a in cue.anims:
            color, effect, opacity = fixture_anim_to_editable(a)
            fixtures.append({
                "fixture_id": a.fixture_id,
                "color":      color,
                "effect":     effect,
                "opacity":    opacity,
            })
        d["fixtures"] = fixtures
    return d


def _cue_from_dict(d: dict) -> TimelineCue:
    scene_ref = d.get("scene_ref", "")
    anims = []
    if not scene_ref:
        anims = [
            editable_to_fixture_anim(
                f["fixture_id"], f["color"], f["effect"], f["opacity"], stagger_idx=i,
            )
            for i, f in enumerate(d.get("fixtures", []))
        ]
    return TimelineCue(
        time      = float(d.get("time", 0.0)),
        fade      = float(d.get("fade", 0.0)),
        label     = d.get("label", ""),
        scene_ref = scene_ref,
        anims     = anims,
    )


def save_timeline_overrides() -> None:
    """Persist all editable timelines to timeline_overrides.json."""
    data = {}
    for name, tl in TIMELINES.items():
        data[name] = {
            "loop":   tl.loop,
            "length": tl.length,
            "cues":   [_cue_to_dict(c) for c in tl.sorted_cues()],
        }
    with open(_OVERRIDES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_timeline_overrides() -> None:
    """Load timeline_overrides.json and apply to the live TIMELINES registry."""
    if not _OVERRIDES_FILE.exists():
        return
    try:
        with open(_OVERRIDES_FILE) as f:
            data = json.load(f)
        for name, entry in data.items():
            if name not in TIMELINES:
                continue
            TIMELINES[name] = Timeline(
                name   = name,
                loop   = bool(entry.get("loop", False)),
                length = float(entry.get("length", 0.0)),
                cues   = [_cue_from_dict(c) for c in entry.get("cues", [])],
            )
    except Exception as exc:
        print(f"[timelines] Failed to load overrides: {exc}")


def reset_timeline_to_defaults(name: str) -> None:
    """Restore a timeline to its hardcoded factory default."""
    if name in _DEFAULT_TIMELINES:
        TIMELINES[name] = copy.deepcopy(_DEFAULT_TIMELINES[name])
