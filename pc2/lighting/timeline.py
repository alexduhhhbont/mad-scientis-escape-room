"""
Back-compat shim for the intro lighting timeline.

The timeline data model, player and the editable intro definition now live in
pc2/lighting/timelines.py. These thin wrappers preserve the original
start/cancel API used by the API layer and game flow.
"""

from pc2.lighting.timelines import TIMELINES, timeline_player


def start_intro_timeline() -> None:
    timeline_player.start(TIMELINES["intro"])


def cancel_intro_timeline() -> None:
    timeline_player.cancel()
