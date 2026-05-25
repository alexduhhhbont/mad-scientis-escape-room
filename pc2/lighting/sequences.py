import math
from dataclasses import dataclass

from pc2.fixtures.library import fixture_library


@dataclass
class SequenceJob:
    seq_type:     str        # "flash" | "pulse" | "strobe"
    color:        tuple      # (r, g, b)
    intensity:    int        # 0-255 master level
    frequency_hz: float
    expires_at:   float      # time.monotonic() deadline
    prior_frame:  bytearray  # restored when sequence ends


def render_sequence(seq: SequenceJob, t: float) -> bytearray:
    frame       = bytearray(513)
    r0, g0, b0  = seq.color
    base_scale  = seq.intensity / 255

    if seq.seq_type in ("flash", "strobe"):
        period = 1.0 / seq.frequency_hz
        on     = (t % period) / period < 0.5
        scale  = base_scale if on else 0.0
    elif seq.seq_type == "pulse":
        val   = (math.sin(2 * math.pi * seq.frequency_hz * t) + 1) / 2
        scale = base_scale * val
    else:
        scale = base_scale

    dimmer = int(seq.intensity * scale)
    for inst in fixture_library.get_instances_snapshot():
        offsets = fixture_library.get_role_offsets(inst.type_id)
        base    = inst.dmx_address
        for role, off in offsets.items():
            ch = base + off
            if   role == "red":       frame[ch] = r0
            elif role == "green":     frame[ch] = g0
            elif role == "blue":      frame[ch] = b0
            elif role == "intensity": frame[ch] = dimmer
            elif role == "strobe":    frame[ch] = 0

    return frame
