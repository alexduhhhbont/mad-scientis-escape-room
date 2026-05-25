import uvicorn
from fastapi import FastAPI

from pc2.config import API_HOST, API_PORT

app = FastAPI(title="Escape Room Controller", docs_url=None, redoc_url=None)


def run_server():
    # Import routers here so routes register onto `app` before uvicorn starts
    from pc2.api import lights, gm, audio  # noqa: F401

    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    server.run()
