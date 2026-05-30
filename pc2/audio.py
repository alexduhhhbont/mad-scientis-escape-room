import os
import time
import threading

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False
    print("[Audio] pygame not installed — audio disabled.  Run: pip install pygame")

try:
    import requests as _requests
except ImportError:
    _requests = None

from pc2.config import (
    AUDIO_WAITING, AUDIO_INTRO,
    AUDIO_PHASE1_THEME,
    AUDIO_PHASE2_STORY, AUDIO_PHASE2_THEME,
    AUDIO_PHASE3_STORY, AUDIO_PHASE3_THEME,
    AUDIO_VICTORY, AUDIO_WRONG, AUDIO_HINT,
    STORY_VOLUME, THEME_VOLUME, DUCK_VOLUME, SFX_VOLUME,
    PC1_URL, PC1_API_KEY,
)


class AudioManager:
    def __init__(self):
        self._ok = False
        self._current_theme = AUDIO_PHASE1_THEME
        if not PYGAME_OK:
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.set_num_channels(4)
            self._sfx_ch   = pygame.mixer.Channel(1)
            self._story_ch = pygame.mixer.Channel(2)
            self._ok = True
        except Exception as e:
            print(f"[Audio] mixer init failed: {e}")

    def _load(self, path):
        if not self._ok:
            return None
        if not os.path.exists(path):
            print(f"[Audio] file not found: {path}")
            return None
        try:
            return pygame.mixer.Sound(path)
        except Exception as e:
            print(f"[Audio] load error {path}: {e}")
            return None

    # ── Theme helpers ────────────────────────────────────────────────────────────

    def _start_theme(self, path):
        if not self._ok:
            return
        if not os.path.exists(path):
            print(f"[Audio] theme not found: {path}")
            return
        try:
            self._current_theme = path
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(THEME_VOLUME)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"[Audio] theme error: {e}")

    def _unduck(self):
        if self._ok:
            pygame.mixer.music.set_volume(THEME_VOLUME)

    # ── Waiting ──────────────────────────────────────────────────────────────────

    def play_waiting(self):
        if not self._ok:
            return
        if not os.path.exists(AUDIO_WAITING):
            print(f"[Audio] waiting not found: {AUDIO_WAITING}")
            return
        try:
            pygame.mixer.music.load(AUDIO_WAITING)
            pygame.mixer.music.set_volume(THEME_VOLUME)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"[Audio] waiting error: {e}")

    # ── Intro ────────────────────────────────────────────────────────────────────

    def play_intro(self):
        if not self._ok:
            return
        pygame.mixer.music.stop()
        snd = self._load(AUDIO_INTRO)
        if snd:
            self._sfx_ch.set_volume(STORY_VOLUME)
            self._sfx_ch.play(snd)
            threading.Timer(snd.get_length() + 0.5, self._on_intro_done).start()
        else:
            self._on_intro_done()

    def _on_intro_done(self):
        self.start_phase1_theme()
        if _requests:
            try:
                _requests.post(
                    f"{PC1_URL}/game/intro_done",
                    headers={"X-API-Key": PC1_API_KEY},
                    timeout=2.0,
                )
            except Exception as e:
                print(f"[Audio] intro_done notify failed: {e}")

    # ── Phase themes (looping background music) ──────────────────────────────────

    def start_phase1_theme(self):
        self._start_theme(AUDIO_PHASE1_THEME)

    def start_phase2_theme(self):
        self._start_theme(AUDIO_PHASE2_THEME)

    def start_phase3_theme(self):
        self._start_theme(AUDIO_PHASE3_THEME)

    # ── Phase stories (one-shot narration → auto-starts phase theme) ─────────────

    def _play_story_then(self, snd, callback):
        self._story_ch.set_volume(STORY_VOLUME)
        self._story_ch.play(snd)
        def _wait():
            while self._story_ch.get_busy():
                time.sleep(0.1)
            time.sleep(1.5)
            callback()
        threading.Thread(target=_wait, daemon=True).start()

    def play_phase2_story(self):
        snd = self._load(AUDIO_PHASE2_STORY)
        if not snd:
            self.start_phase2_theme()
            return
        if self._ok:
            pygame.mixer.music.stop()
            self._play_story_then(snd, self.start_phase2_theme)

    def play_phase3_story(self):
        snd = self._load(AUDIO_PHASE3_STORY)
        if not snd:
            self.start_phase3_theme()
            return
        if self._ok:
            pygame.mixer.music.stop()
            self._play_story_then(snd, self.start_phase3_theme)

    # ── Victory ──────────────────────────────────────────────────────────────────

    def play_victory(self):
        snd = self._load(AUDIO_VICTORY)
        if not snd:
            return
        if self._ok:
            pygame.mixer.music.stop()
            self._story_ch.set_volume(STORY_VOLUME)
            self._story_ch.play(snd)

    # ── SFX (duck theme, restore after) ──────────────────────────────────────────

    def play_sfx(self, path):
        snd = self._load(path)
        if not snd:
            return
        if self._ok:
            pygame.mixer.music.set_volume(DUCK_VOLUME)
            threading.Timer(snd.get_length() + 0.5, self._unduck).start()
            self._sfx_ch.set_volume(SFX_VOLUME)
            self._sfx_ch.play(snd)

    # ── Utilities ─────────────────────────────────────────────────────────────────

    def stop_all(self):
        if not self._ok:
            return
        pygame.mixer.music.stop()
        pygame.mixer.stop()

    def restore_theme(self):
        if not self._ok:
            return
        if not pygame.mixer.music.get_busy():
            self._start_theme(self._current_theme)
        else:
            pygame.mixer.music.set_volume(THEME_VOLUME)


audio_manager = AudioManager()
