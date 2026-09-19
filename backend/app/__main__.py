"""Module entrypoint: 'python -m app' runs uvicorn."""
import uvicorn

from .config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.backend_port, reload=settings.debug)

