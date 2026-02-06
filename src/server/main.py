"""Standalone entrypoint for running the API via `python -m server.main`."""

from __future__ import annotations

import uvicorn

from .app import create_app

app = create_app()


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
