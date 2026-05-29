import threading
import time
from typing import TYPE_CHECKING, Optional

import requests
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException

from pc1.config import PC1_API_PORT, PC1_API_KEY, PC2_URL, PC2_API_KEY

if TYPE_CHECKING:
    from pc1.app import EscapeRoomApp

_game_app: Optional["EscapeRoomApp"] = None


def set_game_app(app: "EscapeRoomApp") -> None:
    global _game_app
    _game_app = app


def notify_pc2(endpoint: str, payload: dict) -> None:
    def _send():
        try:
            requests.post(
                f"{PC2_URL}/{endpoint}",
                json=payload,
                headers={"X-API-Key": PC2_API_KEY},
                timeout=1.0,
            )
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


pc1_api = FastAPI(title="PC1 Game Control", docs_url=None, redoc_url=None)


def _require_key(x_api_key: str = Header(...)):
    if x_api_key != PC1_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@pc1_api.get("/game/status")
def api_game_status():
    if _game_app:
        elapsed = _game_app.game_elapsed_sec
        if _game_app.game_running and _game_app.game_start_time:
            elapsed += time.monotonic() - _game_app.game_start_time
        return {
            "stage":         _game_app.stage,
            "attempts":      _game_app.attempt_count,
            "timer_sec":     int(elapsed),
            "timer_running": _game_app.game_running,
        }
    return {"stage": "starting", "attempts": 0, "timer_sec": 0, "timer_running": False}


@pc1_api.post("/game/reset", dependencies=[Depends(_require_key)])
def api_game_reset():
    if _game_app:
        _game_app.gm_reset()
    return {"status": "ok"}


@pc1_api.post("/game/start", dependencies=[Depends(_require_key)])
def api_game_start():
    if _game_app:
        _game_app.gm_start()
    return {"status": "ok"}


@pc1_api.post("/game/pause", dependencies=[Depends(_require_key)])
def api_game_pause():
    if _game_app:
        _game_app.gm_pause()
    return {"status": "ok"}


@pc1_api.post("/game/skip_s1", dependencies=[Depends(_require_key)])
def api_game_skip_s1():
    if _game_app:
        _game_app.gm_skip_to_stage1()
    return {"status": "ok"}


@pc1_api.post("/game/skip_s2", dependencies=[Depends(_require_key)])
def api_game_skip_s2():
    if _game_app:
        _game_app.gm_skip_to_stage2()
    return {"status": "ok"}


@pc1_api.post("/game/skip_s3", dependencies=[Depends(_require_key)])
def api_game_skip_s3():
    if _game_app:
        _game_app.gm_skip_to_stage3()
    return {"status": "ok"}


@pc1_api.post("/game/victory", dependencies=[Depends(_require_key)])
def api_game_victory():
    if _game_app:
        _game_app.gm_trigger_victory()
    return {"status": "ok"}


@pc1_api.post("/game/intro_done", dependencies=[Depends(_require_key)])
def api_intro_done():
    if _game_app:
        _game_app.gm_intro_done()
    return {"status": "ok"}



def run_api_server() -> None:
    config = uvicorn.Config(pc1_api, host="0.0.0.0", port=PC1_API_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    server.run()
