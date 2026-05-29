from fastapi import Depends, HTTPException

from pc2.api.server import app
from pc2.api.lights import require_api_key
from pc2.audio import audio_manager
from pc2.config import AUDIO_WRONG, AUDIO_HINT
from pc2.log import log_queue


@app.post("/audio/{action}", dependencies=[Depends(require_api_key)])
def api_audio(action: str):
    actions = {
        "waiting":       audio_manager.play_waiting,
        "intro":         audio_manager.play_intro,
        "phase1_theme":  audio_manager.start_phase1_theme,
        "phase2_story":  audio_manager.play_phase2_story,
        "phase2_theme":  audio_manager.start_phase2_theme,
        "phase3_story":  audio_manager.play_phase3_story,
        "phase3_theme":  audio_manager.start_phase3_theme,
        "victory":       audio_manager.play_victory,
        "wrong":         lambda: audio_manager.play_sfx(AUDIO_WRONG),
        "hint":          lambda: audio_manager.play_sfx(AUDIO_HINT),
        "stop":          audio_manager.stop_all,
        "restore":       audio_manager.restore_theme,
    }
    if action not in actions:
        raise HTTPException(status_code=404, detail=f"Unknown audio action: {action}")
    actions[action]()
    log_queue.put(f"API /audio/{action}")
    return {"status": "ok", "action": action}
