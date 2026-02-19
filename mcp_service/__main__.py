from __future__ import annotations

import uvicorn

from mcp_service.api import app
from mcp_service.config import settings


def main() -> None:
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
