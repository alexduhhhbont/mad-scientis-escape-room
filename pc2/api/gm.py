import requests as _requests

from fastapi import Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from pc2.api.server import app
from pc2.audio import audio_manager
from pc2.config import (
    GM_KEY, PC1_URL, PC1_API_KEY, API_PORT,
    AUDIO_WRONG, AUDIO_STAGE1_STORY, AUDIO_VICTORY, AUDIO_HINT,
)
from pc2.lighting.controller import controller
from pc2.lighting.scenes import SCENES
from pc2.log import log_queue

# Maps GM action name → (scene_name, duration_sec, restore_scene)
# duration=0 means permanent; restore="" means no restore.
_SCENE_ACTIONS: dict = {
    "waiting":        ("waiting",        0,   ""),
    "intro":          ("intro",          0,   ""),
    "rainbow":        ("rainbow",        0,   ""),
    "phase1":         ("phase1",         0,   ""),
    "phase2":         ("phase2",         0,   ""),
    "phase1_correct": ("phase1_correct", 0,   ""),
    "phase1_wrong":   ("phase1_wrong",   3.0, "phase1"),
    "phase2_wrong":   ("phase2_wrong",   3.0, "phase2"),
    "victory_green":  ("victory_green",  8.0, "rainbow"),
}

_GM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>🍬 Candy Factory GM</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #1a0030; color: #ff69b4;
           font-family: 'Courier New', monospace; padding: 12px; }
    h1  { color: #ffd700; font-size: 1.15rem; text-align: center; margin-bottom: 12px; }
    h3  { color: #cc44ff; font-size: 0.85rem; margin-bottom: 8px; }
    .card { background: #2a0045; border-radius: 10px; padding: 14px;
            margin-bottom: 12px; border: 1px solid #8800cc; }
    .timer  { font-size: 2rem; color: #884488; text-align: center; padding: 2px 4px;
              font-weight: bold; letter-spacing: 4px; }
    .status { font-size: 0.85rem; color: #884488; text-align: center; padding: 4px; }
    .grid   { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .btn {
      width: 100%; padding: 14px 6px; font-size: 0.9rem; border: none;
      border-radius: 8px; cursor: pointer; font-weight: bold;
      font-family: 'Courier New', monospace; transition: opacity 0.1s;
    }
    .btn:active { opacity: 0.65; }
    .btn-pink   { background: #ff69b4; color: #1a0030; }
    .btn-yellow { background: #ffd700; color: #1a0030; }
    .btn-purple { background: #cc44ff; color: #fff; }
    .btn-orange { background: #ff8c00; color: #fff; }
    .btn-red    { background: #cc1111; color: #fff; }
    .btn-green  { background: #00cc33; color: #000; }
    .btn-aqua   { background: #00c8b4; color: #000; }
    .btn-dark   { background: #3d0060; color: #cc44ff; border: 1px solid #8800cc; }
    .full { grid-column: 1 / -1; }
    .secondary { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
    .secondary .btn { padding: 10px 6px; font-size: 0.8rem; }
    h4 { color: #884488; font-size: 0.75rem; margin: 10px 0 6px; letter-spacing: 1px; }
    .toast {
      position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
      background: #ffd700; color: #1a0030; padding: 10px 22px; border-radius: 20px;
      font-weight: bold; opacity: 0; transition: opacity 0.3s; pointer-events: none;
      white-space: nowrap; z-index: 999;
    }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <h1>🍬 Candy Factory GM Panel</h1>

  <div class="card">
    <div class="timer" id="timer">⏹ --:--</div>
    <div class="status" id="status">Connecting...</div>
  </div>

  <div class="card">
    <h3>🎮 Game Controls</h3>
    <div class="grid">
      <button class="btn btn-green"  onclick="ctrl('game/start')">▶ START</button>
      <button class="btn btn-orange" id="btn-pause" onclick="ctrl('game/pause')">⏸ PAUSE</button>
      <button class="btn btn-yellow" onclick="ctrl('game/victory')">🏆 WIN</button>
      <button class="btn btn-red"    onclick="confirmReset()">↺ RESET</button>
    </div>
    <div class="secondary">
      <button class="btn btn-purple" onclick="ctrl('game/hint')">💡 Hint</button>
      <button class="btn btn-dark"   onclick="ctrl('game/skip_s2')">⏭ Stage 2</button>
    </div>
  </div>

  <div class="card">
    <h3>🎵 Audio</h3>
    <div class="grid">
      <button class="btn btn-yellow" onclick="ctrl('audio/intro')">▶ Intro</button>
      <button class="btn btn-pink"   onclick="ctrl('audio/theme')">♫ Theme</button>
      <button class="btn btn-orange" onclick="ctrl('audio/wrong')">⚠ Wrong SFX</button>
      <button class="btn btn-purple" onclick="ctrl('audio/story')">📖 Story</button>
      <button class="btn btn-yellow" onclick="ctrl('audio/victory')">🏆 Victory</button>
      <button class="btn btn-purple" onclick="ctrl('audio/hint')">💡 Hint</button>
      <button class="btn btn-dark"   onclick="ctrl('audio/restore')">↺ Restore</button>
      <button class="btn btn-red"    onclick="ctrl('audio/stop')">■ Stop All</button>
    </div>
  </div>

  <div class="card">
    <h3>💡 Lights</h3>

    <h4>PHASE SCENES</h4>
    <div class="grid">
      <button class="btn btn-yellow" onclick="scene('waiting')">🌙 Waiting</button>
      <button class="btn btn-pink"   onclick="scene('intro')">🌈 Intro</button>
      <button class="btn btn-orange" onclick="scene('phase1')">🔑 Phase 1</button>
      <button class="btn btn-purple" onclick="scene('phase2')">🔧 Phase 2</button>
      <button class="btn btn-pink full" onclick="scene('rainbow')">🌈 Rainbow</button>
    </div>

    <h4>EVENT SCENES</h4>
    <div class="grid">
      <button class="btn btn-green"  onclick="scene('phase1_correct')">✅ P1 Correct</button>
      <button class="btn btn-red"    onclick="scene('phase1_wrong')">❌ P1 Wrong</button>
      <button class="btn btn-green"  onclick="scene('victory_green')">🏆 Victory</button>
      <button class="btn btn-red"    onclick="scene('phase2_wrong')">❌ P2 Wrong</button>
    </div>

    <div style="margin-top:10px">
      <button class="btn btn-dark full" onclick="ctrl('lights/blackout')" style="width:100%;padding:14px">⬛ BLACKOUT</button>
    </div>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    const KEY = "__GM_KEY__";

    async function ctrl(endpoint) {
      try {
        const r = await fetch('/gm/ctrl/' + endpoint + '?key=' + KEY, {method: 'POST'});
        const j = await r.json();
        toast(j.msg || j.error || 'OK');
        setTimeout(refreshStatus, 400);
      } catch(e) { toast('Network error'); }
    }

    async function scene(name) {
      try {
        const r = await fetch('/gm/ctrl/lights/' + name + '?key=' + KEY, {method: 'POST'});
        const j = await r.json();
        toast(j.msg || j.error || 'OK');
      } catch(e) { toast('Network error'); }
    }

    function confirmReset() {
      if (confirm('Reset the game back to Stage 1?')) ctrl('game/reset');
    }

    async function refreshStatus() {
      try {
        const r = await fetch('/gm/status?key=' + KEY);
        const j = await r.json();
        const sec = j.timer_sec || 0;
        const m   = Math.floor(sec / 60);
        const s   = sec % 60;
        const pad = n => String(n).padStart(2, '0');
        const timerEl = document.getElementById('timer');
        if (j.timer_running) {
          timerEl.textContent = '▶ ' + pad(m) + ':' + pad(s);
          timerEl.style.color = '#ffd700';
        } else if (sec > 0) {
          timerEl.textContent = '⏸ ' + pad(m) + ':' + pad(s);
          timerEl.style.color = '#ff8c00';
        } else {
          timerEl.textContent = '⏹ --:--';
          timerEl.style.color = '#884488';
        }
        document.getElementById('status').textContent =
          '📍 ' + j.stage.toUpperCase() +
          '   ❌ Fails: ' + j.attempts +
          '   DMX: ' + j.dmx;
        const pb = document.getElementById('btn-pause');
        if (pb) pb.textContent = j.timer_running ? '⏸ PAUSE' : '▶ RESUME';
      } catch(e) {}
    }

    function toast(msg) {
      const el = document.getElementById('toast');
      el.textContent = msg;
      el.classList.add('show');
      clearTimeout(el._t);
      el._t = setTimeout(() => el.classList.remove('show'), 2200);
    }

    setInterval(refreshStatus, 3000);
    refreshStatus();
  </script>
</body>
</html>
"""


def _call_pc1(method: str, endpoint: str) -> dict:
    try:
        r = _requests.request(
            method,
            f"{PC1_URL}/{endpoint}",
            headers={"X-API-Key": PC1_API_KEY},
            timeout=2.0,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _gm_auth(key: str = Query(default="")):
    if key != GM_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")


@app.get("/gm", response_class=HTMLResponse)
def gm_panel(key: str = Query(default="")):
    if key != GM_KEY:
        return HTMLResponse("Unauthorized — add ?key=YOUR_KEY to the URL", status_code=403)
    html = _GM_HTML.replace("__GM_KEY__", key)
    return HTMLResponse(html)


@app.get("/gm/status", dependencies=[Depends(_gm_auth)])
def gm_status():
    pc1 = _call_pc1("GET", "game/status")
    dmx = controller.get_status()
    return {
        "stage":         pc1.get("stage", "unknown"),
        "attempts":      pc1.get("attempts", 0),
        "timer_sec":     pc1.get("timer_sec", 0),
        "timer_running": pc1.get("timer_running", False),
        "dmx":           "ONLINE" if dmx["dmx_streaming"] else "OFFLINE",
    }


@app.post("/gm/ctrl/audio/{action}", dependencies=[Depends(_gm_auth)])
def gm_audio(action: str):
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
    log_queue.put(f"GM audio/{action}")
    return {"msg": f"▶ audio/{action}"}


@app.post("/gm/ctrl/lights/{action}", dependencies=[Depends(_gm_auth)])
def gm_lights(action: str):
    if action == "blackout":
        controller.blackout()
        log_queue.put("GM lights/blackout")
        return {"msg": "⬛ blackout"}

    entry = _SCENE_ACTIONS.get(action)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown light action: {action}")

    scene_name, duration, restore = entry
    jobs = SCENES.get(scene_name, [])
    controller.set_scene(list(jobs), duration, restore)
    suffix = f" ({duration}s → {restore})" if duration else ""
    log_queue.put(f"GM lights/{action} → scene:{scene_name}{suffix}")
    return {"msg": f"💡 {action}{suffix}"}


@app.post("/gm/ctrl/game/{action}", dependencies=[Depends(_gm_auth)])
def gm_game(action: str):
    endpoint_map = {
        "reset":   "game/reset",
        "start":   "game/start",
        "pause":   "game/pause",
        "skip_s2": "game/skip_s2",
        "victory": "game/victory",
        "hint":    "game/audio/hint",
    }
    if action not in endpoint_map:
        raise HTTPException(status_code=404, detail="Unknown action")
    result = _call_pc1("POST", endpoint_map[action])
    log_queue.put(f"GM game/{action} → {result}")
    return {"msg": f"✓ game/{action}", **result}
