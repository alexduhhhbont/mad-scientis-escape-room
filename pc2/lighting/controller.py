import threading
import time
from typing import Optional

from pc2.fixtures.library import fixture_library
from pc2.lighting.scenes import SCENES, FixtureAnim, render_fixture_anim
from pc2.lighting.sequences import SequenceJob, render_sequence


class LightingController:
    def __init__(self):
        self._lock         = threading.Lock()
        self.base_frame    = bytearray(513)
        self.base_frame[0] = 0x00
        self.dmx_online    = False
        self._gui_callback = None

        # Legacy global sequence (kept for backwards compat with raw API calls)
        self.sequence: Optional[SequenceJob] = None

        # Per-fixture scene system
        self._scene_jobs:     list  = []   # list[FixtureAnim]
        self._scene_expires:  float = 0.0  # 0.0 = permanent
        self._restore_scene:  str   = ""   # scene name to restore on expiry

    def set_callback(self, fn):
        self._gui_callback = fn

    def _notify_gui(self):
        if self._gui_callback:
            self._gui_callback()

    def is_sequence_active(self) -> bool:
        with self._lock:
            return self.sequence is not None or bool(self._scene_jobs)

    # ── Scene control ──────────────────────────────────────────────────────────

    def set_scene(self, jobs: list, duration: float = 0.0, restore: str = "") -> None:
        """Apply a per-fixture scene. duration=0 means permanent."""
        with self._lock:
            self._scene_jobs    = list(jobs)
            self._scene_expires = (time.monotonic() + duration) if duration > 0 else 0.0
            self._restore_scene = restore
            self.sequence       = None   # cancel any legacy global sequence
        self._notify_gui()

    def clear_scene(self) -> None:
        with self._lock:
            self._scene_jobs    = []
            self._scene_expires = 0.0
            self._restore_scene = ""
        self._notify_gui()

    # ── Legacy controls (raw channel / fixture / global sequence) ─────────────

    def apply_static(self, channels: dict):
        with self._lock:
            for ch, val in channels.items():
                if 1 <= ch <= 512:
                    self.base_frame[ch] = max(0, min(255, int(val)))
            self.sequence    = None
            self._scene_jobs = []
        self._notify_gui()

    def _fixture_channels(self, inst, r: int, g: int, b: int, intensity: int) -> dict:
        offsets   = fixture_library.get_role_offsets(inst.type_id)
        base      = inst.dmx_address
        role_vals = {"red": r, "green": g, "blue": b, "intensity": intensity, "strobe": 0}
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
                seq_type=seq_type, color=color, intensity=intensity,
                frequency_hz=frequency_hz,
                expires_at=time.monotonic() + duration_sec,
                prior_frame=prior,
            )
            self._scene_jobs = []   # scene takes priority; clearing sequence when scene set
        self._notify_gui()

    def blackout(self):
        with self._lock:
            self.base_frame    = bytearray(513)
            self.base_frame[0] = 0x00
            self.sequence      = None
            self._scene_jobs   = []
        self._notify_gui()

    # ── Frame rendering (called by DMX thread at ~40 Hz) ──────────────────────

    def get_frame(self) -> bytearray:
        with self._lock:
            now = time.monotonic()

            # ── Per-fixture scene ──────────────────────────────────────────────
            if self._scene_jobs:
                # Handle timed scene expiry
                if self._scene_expires and now >= self._scene_expires:
                    restore_name        = self._restore_scene
                    self._scene_expires = 0.0
                    self._restore_scene = ""
                    self._scene_jobs    = list(SCENES.get(restore_name, [])) if restore_name else []
                    self._notify_gui()

                if self._scene_jobs:
                    return self._render_scene(now)
                # Fell through (no restore scene) — drop to base frame below

            # ── Legacy global sequence ─────────────────────────────────────────
            if self.sequence:
                if now >= self.sequence.expires_at:
                    self.base_frame = self.sequence.prior_frame.copy()
                    self.sequence   = None
                    self._notify_gui()
                    return self.base_frame.copy()
                return render_sequence(self.sequence, now)

            return self.base_frame.copy()

    def _render_scene(self, t: float) -> bytearray:
        """Render per-fixture animations into a fresh DMX frame."""
        frame    = bytearray(513)
        frame[0] = 0x00
        for job in self._scene_jobs:
            inst = fixture_library.get_instance(job.fixture_id)
            if inst is None:
                continue
            r, g, b, intensity = render_fixture_anim(job, t)
            offsets = fixture_library.get_role_offsets(inst.type_id)
            base    = inst.dmx_address
            for role, off in offsets.items():
                ch = base + off
                if 1 <= ch <= 512:
                    if   role == "red":       frame[ch] = max(0, min(255, r))
                    elif role == "green":     frame[ch] = max(0, min(255, g))
                    elif role == "blue":      frame[ch] = max(0, min(255, b))
                    elif role == "intensity": frame[ch] = max(0, min(255, intensity))
                    elif role == "strobe":    frame[ch] = 0
        return frame

    # ── Status ─────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        with self._lock:
            seq      = self.sequence
            seq_info = None
            if seq:
                remaining = max(0.0, seq.expires_at - time.monotonic())
                seq_info  = {"type": seq.seq_type, "expires_in_sec": round(remaining, 1)}
            scene_info = None
            if self._scene_jobs:
                remaining  = max(0.0, self._scene_expires - time.monotonic()) if self._scene_expires else None
                scene_info = {"fixtures": len(self._scene_jobs), "expires_in_sec": round(remaining, 1) if remaining else None}
            preview = {str(ch): self.base_frame[ch] for ch in range(1, min(10, 513))}
        return {
            "dmx_streaming":      self.dmx_online,
            "active_sequence":    seq_info,
            "active_scene":       scene_info,
            "base_frame_preview": preview,
        }


controller = LightingController()
