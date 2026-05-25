import os
import threading

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False
    print("[Audio] pygame not installed — audio disabled.  Run: pip install pygame")

from pc1.config import (
    AUDIO_INTRO, AUDIO_MAIN_THEME, AUDIO_WRONG,
    AUDIO_STAGE1_STORY, AUDIO_VICTORY, AUDIO_HINT,
    THEME_VOLUME, DUCK_VOLUME, SFX_VOLUME,
)


class AudioManager:
    def __init__(self):
        self._ok = False
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

    def _unduck(self):
        if self._ok:
            pygame.mixer.music.set_volume(THEME_VOLUME)

    def play_intro(self):
        """Play intro once, then automatically start the looping theme."""
        if not self._ok:
            return
        snd = self._load(AUDIO_INTRO)
        if snd:
            self._sfx_ch.set_volume(SFX_VOLUME)
            self._sfx_ch.play(snd)
            threading.Timer(snd.get_length() + 0.5, self.start_main_theme).start()
        else:
            self.start_main_theme()

    def start_main_theme(self):
        if not self._ok:
            return
        if not os.path.exists(AUDIO_MAIN_THEME):
            print(f"[Audio] main theme not found: {AUDIO_MAIN_THEME}")
            return
        try:
            pygame.mixer.music.load(AUDIO_MAIN_THEME)
            pygame.mixer.music.set_volume(THEME_VOLUME)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"[Audio] theme error: {e}")

    def play_sfx(self, path):
        """Short SFX — ducks theme for its duration then restores."""
        snd = self._load(path)
        if not snd:
            return
        if self._ok:
            pygame.mixer.music.set_volume(DUCK_VOLUME)
            threading.Timer(snd.get_length() + 0.5, self._unduck).start()
            self._sfx_ch.set_volume(SFX_VOLUME)
            self._sfx_ch.play(snd)

    def play_story(self, path):
        """Longer story / victory clip — ducks theme while it plays."""
        snd = self._load(path)
        if not snd:
            return
        if self._ok:
            pygame.mixer.music.set_volume(DUCK_VOLUME)
            threading.Timer(snd.get_length() + 1.5, self._unduck).start()
            self._story_ch.set_volume(SFX_VOLUME)
            self._story_ch.play(snd)

    def stop_all(self):
        if not self._ok:
            return
        pygame.mixer.music.stop()
        pygame.mixer.stop()

    def restore_theme(self):
        if not self._ok:
            return
        if not pygame.mixer.music.get_busy():
            self.start_main_theme()
        else:
            pygame.mixer.music.set_volume(THEME_VOLUME)
