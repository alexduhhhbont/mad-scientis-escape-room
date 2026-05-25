from typing import Optional

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from pc2.api.server import app
from pc2.config import API_KEY
from pc2.lighting.controller import controller
from pc2.lighting.scenes import SCENES
from pc2.log import log_queue


def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


class FixtureItem(BaseModel):
    id:        int
    r:         int
    g:         int
    b:         int
    intensity: int = 255


class StaticPayload(BaseModel):
    channels: Optional[dict[str, int]] = None
    fixtures: Optional[list[FixtureItem]] = None


class SequencePayload(BaseModel):
    type:         str
    color:        list[int]
    intensity:    int   = 255
    frequency_hz: float = 2.0
    duration_sec: float = 5.0


@app.post("/lights/static", dependencies=[Depends(require_api_key)])
def lights_static(payload: StaticPayload):
    if payload.channels:
        controller.apply_static({int(k): v for k, v in payload.channels.items()})
        log_queue.put(f"API /lights/static → {len(payload.channels)} channels")
    if payload.fixtures:
        for f in payload.fixtures:
            controller.apply_fixture(f.id, f.r, f.g, f.b, f.intensity)
        log_queue.put(f"API /lights/static → {len(payload.fixtures)} fixture(s)")
    return {"status": "ok"}


@app.post("/lights/sequence", dependencies=[Depends(require_api_key)])
def lights_sequence(payload: SequencePayload):
    if len(payload.color) != 3:
        raise HTTPException(status_code=422, detail="color must be [r, g, b]")
    if payload.type not in ("flash", "pulse", "strobe"):
        raise HTTPException(status_code=422, detail="type must be flash, pulse, or strobe")
    controller.start_sequence(
        seq_type=payload.type,
        color=tuple(payload.color),
        intensity=payload.intensity,
        frequency_hz=payload.frequency_hz,
        duration_sec=payload.duration_sec,
    )
    log_queue.put(
        f"API /lights/sequence → {payload.type} {payload.color} "
        f"{payload.duration_sec}s @ {payload.frequency_hz}Hz"
    )
    return {"status": "ok", "expires_in_sec": payload.duration_sec}


@app.post("/lights/blackout", dependencies=[Depends(require_api_key)])
def lights_blackout():
    controller.blackout()
    log_queue.put("API /lights/blackout")
    return {"status": "ok"}


class ScenePayload(BaseModel):
    name:     str
    duration: float = 0.0   # seconds; 0 = permanent
    restore:  str   = ""    # scene name to restore after duration expires
    fade:     float = 0.0   # fade-in duration in seconds; 0 = hard cut


@app.post("/lights/scene", dependencies=[Depends(require_api_key)])
def lights_scene(payload: ScenePayload):
    jobs = SCENES.get(payload.name)
    if jobs is None:
        raise HTTPException(status_code=404, detail=f"Unknown scene: {payload.name}")
    controller.set_scene(list(jobs), payload.duration, payload.restore, payload.fade)
    suffix = f" for {payload.duration}s → {payload.restore}" if payload.duration else ""
    log_queue.put(f"API /lights/scene → {payload.name}{suffix}")
    return {"status": "ok", "scene": payload.name}


@app.get("/status")
def status():
    return controller.get_status()
