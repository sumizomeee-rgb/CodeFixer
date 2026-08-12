from __future__ import annotations

import uvicorn

from codefixer.config import load_config


def main() -> None:
    loaded = load_config()
    uvicorn.run("codefixer.main:app", host=loaded.config.server.host, port=loaded.config.server.port, log_level="info")


if __name__ == "__main__":
    main()
