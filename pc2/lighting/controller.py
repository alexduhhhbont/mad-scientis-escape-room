import threading
import time
from typing import Optional

from pc2.fixtures.library import fixture_library
from pc2.lighting.sequences import SequenceJob, render_sequence


class LightingController:
    def __init__(self):
        self._lock         = threading.Lock()
        self.base_frame    = bytearray(513)
        self.base_frame[0] = 0x00
        self.sequence: Optional[SequenceJob] = None
        self.dmx_online    = False
        self._gui_callback = None

    def set_callback(self, fn):
        self._gui_callback = fn

    def _notify_gui(self):
        if self._gui_callback:
            self._gui_callback()

    def is_sequence_active(self) -> bool:
        with self._lock:
            return self.sequence is not None

    def apply_static(self, channels: dict):
        with self._lock:
            for ch, val in channels.items():
                if 1 <= ch <= 512:
                    self.base_frame[ch] = max(0, min(255, int(val)))
            self.sequence = None
        self._notify_gui()

    def _fixture_channels(self, inst, r: int, g: int, b: int, intensity: int) -> dict:
        offsets   = fixture_library.get_role_offsets(inst.type_id)
        base      = inst.dmx_address
        role_vals = {"red": r, "green": g, "blue": b,
                     "intensity": intensity, "strobe": 0}
        return {base + off: role_vals[role]
                for role, off in offsets.items() if role in role_vals}

    def apply_fixture(self, fixture_id: int, r: int, g: int, b: int, intensity: int = 255):
        inst = fixture_library.get_instance(fixture_id)
        if inst is None:
            return
        self.apply_static(self._fixture_channels(inst, r, g, b, intensity))

    def apply_all_fixtures(self, r: int, g: int, b: int, intensity: int = 255):
        channels = {}
        for inst in fixture_library.get_instances_snapshot():
            channels.update(self._fixture_channels(inst, r, g, b, intensity))
        self.apply_static(channels)

    def start_sequence(self, seq_type: str, color: tuple, intensity: int,
                       frequency_hz: float, duration_sec: float):
        with self._lock:
            prior = self.base_frame.copy()
            self.sequence = SequenceJob(
                seq_type=seq_type,
                color=color,
                intensity=intensity,
                frequency_hz=frequency_hz,
                expires_at=time.monotonic() + duration_sec,
                prior_frame=prior,
            )
        self._notify_gui()

    def blackout(self):
        with self._lock:
            self.base_frame    = bytearray(513)
            self.base_frame[0] = 0x00
            self.sequence      = None
        self._notify_gui()

    def get_frame(self) -> bytearray:
        with self._lock:
            seq = self.sequence
            if seq is None:
                return self.base_frame.copy()
            now = time.monotonic()
            if now >= seq.expires_at:
                self.base_frame = seq.prior_frame.copy()
                self.sequence   = None
                self._notify_gui()
                return self.base_frame.copy()
            return render_sequence(seq, now)

    def get_status(self) -> dict:
        with self._lock:
            seq      = self.sequence
            seq_info = None
            if seq:
                remaining = max(0.0, seq.expires_at - time.monotonic())
                seq_info  = {"type": seq.seq_type, "expires_in_sec": round(remaining, 1)}
            preview = {str(ch): self.base_frame[ch] for ch in range(1, min(10, 513))}
        return {
            "dmx_streaming":      self.dmx_online,
            "active_sequence":    seq_info,
            "base_frame_preview": preview,
        }


controller = LightingController()
