from fastapi import HTTPException

from pc2.api.server import app
from pc2.audio import audio_manager
from pc2.config import AUDIO_WRONG, AUDIO_STAGE1_STORY, AUDIO_VICTORY, AUDIO_HINT
from pc2.log import log_queue

from pc2.api.lights import require_api_key
from fastapi import Depends


@app.post("/audio/{action}", dependencies=[Depends(require_api_key)])
def api_audio(action: str):
    actions = {
        "waiting": audio_manager.play_waiting,
        "intro":   audio_manager.play_intro,
        "theme":   audio_manager.start_main_theme,
        "wrong":   lambda: audio_manager.play_sfx(AUDIO_WRONG),
        "story":   lambda: audio_manager.play_story(AUDIO_STAGE1_STORY),
        "victory": lambda: audio_manager.play_story(AUDIO_VICTORY),
        "hint":    lambda: audio_manager.play_sfx(AUDIO_HINT),
        "stop":    audio_manager.stop_all,
        "restore": audio_manager.restore_theme,
    }
    if action not in actions:
        raise HTTPException(status_code=404, detail=f"Unknown audio action: {action}")
    actions[action]()
    log_queue.put(f"API /audio/{action}")
    return {"status": "ok", "action": action}
