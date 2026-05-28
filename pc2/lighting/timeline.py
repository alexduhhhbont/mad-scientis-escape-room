"""
Intro lighting timeline — fires per-fixture scene cues on a schedule
that is synchronised with the intro audio track.

Call start_intro_timeline() when the intro begins.
Call cancel_intro_timeline() to abort (e.g. on reset).
"""

import threading
from pc2.lighting.controller import controller
from pc2.lighting.scenes import SCENES

# (time_offset_seconds, scene_name, fade_sec)
# The 66s→70s transition is two consecutive cues: instant snap to intro_66
# then an immediate 4-second fade to phase1 so it arrives at t=70s.
_CUES = [
    ( 0.0,  "intro_0",    1.0),
    (12.0,  "intro_12",   1.0),
    (16.0,  "intro_16",   0.5),
    (17.0,  "intro_17",   0.5),
    (18.0,  "intro_18",   0.5),
    (20.0,  "intro_20",   1.0),
    (27.0,  "intro_27",   1.0),
    (35.0,  "intro_35",   1.0),
    (40.0,  "intro_40",   1.0),
    (45.0,  "intro_45",   1.0),
    (54.0,  "intro_54",   1.0),
    (59.0,  "intro_59",   0.5),
    (59.5,  "intro_59_5", 0.3),
    (60.0,  "intro_60",   0.3),
    (66.0,  "intro_66",   0.5),   # snap to 66s colours
    (66.1,  "phase1",     3.9),   # immediately begin 3.9s fade → arrives at 70s
]

_timers: list = []
_lock = threading.Lock()


def start_intro_timeline() -> None:
    cancel_intro_timeline()
    with _lock:
        for offset, scene_name, fade in _CUES:
            jobs = list(SCENES[scene_name])
            t = threading.Timer(offset, _fire, args=(jobs, fade))
            t.daemon = True
            t.start()
            _timers.append(t)


def cancel_intro_timeline() -> None:
    with _lock:
        for t in _timers:
            t.cancel()
        _timers.clear()


def _fire(jobs: list, fade: float) -> None:
    controller.set_scene(jobs, fade_sec=fade)
